"""Training-readiness evidence for a chosen outcome (experimental, swathi-al).

Pure function over the validated frame: no AI, network, file writes, or input
mutation. It describes whether a dataset is likely to cause problems for a
model (class imbalance, sparse group/outcome cells, single-feature leakage,
missingness that differs by class or group). It cannot show that a model will
work: that needs training and evaluation on held-out data.

Every flag threshold is an explicit, user-adjustable setting reported in the
result, not a clinical or regulatory standard.
"""
from collections import Counter
import math
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import mutual_info_score, roc_auc_score

from services.contracts import (
    DESCRIPTIVE_ONLY, INSUFFICIENT_EVIDENCE, PRIORITIES, REVIEW_NEEDED, SCHEMA_VERSION,
)
from services.representation import _label

READINESS_SCOPE = 'dataset_readiness'
MISSING_LABEL = '(missing)'

DEFAULT_SETTINGS = {
    'min_cell': 10,             # smallest acceptable count in a group x outcome cell
    'imbalance_share': 0.2,     # flag when the minority class share is below this
    'leakage_auc': 0.95,        # flag a numeric feature whose single-feature AUC is at least this
    'leakage_nmi': 0.9,         # flag a feature explaining this share of outcome entropy
    'redundancy_r': 0.95,       # flag numeric pairs with |Pearson r| at least this
    'missing_gap_pp': 10.0,     # flag missingness differing by this many percentage points
    'weak_signal_auc': 0.6,     # note when no single numeric feature reaches this AUC
    'projection_points': 1500,  # sampled points returned for the 2-D projection
}

LIMITATIONS = [
    'Readiness evidence describes the dataset; it does not show that a model trained on it '
    'will be accurate, fair, or clinically safe. That requires evaluation on held-out data.',
    'Flag thresholds are adjustable review settings chosen for this prototype, not clinical, '
    'statistical, or regulatory standards.',
    'Leakage checks look at one feature at a time; combinations of features can also leak.',
    'Category labels are compared exactly as recorded; no mapping is applied.',
]


class ReadinessInputError(ValueError):
    """Invalid column roles or settings."""


def _num(value, digits=6) -> Optional[float]:
    if value is None:
        return None
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def _labels(series: pd.Series) -> pd.Series:
    """Recorded categories as text, with missing values as MISSING_LABEL."""
    return series.map(lambda v: MISSING_LABEL if pd.isna(v) else _label(v))


