"""Representation service (W01): descriptive evidence, never fairness verdicts."""
import json
from pathlib import Path
import socket
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.contracts import STATUSES, RepresentationInputError
from services.representation import analyze_representation
from utils.audit_input import dataset_fingerprint

FAIRNESS_LIMITATION = 'Representation does not measure model fairness or clinical harm.'
REFERENCE_LIMITATION = 'The reference population was supplied by the user.'


def analyze(df, columns, reference=None):
    result = analyze_representation(df, demographic_columns=columns, reference_proportions=reference)
    json.dumps(result, allow_nan=False)  # JSON-safe: no NaN/Infinity, no numpy types
    assert result['status'] in STATUSES
    assert all(a['status'] in STATUSES for a in result['attributes'])
    assert not any(word in json.dumps(result).upper() for word in ('FAIR"', 'BIASED', '"CLEAN'))
    return result


def attribute(result, column):
    return next(a for a in result['attributes'] if a['column'] == column)


def groups(result, column):
    return {g['label']: g for g in attribute(result, column)['groups']}


def codes(result):
    return [f['code'] for f in result['findings']]


def test_contract_example_with_explicit_reference():
    df = pd.DataFrame({'sex': ['Male'] * 100})
    result = analyze(df, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    assert result['schema_version'] == '1.0'
    assert result['scope'] == 'dataset_representation'
    assert result['status'] == 'review_needed'
    assert result['row_count'] == 100
    assert result['attributes'] == [{
        'column': 'sex', 'status': 'review_needed', 'observed_count': 100, 'missing_count': 0,
        'groups': [
            {'label': 'Male', 'count': 100, 'proportion': 1.0,
             'reference_proportion': 0.5, 'difference_pp': 50.0},
            {'label': 'Female', 'count': 0, 'proportion': 0.0,
             'reference_proportion': 0.5, 'difference_pp': -50.0},
        ],
    }]
    assert result['findings'][0] == {
        'id': 'sex:single_group', 'code': 'single_group', 'column': 'sex', 'priority': 'high',
        'title': 'Only one group is observed',
        'evidence': {'observed_group_count': 1, 'observed_count': 100},
        'suggested_action': 'Review intended population coverage.',
    }
    assert codes(result) == ['single_group', 'missing_reference_group']
    assert result['findings'][1]['evidence']['missing_groups'] == ['Female']
    assert result['limitations'][:2] == [FAIRNESS_LIMITATION, REFERENCE_LIMITATION]


def test_empty_selection_is_insufficient_evidence():
    result = analyze(pd.DataFrame({'age': [40, 50]}), [])
    assert result['status'] == 'insufficient_evidence'
    assert result['attributes'] == [] and result['findings'] == []
    assert result['row_count'] == 2
    assert any('No demographic columns were selected' in l for l in result['limitations'])


def test_dataset_without_demographic_columns_is_not_cleared():
    df = pd.DataFrame({'age': [40, 50, 60], 'outcome': [0, 1, 0]})
    assert analyze(df, [])['status'] == 'insufficient_evidence'
    with pytest.raises(RepresentationInputError, match='not found'):
        analyze_representation(df, demographic_columns=['sex'])


def test_zero_rows_is_insufficient_evidence():
    df = pd.DataFrame({'sex': pd.Series([], dtype=object)})
    result = analyze(df, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    assert result['status'] == 'insufficient_evidence'
    assert result['row_count'] == 0
    sex = attribute(result, 'sex')
    assert (sex['observed_count'], sex['missing_count']) == (0, 0)
    for group in sex['groups']:
        assert group['count'] == 0 and group['proportion'] is None and group['difference_pp'] is None
        assert group['reference_proportion'] == 0.5
    assert codes(result) == ['no_observed_values']
    assert 'The dataset has no rows.' in result['limitations']


def test_all_null_column_is_insufficient_evidence():
    df = pd.DataFrame({'race': [None, np.nan, None], 'age': [1, 2, 3]})
    result = analyze(df, ['race'])
    race = attribute(result, 'race')
    assert result['status'] == race['status'] == 'insufficient_evidence'
    assert (race['observed_count'], race['missing_count'], race['groups']) == (0, 3, [])
    assert result['findings'][0]['evidence'] == {'row_count': 3, 'missing_count': 3}


def test_single_group_without_reference_needs_review_but_is_not_bias_proof():
    result = analyze(pd.DataFrame({'sex': ['Female'] * 4}), ['sex'])
    assert result['status'] == 'review_needed'
    assert groups(result, 'sex') == {'Female': {
        'label': 'Female', 'count': 4, 'proportion': 1.0,
        'reference_proportion': None, 'difference_pp': None}}
    assert codes(result) == ['single_group']
    assert REFERENCE_LIMITATION not in result['limitations']


def test_nonbinary_groups_are_descriptive_without_threshold():
    df = pd.DataFrame({'gender': ['Woman'] * 45 + ['Man'] * 45 + ['Nonbinary'] * 10})
    result = analyze(df, ['gender'])
    assert result['status'] == 'descriptive_only'
    assert result['findings'] == []
    assert [g['label'] for g in attribute(result, 'gender')['groups']] == ['Man', 'Woman', 'Nonbinary']
    assert groups(result, 'gender')['Nonbinary']['proportion'] == pytest.approx(0.1)
    assert all(g['reference_proportion'] is None and g['difference_pp'] is None
               for g in attribute(result, 'gender')['groups'])


def test_nonbinary_group_outside_supplied_reference_is_flagged():
    df = pd.DataFrame({'gender': ['Woman'] * 5 + ['Man'] * 4 + ['Nonbinary']})
    result = analyze(df, ['gender'], {'gender': {'Woman': 0.5, 'Man': 0.5}})
    nonbinary = groups(result, 'gender')['Nonbinary']
    assert nonbinary['reference_proportion'] is None and nonbinary['difference_pp'] is None
    assert codes(result) == ['group_not_in_reference']
    assert result['findings'][0]['evidence'] == {'groups': ['Nonbinary'], 'count': 1}
    assert groups(result, 'gender')['Woman']['difference_pp'] == pytest.approx(0.0)


def test_numeric_codes_keep_their_recorded_labels():
    df = pd.DataFrame({'sex': [1, 0, 1, 1], 'race': [2.0, np.nan, 2.0, 3.0]})
    result = analyze(df, ['sex', 'race'])
    assert set(groups(result, 'sex')) == {'1', '0'}  # never mapped to Male/Female
    assert groups(result, 'sex')['1']['count'] == 3
    race = attribute(result, 'race')
    assert {g['label']: g['count'] for g in race['groups']} == {'2': 2, '3': 1}
    assert (race['observed_count'], race['missing_count']) == (3, 1)
    assert 'Male' not in json.dumps(result)


def test_numeric_codes_match_reference_keyed_by_code_not_by_meaning():
    df = pd.DataFrame({'sex': [1, 1, 1, 2]})
    by_code = analyze(df, ['sex'], {'sex': {1: 0.5, '2': 0.5}})
    assert groups(by_code, 'sex')['1']['difference_pp'] == pytest.approx(25.0)
    assert by_code['findings'] == [] and by_code['status'] == 'descriptive_only'
    by_name = analyze(df, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    assert codes(by_name) == ['missing_reference_group', 'group_not_in_reference']


def test_missing_values_are_excluded_from_denominator():
    df = pd.DataFrame({'sex': ['Male', 'Female', None, 'Female', np.nan]})
    sex = attribute(analyze(df, ['sex']), 'sex')
    assert (sex['observed_count'], sex['missing_count']) == (3, 2)
    assert {g['label']: g['proportion'] for g in sex['groups']} == pytest.approx(
        {'Female': 2 / 3, 'Male': 1 / 3})


def test_reference_differences_and_missing_expected_group():
    df = pd.DataFrame({'race': ['White'] * 7 + ['Black'] * 3})
    reference = {'race': {'White': 0.6, 'Black': 0.13, 'Asian': 0.27, 'Other': 0.0}}
    result = analyze(df, ['race'], reference)
    race = groups(result, 'race')
    assert race['White']['difference_pp'] == pytest.approx(10.0)
    assert race['Black']['difference_pp'] == pytest.approx(17.0)
    assert race['Asian'] == {'label': 'Asian', 'count': 0, 'proportion': 0.0,
                             'reference_proportion': 0.27, 'difference_pp': -27.0}
    assert race['Other']['reference_proportion'] == 0.0  # zero expected share is not "missing"
    assert codes(result) == ['missing_reference_group']
    assert result['findings'][0]['evidence']['missing_groups'] == ['Asian']


def test_reference_without_flags_stays_descriptive():
    df = pd.DataFrame({'sex': ['Male'] * 80 + ['Female'] * 20})
    result = analyze(df, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    # A large difference is reported, not judged; v1 has no threshold policy.
    assert result['status'] == 'descriptive_only'
    assert groups(result, 'sex')['Male']['difference_pp'] == pytest.approx(30.0)
    assert REFERENCE_LIMITATION in result['limitations']


def test_status_precedence_and_per_attribute_status():
    df = pd.DataFrame({'sex': ['Male', 'Female'], 'race': [None, None], 'site': ['A', 'A']})
    assert analyze(df, ['sex'])['status'] == 'descriptive_only'
    assert analyze(df, ['sex', 'race'])['status'] == 'insufficient_evidence'
    result = analyze(df, ['sex', 'race', 'site'])
    assert result['status'] == 'review_needed'
    assert [a['status'] for a in result['attributes']] == [
        'descriptive_only', 'insufficient_evidence', 'review_needed']
    assert [f['id'] for f in result['findings']] == ['race:no_observed_values', 'site:single_group']


def test_findings_are_ordered_by_priority_then_column():
    df = pd.DataFrame({'a': ['x', 'y', 'z'], 'b': ['q', 'q', 'q']})
    result = analyze(df, ['a', 'b'], {'a': {'x': 0.5, 'y': 0.5}})
    assert [f['id'] for f in result['findings']] == ['b:single_group', 'a:group_not_in_reference']
    assert len({f['id'] for f in result['findings']}) == len(result['findings'])


def test_unused_categorical_levels_are_not_observed_groups():
    df = pd.DataFrame({'sex': pd.Categorical(['Female', 'Female'], categories=['Female', 'Male'])})
    result = analyze(df, ['sex'])
    assert codes(result) == ['single_group']
    assert list(groups(result, 'sex')) == ['Female']


@pytest.mark.parametrize('reference,message', [
    ({'sex': {'Male': 0.6, 'Female': 0.6}}, 'sums to'),
    ({'sex': {'Male': 0.3, 'Female': 0.3}}, 'sums to'),
    ({'sex': {'Male': 1.5, 'Female': -0.5}}, r'\[0, 1\]'),
    ({'sex': {'Male': float('nan'), 'Female': 0.5}}, r'\[0, 1\]'),
    ({'sex': {'Male': float('inf')}}, r'\[0, 1\]'),
    ({'sex': {'Male': True}}, r'\[0, 1\]'),
    ({'sex': {'Male': '0.5', 'Female': 0.5}}, r'\[0, 1\]'),
    ({'sex': {}}, 'non-empty'),
    ({'sex': [0.5, 0.5]}, 'non-empty mapping'),
    ({'race': {'White': 1.0}}, 'unselected'),
    ({'sex': {1: 0.5, '1': 0.5}}, 'repeats'),
    ([('sex', {'Male': 1.0})], 'must map'),
])
def test_invalid_references_are_rejected(reference, message):
    df = pd.DataFrame({'sex': ['Male', 'Female'], 'race': ['A', 'B']})
    with pytest.raises(RepresentationInputError, match=message):
        analyze_representation(df, demographic_columns=['sex'], reference_proportions=reference)


@pytest.mark.parametrize('df,columns,message', [
    (pd.DataFrame({'sex': ['M']}), 'sex', 'list of column names'),
    (pd.DataFrame({'sex': ['M']}), None, 'list of column names'),
    (pd.DataFrame({'sex': ['M']}), ['sex', 'sex'], 'more than once'),
    (pd.DataFrame({'sex': ['M']}), [0], 'strings'),
    (pd.DataFrame([['M', 'F']], columns=['sex', 'sex']), ['sex'], 'duplicate column'),
    ({'sex': ['M']}, ['sex'], 'DataFrame'),
])
def test_invalid_column_selection_is_rejected(df, columns, message):
    with pytest.raises(RepresentationInputError, match=message):
        analyze_representation(df, demographic_columns=columns)


def test_input_frame_is_not_mutated():
    df = pd.DataFrame({'sex': [1, 0, None, 1], 'race': ['A', 'B', 'B', None],
                       'cat': pd.Categorical(['x', 'y', 'x', 'x'])})
    before, fingerprint = df.copy(deep=True), dataset_fingerprint(df)
    analyze(df, ['sex', 'race', 'cat'], {'race': {'A': 0.5, 'B': 0.25, 'C': 0.25}})
    pd.testing.assert_frame_equal(df, before)
    assert dataset_fingerprint(df) == fingerprint


def test_results_are_deterministic_and_independent_of_row_order():
    df = pd.DataFrame({'sex': ['F', 'M', 'M', None, 'X'] * 20, 'site': list('ABCDE') * 20})
    first = analyze(df, ['sex', 'site'])
    assert analyze(df, ['sex', 'site']) == first
    shuffled = df.sample(frac=1, random_state=7)
    assert json.dumps(analyze(shuffled, ['sex', 'site'])) == json.dumps(first)


def test_runs_without_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Representation analysis must not open network connections')
    monkeypatch.setattr(socket, 'socket', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    assert analyze(pd.DataFrame({'sex': ['F', 'M']}), ['sex'])['status'] == 'descriptive_only'


def test_service_does_not_import_ui_or_ai_packages():
    code = ('import sys; sys.path.insert(0, "src"); import services.representation; '
            'loaded = {"streamlit", "ollama", "chromadb", "sentence_transformers"} & set(sys.modules); '
            'assert not loaded, loaded')
    subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True)
