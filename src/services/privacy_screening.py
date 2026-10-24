"""Heuristic screening for potential identifiers.

Pure function: no AI, network, file writes, or input mutation. It reports
where patterns matched, with counts but never the matched values. Finding
nothing is not de-identification: HIPAA de-identification requires Safe
Harbor or Expert Determination, which these heuristics do not establish.
"""
import re
from typing import List, Optional

import pandas as pd

from services.contracts import (
    INSUFFICIENT_EVIDENCE, NO_PATTERNS_FOUND, PRIORITIES, REVIEW_NEEDED,
    SCHEMA_VERSION, SCREENING_SCOPE,
)

DEFAULT_MAX_ROWS = 200_000
FREE_TEXT_WORDS = 8
UNIQUE_MIN_ROWS = 20

_PERSON_QUALIFIERS = {
    'patient', 'first', 'last', 'full', 'middle', 'given', 'family', 'maiden', 'person',
    'member', 'subscriber', 'guardian', 'contact', 'mother', 'father', 'emergency',
    'doctor', 'physician', 'provider', 'nurse',
}
_NUMBER_WORDS = {'number', 'no', 'num', 'nbr', 'id', 'code'}

# (kind, priority, test on column-name tokens); first match wins.
_NAME_RULES = [
    ('email', 'high', lambda t: 'email' in t or {'e', 'mail'} <= t),
    ('ip_address', 'medium', lambda t: 'ip' in t),
    ('ssn', 'high', lambda t: 'ssn' in t or {'social', 'security'} <= t),
    ('medical_record_number', 'high', lambda t: 'mrn' in t or {'medical', 'record'} <= t),
    ('person_name', 'high', lambda t: bool(t & {'surname', 'firstname', 'lastname', 'fullname', 'forename'})
     or ('name' in t and (len(t) == 1 or bool(t & _PERSON_QUALIFIERS)))),
    ('phone', 'high', lambda t: bool(t & {'phone', 'telephone', 'fax', 'mobile', 'cellphone'})),
    ('address', 'high', lambda t: bool(t & {'address', 'street'})),
    ('postal_code', 'high', lambda t: bool(t & {'zip', 'zipcode', 'postcode', 'postal'})),
    ('birth_date', 'high', lambda t: bool(t & {'dob', 'birthdate', 'birthday'})
     or ('birth' in t and bool(t & {'date', 'day', 'dt'}))),
    ('identifier_number', 'high', lambda t: bool(t & {'vin', 'serial', 'beneficiary'})
     or (bool(t & {'account', 'policy', 'license', 'licence', 'insurance', 'member', 'device'})
         and bool(t & _NUMBER_WORDS))),
    ('url', 'medium', lambda t: bool(t & {'url', 'website', 'webpage'})),
    ('date', 'medium', lambda t: bool(t & {'date', 'datetime', 'timestamp'})),
    ('record_identifier', 'medium', lambda t: bool(t & {'id', 'identifier', 'uuid', 'guid'})),
]

# (code, priority, title, pattern) checked against text values anywhere in the cell.
_VALUE_RULES = [
    ('email_pattern', 'high', 'Values look like email addresses',
     r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}'),
    ('ssn_pattern', 'high', 'Values look like Social Security numbers',
     r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)'),
    ('phone_pattern', 'high', 'Values look like phone numbers',
     r'(?<!\d)(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?!\d)'),
    ('titled_name_pattern', 'high', 'Values contain titled names such as "Dr. Smith"',
     r'\b(?:Dr|Mr|Mrs|Ms|Miss|Prof)\.?\s+[A-Z][a-z]+'),
    ('ip_address_pattern', 'medium', 'Values look like IP addresses',
     r'(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])'),
    ('url_pattern', 'medium', 'Values contain web addresses', r'(?i)\b(?:https?://|www\.)\S+'),
    ('date_values', 'medium', 'Values contain full dates',
     r'(?<!\d)(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})(?!\d)'),
]

CHECKS = (['identifier_column_name'] + [code for code, *_ in _VALUE_RULES]
          + ['free_text', 'unique_values', 'age_over_89'])

LIMITATIONS = [
    'This is heuristic screening for potential identifiers. It does not certify '
    'de-identification under HIPAA Safe Harbor or Expert Determination.',
    'Finding no patterns does not mean the data contains no identifiers.',
    'Names without a title, addresses, and other identifiers without a recognizable '
    'pattern or column name can be missed, especially in free text.',
    'Column-name checks use English keywords. Matched values are not included in this result.',
]


def _tokens(name) -> set:
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(name))
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
    return {t for t in re.split(r'[^a-z0-9]+', text.lower()) if t}


def _finding(column, code, priority, title, evidence, suggested_action) -> dict:
    return {'id': f'{column}:{code}', 'code': code, 'column': column, 'priority': priority,
            'title': title, 'evidence': evidence, 'suggested_action': suggested_action}