def _kind(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return 'categorical'
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    if pd.api.types.is_numeric_dtype(series):
        return 'numeric' if series.nunique(dropna=True) > 10 else 'categorical'
    values = series.dropna().astype(str)
    if len(values) and values.str.split().str.len().mean() >= 4:
        return 'text'
    return 'categorical'


def _finding(column, code, priority, title, evidence, suggested_action) -> dict:
    return {'id': f'{column}:{code}', 'code': code, 'column': column, 'priority': priority,
            'title': title, 'evidence': evidence, 'suggested_action': suggested_action}


def apply_filters(df: pd.DataFrame, filters: Optional[Dict[str, Sequence[str]]]) -> pd.DataFrame:
    """Keep rows whose recorded label is selected for every filtered column."""
    if not filters:
        return df
    mask = pd.Series(True, index=df.index)
    for column, labels in filters.items():
        if column not in df.columns:
            raise ReadinessInputError(f'Filter column not found: {column!r}.')
        mask &= _labels(df[column]).isin([str(l) for l in labels])
    return df[mask]


def _validate(df, outcome_column, demographic_columns, identifier_columns, settings):
    if not isinstance(df, pd.DataFrame):
        raise ReadinessInputError('df must be a pandas DataFrame.')
    if df.columns.has_duplicates:
        raise ReadinessInputError('Column names must be unique.')
    named = ([outcome_column] if outcome_column else []) + list(demographic_columns) + list(identifier_columns)
    missing = [c for c in named if c not in df.columns]
    if missing:
        raise ReadinessInputError(f'Columns not found: {missing}.')
    if outcome_column and (outcome_column in demographic_columns or outcome_column in identifier_columns):
        raise ReadinessInputError('The outcome cannot also be a demographic or identifier column.')
    merged = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in DEFAULT_SETTINGS:
            raise ReadinessInputError(f'Unknown setting: {key!r}.')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ReadinessInputError(f'Setting {key!r} must be a non-negative number.')
        merged[key] = value
    return merged


def _outcome_profile(outcome: pd.Series, settings) -> dict:
    labels = _labels(outcome)
    observed = labels[labels != MISSING_LABEL]
    counts = observed.value_counts()
    total = int(len(observed))
    classes = [{'label': l, 'count': int(c), 'proportion': _num(c / total)}
               for l, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    profile = {'labeled_count': total, 'missing_count': int(len(labels) - total),
               'class_count': len(classes), 'classes': classes,
               'minority': None, 'majority': None, 'imbalance_ratio': None}
    if len(classes) >= 2:
        profile['minority'], profile['majority'] = classes[-1], classes[0]
        profile['imbalance_ratio'] = _num(classes[0]['count'] / classes[-1]['count'], 3)
    return profile


def _group_balance(df, outcome_column, column, classes, settings) -> dict:
    outcome = _labels(df[outcome_column])
    groups = _labels(df[column])
    table = pd.crosstab(groups, outcome)
    rows, smallest = [], None
    for label in sorted(table.index, key=lambda l: (-int(table.loc[l].sum()), l)):
        row = table.loc[label]
        labeled = int(sum(row.get(c, 0) for c in classes))
        cells = {c: int(row.get(c, 0)) for c in classes}
        rows.append({'label': label, 'count': int(row.sum()), 'labeled_count': labeled,
                     'missing_outcome': int(row.get(MISSING_LABEL, 0)), 'classes': cells,
                     'rates': {c: _num(n / labeled) if labeled else None for c, n in cells.items()}})
        if label == MISSING_LABEL:
            continue
        for c, n in cells.items():
            if smallest is None or n < smallest['count']:
                smallest = {'group': label, 'class': c, 'count': n}
    return {'column': column, 'groups': rows, 'smallest_cell': smallest}


def _intersections(df, outcome_column, demographics, classes, min_cell) -> List[dict]:
    result = []
    outcome = _labels(df[outcome_column])
    for i, a in enumerate(demographics):
        for b in demographics[i + 1:]:
            keys = _labels(df[a]) + ' | ' + _labels(df[b])
            table = pd.crosstab(keys, outcome)
            cells = []
            for key in sorted(table.index):
                if MISSING_LABEL in key.split(' | '):
                    continue
                row = table.loc[key]
                counts = {c: int(row.get(c, 0)) for c in classes}
                cells.append({'labels': key.split(' | '), 'count': int(sum(counts.values())),
                              'classes': counts, 'small': min(counts.values()) < min_cell})
            result.append({'columns': [a, b], 'cells': cells,
                           'small_cells': sum(c['small'] for c in cells)})
    return result


def _association(feature: pd.Series, kind: str, outcome: pd.Series, classes: List[str]) -> Optional[dict]:
    """Single-feature association with the outcome on rows where both are present."""
    labels = _labels(outcome)
    keep = (labels != MISSING_LABEL) & feature.notna()
    if keep.sum() < 2 or len(classes) < 2:
        return None
    x, y = feature[keep], labels[keep]
    if y.nunique() < 2:
        return None
    if kind == 'numeric' and len(classes) == 2:
        auc = roc_auc_score((y == classes[0]).astype(int), x.astype(float))
        return {'metric': 'auc', 'value': _num(max(auc, 1 - auc), 4), 'rows': int(keep.sum())}
    if kind == 'numeric':
        x = pd.qcut(x.astype(float), q=10, duplicates='drop').astype(str)
    else:
        x = _labels(x)
    entropy = mutual_info_score(y, y)
    nmi = mutual_info_score(y, x) / entropy if entropy > 0 else 0.0
    return {'metric': 'nmi', 'value': _num(min(nmi, 1.0), 4), 'rows': int(keep.sum())}


def _feature_profile(series: pd.Series, column: str, role: str) -> dict:
    kind = _kind(series)
    observed = series.dropna()
    distinct = int(observed.nunique())
    profile = {'column': column, 'kind': kind, 'role': role, 'dtype': str(series.dtype),
               'missing_count': int(series.isna().sum()),
               'missing_rate': _num(series.isna().mean()) if len(series) else None,
               'distinct': distinct, 'constant': distinct <= 1,
               'id_like': len(observed) >= 20 and distinct == len(observed)
               and not (kind == 'numeric' and pd.api.types.is_float_dtype(series)),
               'stats': None, 'top': None, 'association': None}
    if kind == 'numeric' and len(observed):
        values = observed.astype(float)
        profile['stats'] = {k: _num(v, 4) for k, v in {
            'min': values.min(), 'max': values.max(), 'mean': values.mean(),
            'median': values.median(), 'std': values.std(ddof=1) if len(values) > 1 else None}.items()}
    elif len(observed):
        counts = _labels(observed).value_counts()
        profile['top'] = [{'label': l, 'count': int(c)}
                          for l, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    return profile


def _distribution(series: pd.Series, kind: str, outcome: Optional[pd.Series], classes) -> Optional[dict]:
    split = _labels(outcome) if outcome is not None else pd.Series('All', index=series.index)
    keys = classes if outcome is not None else ['All']
    present = series.notna()
    if not present.any():
        return None
    if kind == 'numeric':
        values = series[present].astype(float)
        edges = np.histogram_bin_edges(values, bins=min(20, max(1, int(values.nunique()))))
        series_counts = {k: np.histogram(values[split[present] == k], bins=edges)[0].astype(int).tolist()
                         for k in keys}
        return {'kind': 'numeric', 'edges': [_num(e, 4) for e in edges], 'series': series_counts}
    if kind != 'categorical':
        return None
    labels = _labels(series[present])
    top = [l for l, _ in sorted(labels.value_counts().items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
    bucket = labels.where(labels.isin(top), 'Other')
    order = top + (['Other'] if (bucket == 'Other').any() else [])
    return {'kind': 'categorical', 'labels': order,
            'series': {k: [int(((bucket == l) & (split[present] == k)).sum()) for l in order] for k in keys}}


def _missingness(df, columns, outcome_column, demographics, classes) -> List[dict]:
    result = []
    outcome = _labels(df[outcome_column]) if outcome_column else None
    for column in columns:
        missing = df[column].isna()
        entry = {'column': column, 'overall_rate': _num(missing.mean()) if len(df) else None,
                 'by_outcome': {}, 'by_group': {}, 'max_gap_pp': None}
        rates = []
        if outcome is not None:
            for c in classes:
                part = missing[outcome == c]
                entry['by_outcome'][c] = _num(part.mean()) if len(part) else None
                rates += [entry['by_outcome'][c]] if len(part) else []
        for group in demographics:
            if group == column:
                continue
            labels = _labels(df[group])
            entry['by_group'][group] = {}
            for label in sorted(labels.unique()):
                if label == MISSING_LABEL:
                    continue
                part = missing[labels == label]
                entry['by_group'][group][label] = _num(part.mean())
                rates.append(entry['by_group'][group][label])
        rates = [r for r in rates if r is not None]
        if rates and missing.any():
            entry['max_gap_pp'] = _num((max(rates) - min(rates)) * 100, 2)
        result.append(entry)
    return result


def _correlations(df, numeric_columns, threshold) -> dict:
    columns = numeric_columns[:30]
    if len(columns) < 2:
        return {'columns': columns, 'matrix': [], 'redundant_pairs': []}
    matrix = df[columns].astype(float).corr(method='pearson')
    values = [[_num(matrix.iloc[i, j], 4) for j in range(len(columns))] for i in range(len(columns))]
    pairs = [{'a': columns[i], 'b': columns[j], 'r': values[i][j]}
             for i in range(len(columns)) for j in range(i + 1, len(columns))
             if values[i][j] is not None and abs(values[i][j]) >= threshold]
    return {'columns': columns, 'matrix': values, 'redundant_pairs': pairs}


def _projection(df, numeric_columns, outcome_column, limit) -> dict:
    if len(numeric_columns) < 2 or len(df) < 3:
        return {'method': 'PCA', 'points': [], 'reason': 'Needs at least two numeric features and three rows.'}
    frame = df[numeric_columns].astype(float)
    frame = frame.fillna(frame.median()).fillna(0.0)
    std = frame.std(ddof=0).replace(0, 1.0)
    scaled = (frame - frame.mean()) / std
    sample = scaled.sample(n=min(int(limit), len(scaled)), random_state=0) if len(scaled) > limit else scaled
    model = PCA(n_components=2, random_state=0).fit(scaled)
    coords = model.transform(sample)
    labels = _labels(df.loc[sample.index, outcome_column]) if outcome_column else pd.Series('All', index=sample.index)
    return {'method': 'PCA', 'features': numeric_columns,
            'explained_variance': [_num(v, 4) for v in model.explained_variance_ratio_],
            'points': [{'x': _num(x, 4), 'y': _num(y, 4), 'label': l, 'row': int(i) if isinstance(i, (int, np.integer)) else str(i)}
                       for (x, y), l, i in zip(coords, labels, sample.index)],
            'sampled': int(len(sample)), 'total': int(len(df)),
            'note': 'Missing values are filled with column medians for this view only; the data is unchanged.'}


def analyze_readiness(df: pd.DataFrame, *, outcome_column: Optional[str],
                      demographic_columns: Sequence[str] = (), identifier_columns: Sequence[str] = (),
                      settings: Optional[dict] = None) -> dict:
    """Describe training-readiness signals for the chosen outcome and groups."""
    settings = _validate(df, outcome_column, demographic_columns, identifier_columns, settings)
    demographics = list(dict.fromkeys(demographic_columns))
    identifiers = set(identifier_columns)
    roles = {c: 'demographic' for c in demographics}
    roles.update({c: 'identifier' for c in identifiers})
    if outcome_column:
        roles[outcome_column] = 'outcome'

    outcome = _outcome_profile(df[outcome_column], settings) if outcome_column else None
    classes = [c['label'] for c in outcome['classes']] if outcome else []
    findings = []

    if outcome:
        if outcome['missing_count']:
            findings.append(_finding(outcome_column, 'missing_outcome_labels', 'medium',
                                     'Some rows have no outcome label',
                                     {'missing_count': outcome['missing_count'], 'row_count': int(len(df))},
                                     'Unlabeled rows cannot be used for supervised training; check why labels are missing.'))
        if outcome['class_count'] == 1:
            findings.append(_finding(outcome_column, 'single_class', 'high', 'Only one outcome class is present',
                                     {'class': classes[0], 'count': outcome['classes'][0]['count']},
                                     'A classifier cannot learn from one class; check the outcome column and cohort.'))
        if outcome['minority']:
            minority = outcome['minority']
            if minority['proportion'] < settings['imbalance_share']:
                findings.append(_finding(outcome_column, 'class_imbalance', 'high', 'Outcome classes are imbalanced',
                                         {'minority_class': minority['label'], 'minority_share': minority['proportion'],
                                          'imbalance_ratio': outcome['imbalance_ratio'],
                                          'setting_imbalance_share': settings['imbalance_share']},
                                         'Plan evaluation metrics and validation that account for the minority class.'))
            if minority['count'] < settings['min_cell']:
                findings.append(_finding(outcome_column, 'minority_class_small', 'high',
                                         'Very few examples of the minority class',
                                         {'minority_class': minority['label'], 'count': minority['count'],
                                          'setting_min_cell': settings['min_cell']},
                                         'Consider whether more labeled cases are needed before training.'))

    group_balance, intersections = [], []
    if outcome and len(classes) >= 2:
        for column in demographics:
            entry = _group_balance(df, outcome_column, column, classes, settings)
            group_balance.append(entry)
            small = [{'group': g['label'], 'class': c, 'count': n}
                     for g in entry['groups'] if g['label'] != MISSING_LABEL
                     for c, n in g['classes'].items() if n < settings['min_cell']]
            if small:
                findings.append(_finding(column, 'small_group_outcome_cells', 'high',
                                         'Some groups have very few cases of an outcome class',
                                         {'cells': small[:20], 'cell_count': len(small),
                                          'setting_min_cell': settings['min_cell']},
                                         'A model may learn little about these groups; review coverage before training.'))
        intersections = _intersections(df, outcome_column, demographics, classes, settings['min_cell'])
        for entry in intersections:
            if entry['small_cells']:
                name = ' x '.join(entry['columns'])
                findings.append(_finding(name, 'small_intersection_cells', 'medium',
                                         'Some combined groups have very few cases',
                                         {'small_cells': entry['small_cells'], 'cells': len(entry['cells']),
                                          'setting_min_cell': settings['min_cell']},
                                         'Check coverage for these combinations before reporting subgroup results.'))

    features, numeric = [], []
    for column in df.columns:
        role = roles.get(column, 'feature')
        profile = _feature_profile(df[column], str(column), role)
        if role == 'feature' and outcome and not profile['id_like'] and not profile['constant'] \
                and profile['kind'] in ('numeric', 'categorical'):
            if profile['kind'] == 'numeric' or profile['distinct'] <= max(50, len(df) // 2):
                profile['association'] = _association(df[column], profile['kind'], df[outcome_column], classes)
        if role == 'feature' and profile['kind'] == 'numeric' and not profile['constant'] and not profile['id_like']:
            numeric.append(str(column))
        features.append(profile)
        if role != 'feature':
            continue
        if profile['constant']:
            findings.append(_finding(column, 'constant_feature', 'low', 'Feature has one value',
                                     {'distinct': profile['distinct']}, 'A constant feature carries no information; consider dropping it.'))
        if profile['id_like']:
            findings.append(_finding(column, 'id_like_feature', 'medium', 'Feature has a distinct value in every row',
                                     {'distinct': profile['distinct']},
                                     'If this is an identifier, mark it as one; models can memorize IDs.'))
        assoc = profile['association']
        if assoc and ((assoc['metric'] == 'auc' and assoc['value'] >= settings['leakage_auc'])
                      or (assoc['metric'] == 'nmi' and assoc['value'] >= settings['leakage_nmi'])):
            findings.append(_finding(column, 'possible_leakage', 'high',
                                     'Feature almost determines the outcome on its own',
                                     {'metric': assoc['metric'], 'value': assoc['value'],
                                      'setting': settings['leakage_auc' if assoc['metric'] == 'auc' else 'leakage_nmi']},
                                     'Check whether this feature is recorded after, or because of, the outcome.'))

    rank = sorted(({'column': f['column'], **f['association']} for f in features if f['association']),
                  key=lambda r: (-r['value'], r['column']))
    auc_scores = [r['value'] for r in rank if r['metric'] == 'auc']
    nmi_scores = [r['value'] for r in rank if r['metric'] == 'nmi']
    if rank and (not auc_scores or max(auc_scores) < settings['weak_signal_auc']) \
            and (not nmi_scores or max(nmi_scores) < 0.05):
        findings.append(_finding(outcome_column, 'weak_single_feature_signal', 'medium',
                                 'No single feature separates the outcome well',
                                 {'best_auc': max(auc_scores) if auc_scores else None,
                                  'best_nmi': max(nmi_scores) if nmi_scores else None,
                                  'setting_weak_signal_auc': settings['weak_signal_auc']},
                                 'Features may carry little information about this outcome on their own; '
                                 'combinations are not assessed here. Check the outcome definition and features.'))
    missingness = _missingness(df, [c for c in df.columns if df[c].isna().any() and c != outcome_column],
                               outcome_column, demographics, classes)
    for entry in missingness:
        if entry['max_gap_pp'] is not None and entry['max_gap_pp'] >= settings['missing_gap_pp']:
            findings.append(_finding(entry['column'], 'missingness_differs', 'medium',
                                     'Missing values are more common in some classes or groups',
                                     {'max_gap_pp': entry['max_gap_pp'], 'setting_missing_gap_pp': settings['missing_gap_pp']},
                                     'Values may be missing for a reason; avoid simple imputation without review.'))
    correlations = _correlations(df, numeric, settings['redundancy_r'])
    for pair in correlations['redundant_pairs']:
        findings.append(_finding(f"{pair['a']} ~ {pair['b']}", 'redundant_features', 'low',
                                 'Two features are almost perfectly correlated',
                                 {'r': pair['r'], 'setting_redundancy_r': settings['redundancy_r']},
                                 'Consider whether both are needed; they may record the same thing.'))

    distributions = {}
    for profile in features:
        if profile['role'] in ('feature', 'demographic'):
            dist = _distribution(df[profile['column']], profile['kind'],
                                 df[outcome_column] if outcome else None, classes)
            if dist:
                distributions[profile['column']] = dist

    findings.sort(key=lambda f: PRIORITIES.index(f['priority']))
    if not outcome or outcome['labeled_count'] == 0:
        status = INSUFFICIENT_EVIDENCE
    elif findings and any(f['priority'] in ('high', 'medium') for f in findings):
        status = REVIEW_NEEDED
    else:
        status = DESCRIPTIVE_ONLY
    candidate_features = [f for f in features if f['role'] == 'feature' and not f['constant'] and not f['id_like']]
    limitations = list(LIMITATIONS)
    if not outcome_column:
        limitations.append('No outcome column was selected, so class balance and leakage were not assessed.')
    return {
        'schema_version': SCHEMA_VERSION,
        'scope': READINESS_SCOPE,
        'status': status,
        'row_count': int(len(df)),
        'settings': settings,
        'roles': {'outcome': outcome_column, 'demographics': demographics, 'identifiers': sorted(identifiers)},
        'outcome': outcome,
        'cases_per_feature': (_num(outcome['minority']['count'] / len(candidate_features), 2)
                              if outcome and outcome['minority'] and candidate_features else None),
        'group_balance': group_balance,
        'intersections': intersections,
        'features': features,
        'rank': rank,
        'missingness': missingness,
        'correlations': correlations,
        'distributions': distributions,
        'projection': _projection(df, numeric, outcome_column, settings['projection_points']),
        'findings': findings,
        'limitations': limitations,
    }
