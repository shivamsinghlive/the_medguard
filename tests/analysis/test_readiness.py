"""Readiness service (swathi-al): class balance, group cells, leakage, missingness."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.readiness import ReadinessInputError, analyze_readiness, apply_filters
from utils.audit_input import dataset_fingerprint


def run(df, outcome='y', demographics=(), identifiers=(), **settings):
    result = analyze_readiness(df, outcome_column=outcome, demographic_columns=list(demographics),
                               identifier_columns=list(identifiers), settings=settings or None)
    json.dumps(result, allow_nan=False)
    return result


def codes(result):
    return {f['code'] for f in result['findings']}


def frame(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({'y': rng.integers(0, 2, n), 'sex': rng.choice(['F', 'M'], n),
                         'race': rng.choice(['A', 'B', 'C'], n), 'age': rng.normal(50, 10, n).round(1),
                         'bp': rng.normal(120, 15, n).round(1)})


def test_class_imbalance_is_measured_and_flagged():
    df = pd.DataFrame({'y': [0] * 90 + [1] * 10, 'x': range(100)})
    r = run(df)
    o = r['outcome']
    assert (o['labeled_count'], o['class_count'], o['minority'], o['imbalance_ratio']) == (
        100, 2, {'label': '1', 'count': 10, 'proportion': 0.1}, 9.0)
    assert 'class_imbalance' in codes(r)
    assert 'class_imbalance' not in codes(run(df, imbalance_share=0.05))


def test_single_class_and_missing_labels():
    r = run(pd.DataFrame({'y': [1, 1, None, 1], 'x': [1, 2, 3, 4]}))
    assert r['outcome']['missing_count'] == 1 and r['outcome']['minority'] is None
    assert {'single_class', 'missing_outcome_labels'} <= codes(r)


def test_group_outcome_cells_flag_groups_without_cases():
    df = pd.DataFrame({'y': [1] * 30 + [0] * 30 + [0] * 20, 'sex': ['M'] * 60 + ['F'] * 20, 'x': range(80)})
    r = run(df, demographics=['sex'])
    f = next(f for f in r['findings'] if f['code'] == 'small_group_outcome_cells')
    assert {'group': 'F', 'class': '1', 'count': 0} in f['evidence']['cells']
    female = next(g for g in r['group_balance'][0]['groups'] if g['label'] == 'F')
    assert female['classes'] == {'0': 50 - 30, '1': 0} or female['classes'] == {'0': 20, '1': 0}
    assert r['group_balance'][0]['smallest_cell'] == {'group': 'F', 'class': '1', 'count': 0}


def test_intersections_report_small_combined_cells():
    r = run(frame(), demographics=['sex', 'race'], min_cell=30)
    inter = r['intersections'][0]
    assert inter['columns'] == ['sex', 'race'] and len(inter['cells']) == 6
    assert inter['small_cells'] == sum(c['small'] for c in inter['cells']) > 0
    assert 'small_intersection_cells' in codes(r)


def test_leakage_numeric_and_categorical_copies_are_flagged():
    df = frame()
    df['score_after'] = df['y'] * 10 + np.random.default_rng(1).normal(0, 0.1, len(df))
    df['status_after'] = df['y'].map({0: 'alive', 1: 'dead'})
    r = run(df)
    leaks = {f['column']: f['evidence'] for f in r['findings'] if f['code'] == 'possible_leakage'}
    assert leaks['score_after']['metric'] == 'auc' and leaks['score_after']['value'] == 1.0
    assert leaks['status_after']['metric'] == 'nmi' and leaks['status_after']['value'] == 1.0
    assert 'age' not in leaks and r['rank'][0]['column'] in leaks


def test_random_features_give_weak_signal_note():
    r = run(frame(400))
    assert 'weak_single_feature_signal' in codes(r)
    assert all(x['value'] < 0.6 for x in r['rank'] if x['metric'] == 'auc')


def test_identifiers_and_demographics_are_not_scored_as_features():
    df = frame()
    df['pid'] = [f'P{i}' for i in range(len(df))]
    r = run(df, demographics=['sex'], identifiers=['pid'])
    scored = {x['column'] for x in r['rank']}
    assert not {'pid', 'sex', 'y'} & scored
    assert 'id_like_feature' not in codes(r)
    assert 'id_like_feature' in codes(run(df))


def test_constant_redundant_and_missingness_gap():
    df = frame()
    df['const'] = 1
    df['bp_copy'] = df['bp'] * 2
    df['lab'] = np.where(df['y'] == 1, np.nan, 5.0)
    r = run(df)
    assert {'constant_feature', 'redundant_features', 'missingness_differs'} <= codes(r)
    lab = next(m for m in r['missingness'] if m['column'] == 'lab')
    assert lab['by_outcome'] == {'0': 0.0, '1': 1.0} or set(lab['by_outcome'].values()) == {0.0, 1.0}
    assert lab['max_gap_pp'] == 100.0


def test_distributions_and_projection_are_computed_from_data():
    df = frame()
    r = run(df)
    age = r['distributions']['age']
    assert age['kind'] == 'numeric' and sum(sum(v) for v in age['series'].values()) == df['age'].notna().sum()
    sex = r['distributions']['sex']
    assert sex['labels'] == ['F', 'M'] or sex['labels'] == ['M', 'F']
    assert sum(sum(v) for v in sex['series'].values()) == len(df)
    p = r['projection']
    assert len(p['points']) == len(df) and len(p['explained_variance']) == 2


def test_without_outcome_is_insufficient_but_profiles_columns():
    r = run(frame(), outcome=None)
    assert r['status'] == 'insufficient_evidence' and r['outcome'] is None
    assert r['rank'] == [] and r['group_balance'] == []
    assert list(r['distributions']['age']['series']) == ['All']


def test_filters_select_recorded_labels_including_missing():
    df = pd.DataFrame({'sex': ['F', 'M', None, 'F'], 'y': [1, 0, 1, 0]})
    assert list(apply_filters(df, {'sex': ['F']}).index) == [0, 3]
    assert list(apply_filters(df, {'sex': ['(missing)'], 'y': ['1']}).index) == [2]
    with pytest.raises(ReadinessInputError):
        apply_filters(df, {'nope': ['x']})


@pytest.mark.parametrize('kwargs,message', [
    ({'outcome_column': 'missing'}, 'not found'),
    ({'outcome_column': 'y', 'demographic_columns': ['y']}, 'cannot also be'),
    ({'outcome_column': 'y', 'settings': {'min_cell': -1}}, 'non-negative'),
    ({'outcome_column': 'y', 'settings': {'unknown': 1}}, 'Unknown setting'),
])
def test_invalid_requests_raise(kwargs, message):
    with pytest.raises(ReadinessInputError, match=message):
        analyze_readiness(frame(), **kwargs)


def test_input_not_mutated_and_deterministic():
    df = frame()
    before, fp = df.copy(deep=True), dataset_fingerprint(df)
    first = run(df, demographics=['sex', 'race'])
    assert run(df, demographics=['sex', 'race']) == first
    pd.testing.assert_frame_equal(df, before)
    assert dataset_fingerprint(df) == fp
