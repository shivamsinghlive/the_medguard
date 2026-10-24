"""Change preview (W03): allowlisted actions on a separate copy, protected roles blocked."""
import json
from pathlib import Path
import socket
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.change_preview import preview_changes
from services.contracts import ChangePreviewError
from utils.audit_input import dataset_fingerprint

ROLES = {'patient_id': 'identifier', 'sex': 'demographic', 'outcome': 'outcome',
         'risk_score': 'prediction', 'chol': 'feature'}


def frame():
    return pd.DataFrame({
        'patient_id': ['P1', 'P2', 'P2', 'P3', 'P4'],
        'sex': ['Female', 'Male', 'Male', None, 'Female '],
        'chol': [200.0, np.nan, np.nan, 240.0, 220.0],
        'note': [' ok', 'ok ', 'ok ', None, 'fine'],
        'outcome': [0, 1, 1, np.nan, 0],
        'risk_score': [0.2, 0.7, 0.7, 0.5, 0.1],
    })


def preview(df, actions, roles=ROLES):
    before, fingerprint = df.copy(deep=True), dataset_fingerprint(df)
    result, out = preview_changes(df, actions, column_roles=roles)
    json.dumps(result, allow_nan=False)
    pd.testing.assert_frame_equal(df, before)  # source is never modified
    assert dataset_fingerprint(df) == fingerprint == result['source_fingerprint']
    assert (result['status'] == 'preview_ready') == (out is not None)
    if out is not None:
        assert out is not df
        assert result['output_fingerprint'] == dataset_fingerprint(out)
    return result, out


def test_no_actions_returns_identical_copy():
    df = frame()
    result, out = preview(df, [])
    pd.testing.assert_frame_equal(out, df)
    assert result['schema'] == {'columns_removed': [], 'dtype_changes': [],
                                'column_order_preserved': True, 'preserved': True}
    assert result['output_fingerprint'] == result['source_fingerprint']


def test_drop_duplicate_rows_keeps_first_and_source_index():
    df = frame()
    result, out = preview(df, [{'action': 'drop_duplicate_rows'}])
    assert result['actions'][0]['evidence'] == {'rows_removed': 1}
    assert list(out.index) == [0, 1, 3, 4]
    assert result['before']['row_count'] == 5 and result['after']['row_count'] == 4
    assert result['before']['demographic_counts']['sex']['counts']['Male'] == 2
    assert result['after']['demographic_counts']['sex']['counts']['Male'] == 1


def test_fill_missing_median_reports_value_and_preserves_schema():
    df = frame()
    result, out = preview(df, [{'action': 'fill_missing', 'column': 'chol', 'method': 'median'}])
    action = result['actions'][0]
    assert action['status'] == 'applied'
    assert action['evidence'] == {'method': 'median', 'fill_value': 220.0, 'cells_changed': 2}
    assert any('Median fill' in w for w in action['warnings'])
    assert out['chol'].tolist() == [200.0, 220.0, 220.0, 240.0, 220.0]
    assert (out.dtypes == df.dtypes).all() and list(out.columns) == list(df.columns)
    assert df['chol'].isna().sum() == 2  # source still has its missing values


def test_fill_missing_constant_on_text_and_strip_whitespace():
    df = frame()
    result, out = preview(df, [
        {'action': 'strip_whitespace', 'column': 'note'},
        {'action': 'fill_missing', 'column': 'note', 'method': 'constant', 'value': 'not recorded'},
    ])
    assert [a['status'] for a in result['actions']] == ['applied', 'applied']
    assert result['actions'][0]['evidence'] == {
        'cells_changed': 3, 'distinct_values_before': 3, 'distinct_values_after': 2}
    assert result['actions'][1]['evidence']['cells_changed'] == 1
    assert out['note'].tolist() == ['ok', 'ok', 'ok', 'not recorded', 'fine']
    assert result['actions'][0]['warnings'] == ['Column note has no assigned role.']


def test_drop_rows_with_missing_shows_cohort_change():
    df = frame()
    result, out = preview(df, [{'action': 'drop_rows_with_missing', 'columns': ['chol']}])
    assert result['actions'][0]['evidence'] == {'rows_removed': 2}
    before = result['before']['demographic_counts']['sex']
    after = result['after']['demographic_counts']['sex']
    assert before['counts'] == {'Male': 2, 'Female': 1, 'Female ': 1}
    assert after['counts'] == {'Female': 1, 'Female ': 1}
    assert (before['missing_count'], after['missing_count']) == (1, 1)


@pytest.mark.parametrize('action', [
    {'action': 'fill_missing', 'column': 'outcome', 'method': 'median'},
    {'action': 'fill_missing', 'column': 'sex', 'method': 'constant', 'value': 'Unknown'},
    {'action': 'strip_whitespace', 'column': 'sex'},
    {'action': 'drop_column', 'column': 'patient_id'},
    {'action': 'drop_column', 'column': 'risk_score'},
    {'action': 'drop_rows_with_missing', 'columns': ['chol', 'outcome']},
])
def test_protected_roles_are_blocked_by_default(action):
    result, out = preview(frame(), [action])
    assert result['status'] == 'blocked' and out is None
    assert result['actions'][0]['status'] == 'blocked'
    assert 'Protected roles are not changed by default' in result['actions'][0]['reason']
    assert result['after'] is None and result['output_fingerprint'] is None


