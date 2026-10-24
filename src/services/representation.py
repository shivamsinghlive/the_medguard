"""Descriptive representation evidence for explicitly selected columns.

Pure function: no AI, network, file writes, Streamlit state, or mutation of
the input frame. It reports counts and proportions; it never certifies a
dataset as fair and never infers harm from representation.
"""
from collections import Counter
from collections.abc import Mapping
import math
import numbers
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from services.contracts import (
    DESCRIPTIVE_ONLY, INSUFFICIENT_EVIDENCE, PRIORITIES, REPRESENTATION_SCOPE,
    REVIEW_NEEDED, SCHEMA_VERSION, RepresentationInputError, overall_status,
)

_SUM_TOLERANCE = 1e-6


def _label(value) -> str:
    """Keep recorded categories as text; 1 and 1.0 (from a column with
    missing values) are the same recorded code. No meaning is assigned."""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (numbers.Integral, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def _validate_columns(df, demographic_columns) -> List[str]:
    if not isinstance(df, pd.DataFrame):
        raise RepresentationInputError('df must be a pandas DataFrame.')
    if isinstance(demographic_columns, (str, bytes)) or not isinstance(demographic_columns, Sequence):
        raise RepresentationInputError('demographic_columns must be a list of column names.')
    columns = list(demographic_columns)
    if not all(isinstance(c, str) for c in columns):
        raise RepresentationInputError('Column names must be strings.')
    repeated = sorted(c for c, n in Counter(columns).items() if n > 1)
    if repeated:
        raise RepresentationInputError(f'Columns selected more than once: {repeated}.')
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise RepresentationInputError(f'Selected columns not found in the dataset: {missing}.')
    ambiguous = [c for c in columns if int((df.columns == c).sum()) > 1]
    if ambiguous:
        raise RepresentationInputError(f'Dataset has duplicate column names: {ambiguous}.')
    return columns


def _validate_reference(reference_proportions, columns) -> Dict[str, Dict[str, float]]:
    if reference_proportions is None:
        return {}
    if not isinstance(reference_proportions, Mapping):
        raise RepresentationInputError('reference_proportions must map column names to proportions.')
    references = {}
    for column, proportions in reference_proportions.items():
        if column not in columns:
            raise RepresentationInputError(f'Reference supplied for unselected column: {column!r}.')
        if not isinstance(proportions, Mapping) or not proportions:
            raise RepresentationInputError(f'Reference for {column!r} must be a non-empty mapping.')
        reference = {}
        for category, value in proportions.items():
            if isinstance(value, bool) or not isinstance(value, numbers.Real) \
                    or not math.isfinite(value) or not 0 <= value <= 1:
                raise RepresentationInputError(
                    f'Reference proportion for {column!r}/{category!r} must be a number in [0, 1].')
            label = _label(category)
            if label in reference:
                raise RepresentationInputError(f'Reference for {column!r} repeats category {label!r}.')
            reference[label] = float(value)
        total = math.fsum(reference.values())
        if abs(total - 1) > _SUM_TOLERANCE:
            raise RepresentationInputError(f'Reference for {column!r} sums to {total:g}, not 1.')
        references[column] = reference
    return references


def _finding(column, code, priority, title, evidence, suggested_action) -> dict:
    return {'id': f'{column}:{code}', 'code': code, 'column': column, 'priority': priority,
            'title': title, 'evidence': evidence, 'suggested_action': suggested_action}


def _analyze_column(series: pd.Series, column: str, reference: Optional[Dict[str, float]]):
    missing_count = int(series.isna().sum())
    observed_count = int(len(series) - missing_count)
    counts = Counter()
    for value, n in series.dropna().value_counts(sort=False).items():
        if n:  # categorical dtypes also list unused categories
            counts[_label(value)] += int(n)

    labels = set(counts) | set(reference or ())
    groups = []
    for label in labels:
        count = counts.get(label, 0)
        proportion = count / observed_count if observed_count else None
        ref = reference.get(label) if reference is not None else None
        difference = None
        if proportion is not None and ref is not None:
            difference = round((proportion - ref) * 100, 6) + 0.0  # drops -0.0
        groups.append({'label': label, 'count': count, 'proportion': proportion,
                       'reference_proportion': ref, 'difference_pp': difference})
    groups.sort(key=lambda g: (-g['count'], g['label']))

    findings = []
    if observed_count == 0:
        findings.append(_finding(
            column, 'no_observed_values', 'high', 'No values are recorded',
            {'row_count': int(len(series)), 'missing_count': missing_count},
            'Check the column selection and data extraction.'))
        status = INSUFFICIENT_EVIDENCE
    else:
        if len(counts) == 1:
            findings.append(_finding(
                column, 'single_group', 'high', 'Only one group is observed',
                {'observed_group_count': 1, 'observed_count': observed_count},
                'Review intended population coverage.'))
        if reference is not None:
            absent = sorted(l for l, p in reference.items() if p > 0 and counts.get(l, 0) == 0)
            if absent:
                findings.append(_finding(
                    column, 'missing_reference_group', 'high',
                    'Expected groups have no observed rows',
                    {'missing_groups': absent,
                     'reference_proportions': {l: reference[l] for l in absent}},
                    'Check whether these groups should be present or category labels need mapping.'))
            outside = sorted(l for l in counts if l not in reference)
            if outside:
                findings.append(_finding(
                    column, 'group_not_in_reference', 'medium',
                    'Observed groups are not in the supplied reference',
                    {'groups': outside, 'count': sum(counts[l] for l in outside)},
                    'Check category labels and the reference population.'))
        status = REVIEW_NEEDED if findings else DESCRIPTIVE_ONLY

    attribute = {'column': column, 'status': status, 'observed_count': observed_count,
                 'missing_count': missing_count, 'groups': groups}
    return attribute, findings


def _limitations(columns, references, row_count) -> List[str]:
    limitations = ['Representation does not measure model fairness or clinical harm.']
    if references:
        limitations.append('The reference population was supplied by the user.')
    if not columns:
        limitations.append('No demographic columns were selected, so representation was not assessed.')
        return limitations
    if row_count == 0:
        limitations.append('The dataset has no rows.')
    unreferenced = [c for c in columns if c not in references]
    if unreferenced:
        limitations.append(f'No reference population was supplied for {", ".join(unreferenced)}; '
                           'those proportions are descriptive only.')
    limitations += [
        'Proportions use non-missing values as the denominator; missing values are counted separately.',
        'Category labels are compared exactly as recorded; no mapping was applied, '
        'so numeric codes are not assumed to mean any group.',
        'No uncertainty intervals, thresholds, or intersectional groups are calculated in this version.',
    ]
    return limitations


def analyze_representation(df: pd.DataFrame, *, demographic_columns: Sequence[str],
                           reference_proportions: Optional[Mapping] = None) -> dict:
    """Describe group counts, missingness, and optional reference differences.

    Raises RepresentationInputError for unknown columns or invalid references.
    """
    columns = _validate_columns(df, demographic_columns)
    references = _validate_reference(reference_proportions, columns)

    attributes, findings = [], []
    for column in columns:
        attribute, column_findings = _analyze_column(df[column], column, references.get(column))
        attributes.append(attribute)
        findings += column_findings
    findings.sort(key=lambda f: PRIORITIES.index(f['priority']))  # stable: keeps column order

    return {
        'schema_version': SCHEMA_VERSION,
        'scope': REPRESENTATION_SCOPE,
        'status': overall_status([a['status'] for a in attributes]),
        'row_count': int(len(df)),
        'attributes': attributes,
        'findings': findings,
        'limitations': _limitations(columns, references, len(df)),
    }
