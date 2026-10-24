"""Potential identifier screening (W02): coverage, positives, and benign lookalikes."""
import json
from pathlib import Path
import socket
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.contracts import SCREENING_STATUSES
from services.privacy_screening import screen_identifiers
from utils.audit_input import dataset_fingerprint


def screen(df, **kwargs):
    result = screen_identifiers(df, **kwargs)
    json.dumps(result, allow_nan=False)
    assert result['status'] in SCREENING_STATUSES
    assert result['certifies_deidentification'] is False
    assert not any(w in json.dumps(result).upper() for w in ('"SAFE', 'HIPAA COMPLIANT', '"CLEAN'))
    assert len({f['id'] for f in result['findings']}) == len(result['findings'])
    return result


def found(result, column=None):
    return {(f['column'], f['code']) for f in result['findings']
            if column is None or f['column'] == column}


def name_kind(result, column):
    return next((f['evidence']['kind'] for f in result['findings']
                 if f['column'] == column and f['code'] == 'identifier_column_name'), None)


def test_email_after_row_100_is_found():
    df = pd.DataFrame({'notes': ['ok'] * 100 + ['example@example.com']})
    result = screen(df)
    assert result['status'] == 'review_needed'
    assert ('notes', 'email_pattern') in found(result)
    assert result['coverage'] == {'row_count': 101, 'rows_scanned': 101, 'column_count': 1,
                                  'complete': True, 'checks': result['coverage']['checks']}


def test_identifier_late_in_large_frame_is_found():
    df = pd.DataFrame({'comment': ['stable'] * 150_000 + ['call 617-555-0100']})
    assert ('comment', 'phone_pattern') in found(screen(df))


def test_numeric_identifier_and_age_95_are_found():
    result = screen(pd.DataFrame({'patient_id': [123456789], 'age': [95]}))
    assert name_kind(result, 'patient_id') == 'record_identifier'  # no safe-name whitelist
    assert ('age', 'age_over_89') in found(result)
    assert result['findings'][0]['code'] == 'age_over_89'  # high priority first


def test_unique_numeric_and_text_identifiers_without_identifier_names():
    df = pd.DataFrame({'ref': np.arange(10_000_000, 10_000_030),
                       'code': [f'SYNTH_{i:03d}' for i in range(30)],
                       'visits': [i % 4 for i in range(30)]})
    result = screen(df)
    assert found(result) == {('ref', 'unique_values'), ('code', 'unique_values')}


@pytest.mark.parametrize('value,code', [
    ('Contact jane.doe@hospital.org for follow-up', 'email_pattern'),
    ('SSN 123-45-6789 on file', 'ssn_pattern'),
    ('(617) 555-0100', 'phone_pattern'),
    ('617.555.0100', 'phone_pattern'),
    ('Seen by Dr. Patel today', 'titled_name_pattern'),
    ('Referred by Mrs Okafor', 'titled_name_pattern'),
    ('client 192.168.10.4 logged', 'ip_address_pattern'),
    ('see https://portal.example.com/p/1', 'url_pattern'),
    ('admitted 2023-01-15', 'date_values'),
    ('follow up 3/14/2024', 'date_values'),
])
def test_value_patterns_in_free_text_are_found(value, code):
    df = pd.DataFrame({'remarks': ['no concerns'] * 120 + [value]})
    result = screen(df)
    assert (('remarks', code)) in found(result)
    finding = next(f for f in result['findings'] if f['code'] == code)
    assert finding['evidence'] == {'matching_values': 1, 'values_scanned': 121}
    assert value not in json.dumps(result)  # matched values are never echoed


@pytest.mark.parametrize('value', [
    '120/80',                 # blood pressure, not a date
    '2023',                   # year alone is not a full date
    '1.2.3',                  # version-like, not an IP address
    '1.2.3.400',              # octet out of range
    'MS Clinic follow-up',    # multiple sclerosis, not "Ms." + name
    'Dr. visit scheduled',    # title without a capitalized name
    'Heart Disease',          # capitalized words alone are not flagged as names
    'HbA1c 6.5-7.0',          # lab range
    '555-1234',               # too short for a phone number
    'ratio 12-34-5678x',      # digits run into letters, not an SSN
])
def test_benign_lookalike_values_are_not_flagged(value):
    df = pd.DataFrame({'remarks': ['no concerns'] * 30 + [value]})
    assert found(screen(df)) == set()


@pytest.mark.parametrize('column,kind', [
    ('patient_name', 'person_name'), ('Name', 'person_name'), ('LastName', 'person_name'),
    ('SSN', 'ssn'), ('social_security_no', 'ssn'), ('MRN', 'medical_record_number'),
    ('e-mail', 'email'), ('EmailAddress', 'email'), ('home_phone', 'phone'),
    ('street_address', 'address'), ('zipCode', 'postal_code'), ('DOB', 'birth_date'),
    ('date_of_birth', 'birth_date'), ('IPAddress', 'ip_address'), ('website', 'url'),
    ('admission_date', 'date'), ('PatientID', 'record_identifier'),
    ('subject_id', 'record_identifier'), ('account_number', 'identifier_number'),
    ('device_serial', 'identifier_number'), ('member_id', 'identifier_number'),
])
def test_identifier_column_names_are_found(column, kind):
    assert name_kind(screen(pd.DataFrame({column: [1, 2]})), column) == kind


