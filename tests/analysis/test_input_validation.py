"""CSV structural validation (W02): explicit rejections, no tracebacks, no cell values."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.input_validation import validate_input


def validate(data, **limits):
    result, frame = validate_input(data, **limits)
    json.dumps(result, allow_nan=False)
    assert result['status'] in ('accepted', 'rejected')
    assert (result['status'] == 'accepted') == (frame is not None) == (not result['errors'])
    return result, frame


def error_codes(result):
    return [e['code'] for e in result['errors']]


def test_accepts_well_formed_csv_and_returns_the_validated_parse():
    data = b'sex,age,outcome\nMale,40,0\nFemale,55,1\n,61,0\n'
    result, frame = validate(data)
    assert result['status'] == 'accepted'
    assert (result['row_count'], result['column_count'], result['byte_count']) == (3, 3, len(data))
    assert result['warnings'] == []
    pd.testing.assert_frame_equal(frame, pd.DataFrame(
        {'sex': ['Male', 'Female', np.nan], 'age': [40, 55, 61], 'outcome': [0, 1, 0]}))
    assert any('not data quality' in l for l in result['limitations'])


def test_utf8_bom_quoted_commas_and_newlines_are_accepted():
    data = '﻿note,sex\n"chest pain, mild",F\n"line one\nline two",M\n'.encode('utf-8')
    result, frame = validate(data)
    assert result['status'] == 'accepted'
    assert list(frame.columns) == ['note', 'sex']
    assert frame['note'].tolist() == ['chest pain, mild', 'line one\nline two']


@pytest.mark.parametrize('data,code', [
    (b'', 'empty_file'),
    (b'   \n\n  ', 'empty_file'),
    (b'sex,age\n', 'no_data_rows'),
    (b'sex,age\nMale,40\nFemale\n', 'inconsistent_row_length'),
    (b'sex,age\nMale,40,extra\n', 'inconsistent_row_length'),
    (b'sex,age\n"Male,40\n', 'malformed_csv'),
    (b'sex,sex\nMale,Female\n', 'duplicate_column_names'),
    (b'sex,age\n\x00\x01,2\n', 'not_text'),
    ('sex\nFéminin\n'.encode('latin-1'), 'encoding_error'),
])
def test_malformed_input_is_rejected_with_a_reason(data, code):
    result, frame = validate(data)
    assert result['status'] == 'rejected' and frame is None
    assert error_codes(result) == [code]
    assert result['errors'][0]['message']


def test_inconsistent_rows_report_line_numbers_not_values():
    rows = ['sex,age'] + ['Male,40'] * 3 + ['SECRET_VALUE'] + ['Female,50,x'] * 7
    result, _ = validate('\n'.join(rows).encode())
    error = result['errors'][0]
    assert error['details']['row_count'] == 8
    assert error['details']['first_lines'] == [5, 6, 7, 8, 9]
    assert 'SECRET_VALUE' not in json.dumps(result)


@pytest.mark.parametrize('limits,data,code', [
    ({'max_bytes': 10}, b'sex,age\nMale,40\n', 'too_large'),
    ({'max_rows': 2}, b'a\n1\n2\n3\n', 'too_many_rows'),
    ({'max_columns': 2}, b'a,b,c\n1,2,3\n', 'too_many_columns'),
])
def test_input_size_is_bounded(limits, data, code):
    result, frame = validate(data, **limits)
    assert error_codes(result) == [code] and frame is None
    assert result['row_count'] is None
    assert all(result['limits'][k] == v for k, v in limits.items())


def test_row_limit_is_inclusive():
    result, frame = validate(b'a\n1\n2\n', max_rows=2)
    assert result['status'] == 'accepted' and len(frame) == 2


def test_blank_and_padded_column_names_are_warnings_not_rewrites():
    result, frame = validate(b',sex , age\n0,M,40\n1,F,50\n')
    assert result['status'] == 'accepted'
    assert [w['code'] for w in result['warnings']] == ['blank_column_names', 'column_name_whitespace']
    assert result['warnings'][0]['details'] == {'positions': [1]}
    assert list(frame.columns) == ['Unnamed: 0', 'sex ', ' age']


def test_blank_lines_are_ignored_like_pandas():
    result, frame = validate(b'sex,age\n\nMale,40\n\nFemale,50\n')
    assert result['status'] == 'accepted' and result['row_count'] == 2


def test_accepts_bytearray_and_memoryview_but_not_paths():
    assert validate(bytearray(b'a\n1\n'))[0]['status'] == 'accepted'
    assert validate(memoryview(b'a\n1\n'))[0]['status'] == 'accepted'
    with pytest.raises(TypeError):
        validate_input('data/synthetic/dataset1_heart_disease_quality.csv')


def test_validation_is_deterministic_for_mixed_type_columns():
    data = ('code\n' + '\n'.join(['1'] * 70_000 + ['A'] * 10)).encode()
    first, frame = validate(data)
    second, again = validate(data)
    assert first == second
    pd.testing.assert_frame_equal(frame, again)
    assert frame['code'].dtype == object
