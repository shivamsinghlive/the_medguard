"""Source-preserving preview of allowlisted cleaning actions.

Pure function: the input frame is never modified, and no AI, network, or file
writes are involved. Actions run in order on a separate copy. Resampling,
synthetic records (such as SMOTE), and demographic balancing are deliberately
not available. A preview shows what a change does to the records; it does not
show that the change improves accuracy or fairness.
"""
from collections.abc import Mapping
import math
import numbers
from typing import Dict, List, Sequence

import pandas as pd

from services.contracts import (
    ALLOWED_ACTIONS, APPLIED, BLOCKED, COLUMN_ROLES, NOT_RUN, PREVIEW_BLOCKED, PREVIEW_READY,
    PREVIEW_SCOPE, PROTECTED_ROLES, SCHEMA_VERSION, ChangePreviewError,
)
from services.representation import analyze_representation
from utils.audit_input import dataset_fingerprint

_FIELDS = {
    'drop_duplicate_rows': (set(), set()),
    'drop_rows_with_missing': ({'columns'}, set()),
    'fill_missing': ({'column', 'method'}, {'value'}),
    'strip_whitespace': ({'column'}, set()),
    'drop_column': ({'column'}, set()),
}  # action -> (required fields, optional fields); 'action'/'allow_protected' always allowed

LIMITATIONS = [
    'A preview shows what a change does to the records; it does not show that the change '
    'improves model accuracy or fairness. That requires evaluation on untouched held-out data.',
    'The source dataset is not modified. Changes apply to a separate copy whose row index '
    'labels refer to source rows.',
    'Resampling, synthetic records (such as SMOTE), and demographic balancing are not '
    'available in this release.',
]


class _Blocked(Exception):
    pass


def _changed_cells(before: pd.Series, after: pd.Series) -> int:
    same = (before == after) | (before.isna() & after.isna())
    return int((~same).sum())


def _demographic_counts(df: pd.DataFrame, columns: List[str]) -> Dict[str, dict]:
    present = [c for c in columns if c in df.columns]
    result = analyze_representation(df, demographic_columns=present)
    return {a['column']: {'observed_count': a['observed_count'], 'missing_count': a['missing_count'],
                          'counts': {g['label']: g['count'] for g in a['groups']}}
            for a in result['attributes']}


def _column(spec, work) -> str:
    column = spec['column']
    if not isinstance(column, str) or column not in work.columns:
        raise _Blocked(f'Column {column!r} is not in the dataset.')
    return column


def _parse(spec, work):
    """Validate one action; return (name, referenced columns)."""
    name = spec.get('action')
    if name not in ALLOWED_ACTIONS:
        raise _Blocked(f'Action {name!r} is not in the allowlist {list(ALLOWED_ACTIONS)}. '
                       'Resampling and demographic balancing are not supported.')
    required, optional = _FIELDS[name]
    missing = sorted(required - set(spec))
    unexpected = sorted(set(spec) - required - optional - {'action', 'allow_protected'})
    if missing or unexpected:
        raise _Blocked(f'{name} needs fields {sorted(required)}; missing {missing}, unexpected {unexpected}.')
    if not isinstance(spec.get('allow_protected', False), bool):
        raise _Blocked('allow_protected must be true or false.')
    if name == 'drop_duplicate_rows':
        return name, []
    if name == 'drop_rows_with_missing':
        columns = spec['columns']
        if isinstance(columns, str) or not isinstance(columns, Sequence) or not columns:
            raise _Blocked('drop_rows_with_missing needs a non-empty list of columns.')
        for column in columns:
            _column({'column': column}, work)
        return name, list(dict.fromkeys(columns))
    return name, [_column(spec, work)]


def _fill_value(spec, series: pd.Series):
    method = spec['method']
    numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    if method == 'median':
        if 'value' in spec:
            raise _Blocked('Median fill computes its value; do not supply one.')
        if not numeric:
            raise _Blocked('Median fill needs a numeric column.')
        if series.notna().sum() == 0:
            raise _Blocked('Median fill needs at least one observed value.')
        return float(series.median())
    if method == 'constant':
        if 'value' not in spec:
            raise _Blocked('Constant fill needs a value.')
        value = spec['value']
        if numeric:
            if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
                raise _Blocked('Constant fill for a numeric column needs a finite number.')
        elif not isinstance(value, str):
            raise _Blocked('Constant fill for a text column needs text.')
        return value
    raise _Blocked(f'Fill method {method!r} is not supported; use "median" or "constant".')


