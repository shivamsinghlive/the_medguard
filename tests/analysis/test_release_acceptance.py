"""W05 release acceptance: first-release gates through the integrated path.

Each test drives raw CSV bytes through validate_input -> run_audit -> exports,
the same path the workspace uses. Known-defect cases come from DSX_AUDIT.md.
Passing these checks is not clinical validation or privacy certification.
"""
import csv
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from services.audit_runner import report_csv, report_json, reviewed_copy_csv, run_audit
from services.change_preview import preview_changes
from services.input_validation import validate_input
from utils.audit_input import dataset_fingerprint

DEMO = ROOT / 'data/synthetic/dataset1_heart_disease_quality.csv'


def to_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode('utf-8')


def audit(data: bytes, demographic_columns=(), reference=None):
    validation, frame = validate_input(data)
    assert validation['status'] == 'accepted', validation['errors']
    report = run_audit(frame, demographic_columns=list(demographic_columns),
                       reference_proportions=reference, source_type='uploaded_csv',
                       input_validation=validation)
    return report, frame


def csv_rows(report, row_type):
    return [r for r in csv.DictReader(io.StringIO(report_csv(report))) if r['row_type'] == row_type]


# --- Known defects from DSX_AUDIT.md --------------------------------------

def test_defect_wrong_dataset_audited_now_uses_source_records():
    data = DEMO.read_bytes()
    report, frame = audit(data)
    source = pd.read_csv(DEMO)
    assert report['dataset']['fingerprint'] == dataset_fingerprint(frame) == dataset_fingerprint(source)
    assert report['dataset']['row_count'] == len(source)
    assert report['quality']['duplicate_rows'] == int(source.duplicated(keep=False).sum()) > 0
    assert report['quality']['missing_cells'] == int(source.isna().sum().sum())
    assert DEMO.read_bytes() == data


def test_defect_single_gender_dataset_is_no_longer_fair():
    report, _ = audit(to_bytes(pd.DataFrame({'sex': ['Male'] * 100, 'age': range(100)})), ['sex'])
    assert report['representation']['status'] == 'review_needed'
    assert [f['code'] for f in report['representation']['findings']] == ['single_group']


def test_defect_no_demographic_columns_is_insufficient_not_fair():
    report, _ = audit(to_bytes(pd.DataFrame({'measurement': [1, 2, 3]})))
    assert report['representation']['status'] == 'insufficient_evidence'
    assert 'FAIR' not in report_json(report)


def test_defect_email_after_row_100_is_screened():
    report, _ = audit(to_bytes(pd.DataFrame({'notes': ['ok'] * 100 + ['example@example.com']})))
    screening = report['identifier_screening']
    assert ('notes', 'email_pattern') in {(f['column'], f['code']) for f in screening['findings']}
    assert screening['coverage']['complete'] is True
    assert 'example@example.com' not in report_json(report) + report_csv(report)


def test_defect_numeric_identifier_with_age_95_is_screened():
    report, _ = audit(to_bytes(pd.DataFrame({'patient_id': [123456789], 'age': [95]})))
    codes = {(f['column'], f['code']) for f in report['identifier_screening']['findings']}
    assert {('patient_id', 'identifier_column_name'), ('age', 'age_over_89')} <= codes


def test_defect_smote_cannot_corrupt_outcomes():
    _, frame = audit(DEMO.read_bytes())
    roles = {'heart_disease': 'outcome', 'sex': 'demographic', 'patient_id': 'identifier'}
    for action in ({'action': 'smote'}, {'action': 'balance_demographics'},
                   {'action': 'fill_missing', 'column': 'heart_disease', 'method': 'median'}):
        result, out = preview_changes(frame, [action], column_roles=roles)
        assert result['status'] == 'blocked' and out is None


def test_defect_fabricated_harm_is_reported_as_not_measured():
    report, _ = audit(DEMO.read_bytes(), ['sex'])
    assert report['model_performance']['status'] == 'not_measured'
    text = report_json(report).lower()
    for claim in ('patients_affected', 'performance_gap', 'accuracy improvement'):
        assert claim not in text