def test_explicit_override_is_applied_with_warning():
    result, out = preview(frame(), [{'action': 'drop_column', 'column': 'patient_id', 'allow_protected': True}])
    action = result['actions'][0]
    assert action['status'] == 'applied'
    assert action['warnings'] == ['Protected-role override for patient_id (identifier).']
    assert action['evidence'] == {'non_missing_values_removed': 5}
    assert 'patient_id' not in out.columns
    assert result['schema'] == {'columns_removed': ['patient_id'], 'dtype_changes': [],
                                'column_order_preserved': True, 'preserved': False}


@pytest.mark.parametrize('name', ['smote', 'SMOTE', 'oversample', 'balance_demographics',
                                  'resample', 'generate_synthetic', None])
def test_resampling_and_balancing_are_not_available(name):
    result, out = preview(frame(), [{'action': name}])
    assert out is None
    assert 'not in the allowlist' in result['actions'][0]['reason']


def test_a_blocked_action_blocks_the_whole_preview():
    result, out = preview(frame(), [
        {'action': 'drop_duplicate_rows'},
        {'action': 'smote'},
        {'action': 'strip_whitespace', 'column': 'note'},
    ])
    assert out is None
    assert [a['status'] for a in result['actions']] == ['applied', 'blocked', 'not_run']
    assert result['after'] is None and result['schema'] is None


@pytest.mark.parametrize('action,reason', [
    ({'action': 'fill_missing', 'column': 'note', 'method': 'median'}, 'numeric column'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'mean'}, 'not supported'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'constant'}, 'needs a value'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'constant', 'value': 'high'}, 'finite number'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'constant', 'value': float('nan')}, 'finite number'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'constant', 'value': True}, 'finite number'),
    ({'action': 'fill_missing', 'column': 'note', 'method': 'constant', 'value': 0}, 'needs text'),
    ({'action': 'fill_missing', 'column': 'chol', 'method': 'median', 'value': 1}, 'do not supply'),
    ({'action': 'fill_missing', 'column': 'empty', 'method': 'median'}, 'at least one observed'),
    ({'action': 'strip_whitespace', 'column': 'chol'}, 'text column'),
    ({'action': 'strip_whitespace', 'column': 'missing'}, 'not in the dataset'),
    ({'action': 'drop_rows_with_missing', 'columns': 'chol'}, 'non-empty list'),
    ({'action': 'drop_rows_with_missing', 'columns': []}, 'non-empty list'),
    ({'action': 'drop_column'}, 'missing'),
    ({'action': 'drop_duplicate_rows', 'subset': ['chol']}, 'unexpected'),
    ({'action': 'drop_column', 'column': 'chol', 'allow_protected': 'yes'}, 'true or false'),
    ({'action': 'fill_missing', 'column': 'seen', 'method': 'constant', 'value': 'unknown'}, 'column types'),
])
def test_invalid_actions_are_blocked_with_reasons(action, reason):
    df = frame().assign(empty=np.nan, seen=pd.to_datetime(['2024-01-01', None, None, None, None]))
    result, out = preview(df, [action])
    assert out is None
    assert reason in result['actions'][0]['reason']


def test_categorical_and_nullable_columns_do_not_silently_change_type():
    df = pd.DataFrame({'grade': pd.Categorical(['a', None, 'b']), 'n': pd.array([1, None, 3], dtype='Int64')})
    result, out = preview(df, [{'action': 'fill_missing', 'column': 'n', 'method': 'median'}], roles={})
    assert out['n'].dtype == 'Int64' and out['n'].tolist() == [1, 2, 3]
    blocked, _ = preview(df, [{'action': 'fill_missing', 'column': 'grade', 'method': 'constant',
                               'value': 'c'}], roles={})
    assert blocked['status'] == 'blocked'


def test_without_demographic_roles_cohort_counts_are_not_claimed():
    result, _ = preview(frame(), [{'action': 'drop_duplicate_rows'}], roles={})
    assert result['before']['demographic_counts'] == {} == result['after']['demographic_counts']
    assert any('No demographic columns were assigned' in l for l in result['limitations'])
    assert any('held-out data' in l for l in result['limitations'])


@pytest.mark.parametrize('actions,roles,message', [
    ({'action': 'drop_duplicate_rows'}, {}, 'list of action'),
    ('drop_duplicate_rows', {}, 'list of action'),
    ([['drop_duplicate_rows']], {}, 'list of action'),
    ([], {'unknown': 'feature'}, 'unknown column'),
    ([], {'sex': 'gender'}, 'must be one of'),
    ([], None, 'column_roles'),
])
def test_malformed_requests_raise(actions, roles, message):
    with pytest.raises(ChangePreviewError, match=message):
        preview_changes(frame(), actions, column_roles=roles)


def test_results_are_deterministic_and_run_without_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Change preview must not open network connections')
    monkeypatch.setattr(socket, 'socket', blocked)
    actions = [{'action': 'drop_duplicate_rows'},
               {'action': 'fill_missing', 'column': 'chol', 'method': 'median'}]
    first, out1 = preview(frame(), actions)
    second, out2 = preview(frame(), actions)
    assert first == second
    pd.testing.assert_frame_equal(out1, out2)