def _name_finding(column: str) -> Optional[dict]:
    tokens = _tokens(column)
    for kind, priority, test in _NAME_RULES:
        if test(tokens):
            return _finding(column, 'identifier_column_name', priority,
                            'Column name suggests an identifier', {'kind': kind},
                            'Confirm whether this column is needed; remove or generalize it before sharing.')
    return None


def _text_findings(column: str, values: pd.Series) -> List[dict]:
    findings, scanned = [], int(len(values))
    for code, priority, title, pattern in _VALUE_RULES:
        matches = int(values.str.contains(pattern, regex=True).sum())
        if matches:
            findings.append(_finding(column, code, priority, title,
                                     {'matching_values': matches, 'values_scanned': scanned},
                                     'Review this column; remove or generalize these values before sharing.'))
    long_values = int((values.str.split().str.len() >= FREE_TEXT_WORDS).sum())
    if long_values:
        findings.append(_finding(column, 'free_text', 'medium', 'Column contains free text',
                                 {'values_with_8_or_more_words': long_values, 'values_scanned': scanned},
                                 'Free text can contain identifiers patterns miss; review it manually.'))
    elif scanned >= UNIQUE_MIN_ROWS and values.nunique() == scanned:
        findings.append(_unique_finding(column, scanned))
    return findings


def _unique_finding(column, scanned) -> dict:
    return _finding(column, 'unique_values', 'medium', 'Every value is distinct',
                    {'distinct_values': scanned, 'values_scanned': scanned},
                    'Distinct values can act as record identifiers; confirm this column is needed.')


def _numeric_findings(column: str, values: pd.Series, tokens: set) -> List[dict]:
    findings, scanned = [], int(len(values))
    if 'age' in tokens:
        over = int((values > 89).sum())
        if over:
            findings.append(_finding(
                column, 'age_over_89', 'high', 'Ages over 89 are present',
                {'values_over_89': over, 'values_scanned': scanned},
                'HIPAA Safe Harbor groups ages over 89 into one category; review before sharing.'))
    integral = bool(((values % 1) == 0).all()) if scanned else False
    if integral and scanned >= UNIQUE_MIN_ROWS and values.nunique() == scanned:
        findings.append(_unique_finding(column, scanned))
    return findings


def screen_identifiers(df: pd.DataFrame, *, max_rows: int = DEFAULT_MAX_ROWS) -> dict:
    """Screen column names and values for potential identifiers.

    Values in the first max_rows rows of every column are checked; coverage
    reports exactly what was scanned. Raises ValueError for duplicate column
    names, which validate_input rejects.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError('screen_identifiers expects a pandas DataFrame.')
    if df.columns.has_duplicates:
        raise ValueError('Column names must be unique before screening.')
    rows_scanned = min(int(len(df)), max_rows)
    scanned = df.iloc[:rows_scanned]

    findings = []
    for position, name in enumerate(df.columns):
        column = str(name)
        name_finding = _name_finding(column)
        findings += [name_finding] if name_finding else []
        values = scanned.iloc[:, position].dropna()
        if pd.api.types.is_bool_dtype(values):
            continue
        if pd.api.types.is_datetime64_any_dtype(values):
            if len(values):
                findings.append(_finding(column, 'date_values', 'medium', 'Column contains dates',
                                         {'matching_values': int(len(values)), 'values_scanned': int(len(values))},
                                         'Dates other than year can identify people; generalize before sharing.'))
        elif pd.api.types.is_numeric_dtype(values):
            findings += _numeric_findings(column, values, _tokens(column))
        else:
            findings += _text_findings(column, values.astype(str))
    findings.sort(key=lambda f: PRIORITIES.index(f['priority']))  # stable: keeps column order

    if findings:
        status = REVIEW_NEEDED
    elif len(df) == 0 or len(df.columns) == 0:
        status = INSUFFICIENT_EVIDENCE
    else:
        status = NO_PATTERNS_FOUND
    limitations = list(LIMITATIONS)
    if rows_scanned < len(df):
        limitations.append(f'Only the first {rows_scanned:,} of {len(df):,} rows were scanned for value patterns.')
    if len(df) == 0:
        limitations.append('The dataset has no rows, so only column names were checked.')

    return {
        'schema_version': SCHEMA_VERSION,
        'scope': SCREENING_SCOPE,
        'status': status,
        'certifies_deidentification': False,
        'coverage': {
            'row_count': int(len(df)),
            'rows_scanned': rows_scanned,
            'column_count': int(len(df.columns)),
            'complete': rows_scanned == len(df),
            'checks': list(CHECKS),
        },
        'findings': findings,
        'limitations': limitations,
    }
