"""Structural CSV validation before any analysis.

Pure function over the uploaded bytes: no file writes, AI, network, or
Streamlit state. Accepting a file means it parsed with a consistent shape
inside the size limits, not that its contents are correct or de-identified.
Messages and details never quote cell values.
"""
from collections import Counter
import csv
import io
from typing import List, Optional, Tuple

import pandas as pd

from services.contracts import ACCEPTED, REJECTED, SCHEMA_VERSION, VALIDATION_SCOPE

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_ROWS = 200_000
DEFAULT_MAX_COLUMNS = 500
_MAX_REPORTED_LINES = 5

LIMITATIONS = [
    'Validation checks file structure and size only, not data quality, clinical '
    'correctness, or privacy.',
    'Column types are inferred with pandas defaults; empty cells and values such as '
    '"NA" or "null" are read as missing.',
]


def _issue(code, message, **details) -> dict:
    return {'code': code, 'message': message, 'details': details}


def _result(byte_count, limits, errors, warnings, frame=None):
    result = {
        'schema_version': SCHEMA_VERSION,
        'scope': VALIDATION_SCOPE,
        'status': REJECTED if errors else ACCEPTED,
        'byte_count': byte_count,
        'row_count': None if frame is None else int(len(frame)),
        'column_count': None if frame is None else int(len(frame.columns)),
        'limits': limits,
        'errors': errors,
        'warnings': warnings,
        'limitations': list(LIMITATIONS),
    }
    return result, (None if errors else frame)


def _check_structure(text, max_rows, max_columns) -> Tuple[List[str], int, List[dict]]:
    """Return header, data-row count, and errors, reading rows with csv."""
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    header, data_rows, bad_lines, bad_count = None, 0, [], 0
    try:
        for row in reader:
            if not row:  # blank line; pandas skips these too
                continue
            if header is None:
                header = row
                if len(header) > max_columns:
                    return header, 0, [_issue(
                        'too_many_columns', f'The file has more than {max_columns} columns.',
                        column_count=len(header), max_columns=max_columns)]
                continue
            data_rows += 1
            if data_rows > max_rows:
                return header, data_rows, [_issue(
                    'too_many_rows', f'The file has more than {max_rows:,} data rows.',
                    max_rows=max_rows)]
            if len(row) != len(header):
                bad_count += 1
                if len(bad_lines) < _MAX_REPORTED_LINES:
                    bad_lines.append(reader.line_num)
    except csv.Error as exc:
        return header or [], data_rows, [_issue(
            'malformed_csv', 'The file could not be read as CSV (for example, an unclosed quote).',
            line=reader.line_num, reason=str(exc))]
    if header is None:
        return [], 0, [_issue('empty_file', 'The file has no header row.')]
    if bad_count:
        return header, data_rows, [_issue(
            'inconsistent_row_length',
            f'{bad_count} row(s) do not have the same number of fields as the header '
            f'({len(header)}).',
            row_count=bad_count, first_lines=bad_lines, expected_fields=len(header))]
    return header, data_rows, []


def _header_issues(header) -> Tuple[List[dict], List[dict]]:
    errors, warnings = [], []
    repeated = sorted(name for name, n in Counter(header).items() if n > 1 and name.strip())
    if repeated:
        errors.append(_issue('duplicate_column_names',
                             'Column names must be unique so results refer to one column.',
                             columns=repeated))
    blank = [i + 1 for i, name in enumerate(header) if not name.strip()]
    if blank:
        warnings.append(_issue('blank_column_names',
                               'Some columns have no name; they are shown as "Unnamed: N".',
                               positions=blank))
    padded = [name for name in header if name.strip() and name != name.strip()]
    if padded:
        warnings.append(_issue('column_name_whitespace',
                               'Some column names start or end with spaces; they are kept as written.',
                               columns=padded))
    return errors, warnings


def validate_input(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES,
                   max_rows: int = DEFAULT_MAX_ROWS,
                   max_columns: int = DEFAULT_MAX_COLUMNS) -> Tuple[dict, Optional[pd.DataFrame]]:
    """Validate raw CSV bytes; return (ValidationResult, frame or None).

    The returned frame is the exact parse that was validated, so callers
    analyze what was checked instead of re-reading the file differently.
    """
    if isinstance(data, memoryview):
        data = data.tobytes()
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('validate_input expects the raw file bytes.')
    limits = {'max_bytes': max_bytes, 'max_rows': max_rows, 'max_columns': max_columns}
    byte_count = len(data)

    if byte_count > max_bytes:
        return _result(byte_count, limits, [_issue(
            'too_large', f'The file is larger than {max_bytes:,} bytes.',
            byte_count=byte_count, max_bytes=max_bytes)], [])
    if b'\x00' in data:
        return _result(byte_count, limits, [_issue(
            'not_text', 'The file contains binary data and is not a text CSV.')], [])
    try:
        text = bytes(data).decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        return _result(byte_count, limits, [_issue(
            'encoding_error', 'The file is not UTF-8 text. Save it as "CSV UTF-8" and retry.',
            byte_offset=exc.start)], [])
    if not text.strip():
        return _result(byte_count, limits, [_issue('empty_file', 'The file is empty.')], [])

    header, data_rows, errors = _check_structure(text, max_rows, max_columns)
    if errors:
        return _result(byte_count, limits, errors, [])
    errors, warnings = _header_issues(header)
    if not data_rows:
        errors.append(_issue('no_data_rows', 'The file has a header but no data rows.'))
    if errors:
        return _result(byte_count, limits, errors, warnings)

    try:
        frame = pd.read_csv(io.StringIO(text), low_memory=False)
    except (pd.errors.ParserError, ValueError) as exc:
        return _result(byte_count, limits, [_issue(
            'malformed_csv', 'The file could not be parsed as CSV.', reason=str(exc))], warnings)
    return _result(byte_count, limits, [], warnings, frame)