def _apply(name, spec, columns, work):
    """Return (new frame, evidence, warnings) for one validated action."""
    if name == 'drop_duplicate_rows':
        out = work[~work.duplicated(keep='first')]
        return out, {'rows_removed': len(work) - len(out)}, []
    if name == 'drop_rows_with_missing':
        out = work[~work[columns].isna().any(axis=1)]
        return out, {'rows_removed': len(work) - len(out)}, []
    column = columns[0]
    series = work[column]
    if name == 'drop_column':
        return work.drop(columns=[column]), {'non_missing_values_removed': int(series.notna().sum())}, []
    out = work.copy()
    if name == 'fill_missing':
        value = _fill_value(spec, series)
        out[column] = series.fillna(value)
        warnings = (['Median fill can hide why values were missing and reduces variability.']
                    if spec['method'] == 'median' else [])
        return out, {'method': spec['method'], 'fill_value': value,
                     'cells_changed': _changed_cells(series, out[column])}, warnings
    # strip_whitespace
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        raise _Blocked('strip_whitespace needs a text column.')
    out[column] = series.map(lambda v: v.strip() if isinstance(v, str) else v)
    return out, {'cells_changed': _changed_cells(series, out[column]),
                 'distinct_values_before': int(series.nunique()),
                 'distinct_values_after': int(out[column].nunique())}, []


def _validate_request(df, actions, column_roles):
    if not isinstance(df, pd.DataFrame):
        raise ChangePreviewError('df must be a pandas DataFrame.')
    if df.columns.has_duplicates:
        raise ChangePreviewError('Column names must be unique.')
    if isinstance(actions, (str, bytes, Mapping)) or not isinstance(actions, Sequence) \
            or not all(isinstance(a, Mapping) for a in actions):
        raise ChangePreviewError('actions must be a list of action mappings.')
    if not isinstance(column_roles, Mapping):
        raise ChangePreviewError('column_roles must map column names to roles.')
    for column, role in column_roles.items():
        if column not in df.columns:
            raise ChangePreviewError(f'Role assigned to unknown column {column!r}.')
        if role not in COLUMN_ROLES:
            raise ChangePreviewError(f'Role {role!r} for {column!r} must be one of {list(COLUMN_ROLES)}.')


def preview_changes(df: pd.DataFrame, actions: Sequence[Mapping], *,
                    column_roles: Mapping[str, str]) -> tuple:
    """Preview allowlisted actions; return (PreviewResult, output frame or None).

    column_roles is required (it may be empty); columns without a role are
    unassigned and not protected. Raises ChangePreviewError for a malformed
    request; problems with individual actions are reported as blocked.
    """
    _validate_request(df, actions, column_roles)
    source_fingerprint = dataset_fingerprint(df)
    demographics = [c for c, r in column_roles.items() if r == 'demographic']

    work, results, blocked = df.copy(deep=True), [], False
    for index, spec in enumerate(actions):
        entry = {'index': index, 'action': str(spec.get('action')), 'columns': [],
                 'status': NOT_RUN, 'reason': None, 'evidence': {}, 'warnings': []}
        results.append(entry)
        if blocked:
            continue
        try:
            name, columns = _parse(spec, work)
            entry['columns'] = columns
            protected = [c for c in columns if column_roles.get(c) in PROTECTED_ROLES]
            if protected and not spec.get('allow_protected', False):
                raise _Blocked('Protected roles are not changed by default: ' + ', '.join(
                    f'{c} ({column_roles[c]})' for c in protected) + '. Set allow_protected to override.')
            try:
                out, evidence, warnings = _apply(name, spec, columns, work)
            except (TypeError, ValueError) as exc:
                raise _Blocked(f'The action could not be applied: {exc}')
            changed = [c for c in out.columns if out[c].dtype != work[c].dtype]
            if changed:
                raise _Blocked(f'The action would change column types: {changed}.')
        except _Blocked as exc:
            entry.update(status=BLOCKED, reason=str(exc))
            blocked = True
            continue
        entry['warnings'] += [f'Protected-role override for {c} ({column_roles[c]}).' for c in protected]
        entry['warnings'] += [f'Column {c} has no assigned role.' for c in columns if c not in column_roles]
        entry['warnings'] += warnings
        entry.update(status=APPLIED, evidence=evidence)
        work = out

    if dataset_fingerprint(df) != source_fingerprint:
        raise RuntimeError('Change preview modified the source dataset.')

    limitations = list(LIMITATIONS)
    if not demographics:
        limitations.append('No demographic columns were assigned, so cohort count changes are not shown.')
    result = {
        'schema_version': SCHEMA_VERSION,
        'scope': PREVIEW_SCOPE,
        'status': PREVIEW_BLOCKED if blocked else PREVIEW_READY,
        'actions': results,
        'before': {'row_count': int(len(df)), 'column_count': int(len(df.columns)),
                   'demographic_counts': _demographic_counts(df, demographics)},
        'after': None,
        'schema': None,
        'source_fingerprint': source_fingerprint,
        'output_fingerprint': None,
        'limitations': limitations,
    }
    if blocked:
        return result, None
    removed = [str(c) for c in df.columns if c not in work.columns]
    result['after'] = {'row_count': int(len(work)), 'column_count': int(len(work.columns)),
                       'demographic_counts': _demographic_counts(work, demographics)}
    result['schema'] = {'columns_removed': removed, 'dtype_changes': [],
                        'column_order_preserved': list(work.columns) == [c for c in df.columns if c in work.columns],
                        'preserved': not removed}
    result['output_fingerprint'] = dataset_fingerprint(work)
    return result, work