@pytest.mark.parametrize('column', [
    'drug_name', 'test_name', 'hospital_name', 'stage', 'dosage', 'page_count',
    'cell_count', 'birth_weight', 'covid_status', 'valid', 'paid_amount', 'insurance_type',
    'unzipped', 'mobility_score', 'diagnosis', 'outcome',
])
def test_benign_lookalike_column_names_are_not_flagged(column):
    assert name_kind(screen(pd.DataFrame({column: [1, 2]})), column) is None


def test_ages_at_or_below_89_and_non_age_columns_are_not_flagged():
    df = pd.DataFrame({'age': [20, 89, 45], 'stage': [95, 96, 97], 'age_years': [30.5, 88.9, None]})
    assert found(screen(df)) == set()
    assert ('age_years', 'age_over_89') in found(screen(pd.DataFrame({'age_years': [90.5]})))


def test_measurements_and_repeated_codes_are_not_unique_identifiers():
    df = pd.DataFrame({'cholesterol': np.linspace(150.5, 300.5, 40),  # distinct but fractional
                       'sex': ['F', 'M'] * 20,
                       'small': list(range(19)) + [None] * 21})       # too few values to judge
    assert found(screen(df)) == set()


def test_free_text_is_flagged_for_manual_review():
    note = 'patient reports intermittent chest pain after exercise for two weeks'
    result = screen(pd.DataFrame({'note': ['none'] * 40 + [note]}))
    assert found(result) == {('note', 'free_text')}
    assert result['findings'][0]['evidence']['values_with_8_or_more_words'] == 1


def test_datetime_columns_are_reported():
    df = pd.DataFrame({'when': pd.to_datetime(['2023-01-01', '2023-02-01', None])})
    result = screen(df)
    assert found(result) == {('when', 'date_values')}
    assert result['findings'][0]['evidence']['matching_values'] == 2


def test_no_patterns_found_is_not_clearance():
    df = pd.DataFrame({'sex': ['F', 'M'] * 30, 'cholesterol': [180, 200, 220] * 20, 'flag': [True, False] * 30})
    result = screen(df)
    assert result['status'] == 'no_patterns_found'
    assert result['findings'] == []
    assert any('does not mean the data contains no identifiers' in l for l in result['limitations'])
    assert any('does not certify de-identification' in l for l in result['limitations'])


def test_partial_coverage_is_reported_honestly():
    df = pd.DataFrame({'remarks': ['ok'] * 50 + ['a@b.org']})
    result = screen(df, max_rows=50)
    assert result['coverage']['rows_scanned'] == 50 and result['coverage']['complete'] is False
    assert result['status'] == 'no_patterns_found'
    assert any('Only the first 50 of 51 rows' in l for l in result['limitations'])


def test_empty_frames_are_insufficient_evidence_unless_names_match():
    assert screen(pd.DataFrame())['status'] == 'insufficient_evidence'
    assert screen(pd.DataFrame({'sex': pd.Series([], dtype=object)}))['status'] == 'insufficient_evidence'
    no_rows = screen(pd.DataFrame({'email': pd.Series([], dtype=object)}))
    assert no_rows['status'] == 'review_needed'
    assert any('only column names were checked' in l for l in no_rows['limitations'])


def test_all_null_and_mixed_type_columns_do_not_crash():
    df = pd.DataFrame({'empty': [None] * 25, 'mixed': [1, 'two', 3.5, None, 'x@y.com'] * 5})
    assert found(screen(df)) == {('mixed', 'email_pattern')}


def test_findings_are_ordered_by_priority_then_column():
    df = pd.DataFrame({'visit_date': ['x', 'y'], 'notes': ['a@b.org', 'none'], 'patient_id': [1, 2]})
    assert [f['id'] for f in screen(df)['findings']] == [
        'notes:email_pattern', 'visit_date:identifier_column_name', 'patient_id:identifier_column_name']


def test_input_is_not_mutated_and_results_are_deterministic():
    df = pd.DataFrame({'note': ['call 617-555-0100', None, 'ok'] * 10, 'age': [91, 40, None] * 10,
                       'cat': pd.Categorical(['a', 'b', 'a'] * 10)})
    before, fingerprint = df.copy(deep=True), dataset_fingerprint(df)
    first = screen(df)
    assert screen(df) == first
    pd.testing.assert_frame_equal(df, before)
    assert dataset_fingerprint(df) == fingerprint


def test_rejects_duplicate_columns_and_non_frames():
    with pytest.raises(ValueError, match='unique'):
        screen_identifiers(pd.DataFrame([[1, 2]], columns=['a', 'a']))
    with pytest.raises(TypeError):
        screen_identifiers({'a': [1]})


def test_runs_without_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Screening must not open network connections')
    monkeypatch.setattr(socket, 'socket', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    assert screen(pd.DataFrame({'email': ['a@b.org']}))['status'] == 'review_needed'