def test_defect_no_default_50_50_reference_or_5pct_rule():
    df = pd.DataFrame({'sex': ['Male'] * 80 + ['Female'] * 20})
    plain, _ = audit(to_bytes(df), ['sex'])
    assert all(g['reference_proportion'] is None for g in plain['representation']['attributes'][0]['groups'])
    supplied, _ = audit(to_bytes(df), ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    assert supplied['representation']['status'] == 'descriptive_only'  # 30 pp reported, not judged


def test_defect_numeric_codes_are_not_mapped_to_sex():
    report, _ = audit(to_bytes(pd.DataFrame({'sex': [1, 0, 1, 1, 0]})), ['sex'])
    labels = {g['label'] for g in report['representation']['attributes'][0]['groups']}
    assert labels == {'1', '0'}


# --- Release gates ---------------------------------------------------------

def test_gate_all_null_and_single_group_cases():
    df = pd.DataFrame({'race': [np.nan] * 30, 'site': ['A'] * 30, 'sex': ['F', 'M'] * 15})
    report, _ = audit(to_bytes(df), ['race', 'site', 'sex'])
    rep = report['representation']
    assert [a['status'] for a in rep['attributes']] == [
        'insufficient_evidence', 'review_needed', 'descriptive_only']
    assert rep['status'] == 'review_needed'
    assert {f['id'] for f in rep['findings']} == {'race:no_observed_values', 'site:single_group'}


@pytest.mark.parametrize('data', [
    b'', b'sex,age\n', b'sex,age\nM,40,extra\n', b'sex,sex\nM,F\n', b'\x00\x01', 'é'.encode('latin-1'),
])
def test_gate_malformed_input_never_reaches_analysis(data):
    validation, frame = validate_input(data)
    assert validation['status'] == 'rejected' and frame is None and validation['errors']
    with pytest.raises(ValueError):
        run_audit(pd.DataFrame({'a': [1]}), demographic_columns=[], source_type='uploaded_csv',
                  input_validation=validation)


def test_gate_repeated_runs_are_identical():
    data = DEMO.read_bytes()
    first, _ = audit(data, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    second, _ = audit(data, ['sex'], {'sex': {'Male': 0.5, 'Female': 0.5}})
    assert report_json(first) == report_json(second)
    assert report_csv(first) == report_csv(second)


def test_gate_exports_match_measurements():
    report, _ = audit(DEMO.read_bytes(), ['sex'])
    assert json.loads(report_json(report)) == report
    cohort = csv_rows(report, 'cohort')
    groups = [g for a in report['representation']['attributes'] for g in a['groups']]
    assert [(r['label'], int(r['count'])) for r in cohort] == [(g['label'], g['count']) for g in groups]
    assert len(csv_rows(report, 'finding')) == len(report['representation']['findings'])
    identifier_rows = csv_rows(report, 'identifier_finding')
    assert [(r['column'], r['code']) for r in identifier_rows] == [
        (f['column'], f['code']) for f in report['identifier_screening']['findings']]


def test_gate_privacy_coverage_and_limitations_are_honest():
    report, _ = audit(DEMO.read_bytes())
    screening = report['identifier_screening']
    assert screening['certifies_deidentification'] is False
    assert screening['coverage']['rows_scanned'] == report['dataset']['row_count']
    assert any('does not certify de-identification' in l for l in screening['limitations'])
    assert any('does not mean the data contains no identifiers' in l for l in screening['limitations'])


def test_gate_accepted_preview_exports_a_separate_traceable_copy():
    data = DEMO.read_bytes()
    _, frame = audit(data)
    result, out = preview_changes(frame, [{'action': 'drop_duplicate_rows'}],
                                  column_roles={'sex': 'demographic'})
    assert result['status'] == 'preview_ready'
    assert result['after']['row_count'] == len(frame) - result['actions'][0]['evidence']['rows_removed']
    exported = pd.read_csv(io.StringIO(reviewed_copy_csv(out)))
    assert exported['source_row_index'].tolist() == list(out.index)
    assert dataset_fingerprint(frame) == result['source_fingerprint']
    assert DEMO.read_bytes() == data


def test_gate_offline_demo_runs_without_ai_or_network(monkeypatch):
    monkeypatch.chdir(ROOT)

    def blocked(*args, **kwargs):
        raise OSError('network disabled for offline demo check')
    with patch('socket.create_connection', side_effect=blocked), \
         patch('ollama.generate', side_effect=RuntimeError('AI unavailable')), \
         patch('ollama.Client.embeddings', side_effect=RuntimeError('AI unavailable')):
        app = AppTest.from_file(str(ROOT / 'src/ui/audit_workspace.py')).run(timeout=60)
    assert not app.exception
    assert [m.value for m in app.metric if m.label == 'Records'] == ['1,200']
