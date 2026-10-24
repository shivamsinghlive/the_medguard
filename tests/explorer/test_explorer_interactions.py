"""Explorer API: range and row filters, shared evidence payloads, and the reviewed-copy flow."""
from pathlib import Path
import json
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from explorer import llm, server
from utils.audit_input import dataset_fingerprint

DEMO = 'dataset4_diabetes_combined.csv'
ROLES = {'outcome': 'diabetes', 'demographics': ['sex'], 'identifiers': ['patient_id']}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(llm, 'status', lambda *a, **k: {'available': False, 'model': 'test', 'reason': 'disabled in tests'})
    return TestClient(server.app)


@pytest.fixture
def source():
    return pd.read_csv(ROOT / 'data/synthetic' / DEMO)


def load(client):
    return client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']


def analyze(client, dataset_id, **extra):
    return client.post('/api/analyze', json={'dataset_id': dataset_id, 'roles': ROLES, **extra})


def test_numeric_range_filter_recomputes_from_the_subset(client, source):
    dataset_id = load(client)
    result = analyze(client, dataset_id, ranges={'age': [60, 40]}).json()

    expected = int(source['age'].between(40, 60).sum())
    assert result['subset']['row_count'] == expected
    assert result['evidence']['mosaic']['rowCount'] == expected
    assert result['subset']['ranges'] == {'age': [60.0, 40.0]}


def test_row_selection_filter_keeps_source_row_ids(client):
    dataset_id = load(client)
    result = analyze(client, dataset_id, row_ids=[0, 5, 9, 99999]).json()

    assert result['subset']['row_count'] == 3
    assert [row['id'] for row in result['evidence']['mosaic']['rows']] == [0, 5, 9]
    assert [row['row'] for row in result['evidence']['mosaic']['rows']] == [1, 6, 10]


def test_bad_or_empty_filters_are_rejected_without_a_traceback(client):
    dataset_id = load(client)
    assert analyze(client, dataset_id, ranges={'sex': [0, 1]}).status_code == 422
    assert analyze(client, dataset_id, ranges={'nope': [0, 1]}).status_code == 422
    empty = analyze(client, dataset_id, ranges={'age': [-5, -1]})
    assert empty.status_code == 422 and 'No rows match' in empty.json()['detail']


def test_evidence_payload_carries_aggregates_and_no_cell_values(client, source):
    result = analyze(client, load(client), focus_column='hba1c').json()
    evidence = result['evidence']
    mosaic_text = json.dumps(evidence['mosaic'])

    assert [t['label'] for t in evidence['status_tiles']] == ['Structure', 'Identifiers', 'Quality', 'Representation']
    assert evidence['mosaic']['focusActive'] is True
    assert evidence['mosaic']['funnel'][0]['rows'] == len(source)
    assert evidence['quality']['missing_cells'] == int(source.isna().sum().sum())
    assert evidence['cohort'][0]['groups'][0]['label'].startswith('sex = ')
    assert 'SYNTH_' not in mosaic_text and 'hba1c' not in mosaic_text
    assert {b['id'] for b in result['board']} >= {'rows'}


def test_preview_accept_and_copy_leave_the_source_unchanged(client, source):
    dataset_id = load(client)
    before = dataset_fingerprint(server._datasets('local')[dataset_id]['frame'])
    preview = client.post('/api/preview', json={
        'dataset_id': dataset_id, 'roles': ROLES, 'actions': [{'action': 'drop_duplicate_rows'}],
    }).json()

    assert preview['result']['status'] == 'preview_ready'
    assert preview['changes']['removedRows'] == int(source.duplicated().sum())
    assert preview['diff']['rows'] == [len(source), len(source) - int(source.duplicated().sum())]
    assert client.get('/api/preview/copy.csv', params={'dataset_id': dataset_id, 'preview_id': preview['preview_id']}).status_code == 409

    accepted = client.post('/api/preview/accept', json={'dataset_id': dataset_id, 'preview_id': preview['preview_id']}).json()
    assert accepted['changes']['accepted'] is True
    copy = client.get('/api/preview/copy.csv', params={'dataset_id': dataset_id, 'preview_id': preview['preview_id']})
    assert copy.status_code == 200 and copy.text.startswith('source_row_index,')
    assert dataset_fingerprint(server._datasets('local')[dataset_id]['frame']) == before

    report = client.post('/api/report', json={'dataset_id': dataset_id, 'roles': ROLES}).json()
    assert report['change_preview']['accepted_for_export'] is True


def test_protected_roles_cannot_be_change_targets(client):
    dataset_id = load(client)
    blocked = client.post('/api/preview', json={
        'dataset_id': dataset_id, 'roles': ROLES, 'actions': [{'action': 'drop_column', 'column': 'sex'}],
    }).json()
    assert blocked['result']['status'] == 'blocked'
    assert blocked['diff'] is None
    stale = client.post('/api/preview/accept', json={'dataset_id': dataset_id, 'preview_id': 'not-current'})
    assert stale.status_code == 409
