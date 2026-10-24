"""Public demo mode: private sessions, expiry, AI off, and upload limits."""
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from explorer import llm, server

DEMO = 'dataset4_diabetes_combined.csv'
ROLES = {'outcome': 'diabetes', 'demographics': ['sex'], 'identifiers': ['patient_id']}
ALICE = {'X-MedGuard-Session': 'alice-0000-0000-0001'}
BOB = {'X-MedGuard-Session': 'bob-0000-0000-0000-02'}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('MEDGUARD_PUBLIC', '1')
    monkeypatch.setattr(llm, 'status', lambda *a, **k: pytest.fail('public mode must not probe the local model'))
    server._SESSIONS.clear()
    return TestClient(server.app)


def test_health_reports_public_mode_with_ai_off(client):
    health = client.get('/api/health').json()
    assert health['public'] is True and health['retention_minutes'] == 60
    assert health['ai']['available'] is False


def test_requests_without_a_session_are_refused(client):
    assert client.post(f'/api/datasets/demo/{DEMO}').status_code == 400
    assert client.post(f'/api/datasets/demo/{DEMO}', headers={'X-MedGuard-Session': 'short'}).status_code == 400


def test_sessions_do_not_share_datasets_or_previews(client):
    alice = client.post(f'/api/datasets/demo/{DEMO}', headers=ALICE).json()['dataset_id']
    bob = client.post(f'/api/datasets/demo/{DEMO}', headers=BOB).json()['dataset_id']
    assert alice == bob  # same file, same fingerprint, still separate copies

    preview = client.post('/api/preview', headers=ALICE, json={'dataset_id': alice, 'roles': ROLES,
                          'actions': [{'action': 'drop_duplicate_rows'}]}).json()
    accept_as_bob = client.post('/api/preview/accept', headers=BOB, json={'dataset_id': bob, 'preview_id': preview['preview_id']})
    assert accept_as_bob.status_code == 409
    other = client.post('/api/analyze', headers={'X-MedGuard-Session': 'carol-0000-0000-03'}, json={'dataset_id': alice, 'roles': ROLES})
    assert other.status_code == 404


def test_download_link_carries_the_session_in_the_query(client):
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}', headers=ALICE).json()['dataset_id']
    preview = client.post('/api/preview', headers=ALICE, json={'dataset_id': dataset_id, 'roles': ROLES,
                          'actions': [{'action': 'drop_duplicate_rows'}]}).json()
    client.post('/api/preview/accept', headers=ALICE, json={'dataset_id': dataset_id, 'preview_id': preview['preview_id']})
    copy = client.get('/api/preview/copy.csv', params={'dataset_id': dataset_id, 'preview_id': preview['preview_id'],
                                                       'session': ALICE['X-MedGuard-Session']})
    assert copy.status_code == 200


def test_sessions_expire_after_the_retention_window(client, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(server.time, 'monotonic', lambda: now[0])
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}', headers=ALICE).json()['dataset_id']
    now[0] += server.SESSION_TTL_SECONDS + 1
    expired = client.post('/api/analyze', headers=ALICE, json={'dataset_id': dataset_id, 'roles': ROLES})
    assert expired.status_code == 404 and '60 minutes' in expired.json()['detail']


def test_plans_never_use_the_local_model_in_public_mode(client, monkeypatch):
    monkeypatch.setattr(llm, 'generate', lambda *a, **k: pytest.fail('public mode must not call the local model'), raising=False)
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}', headers=ALICE).json()['dataset_id']
    plan = client.post('/api/plan', headers=ALICE, json={'dataset_id': dataset_id, 'use_ai': True,
                       'idea': {'question': 'Can we predict diabetes for women?', 'outcome': 'diabetes'}}).json()
    assert plan['source'] == 'rules'


def test_oversized_uploads_are_refused_before_reading(client):
    big = client.post('/api/datasets/upload', headers={**ALICE, 'Content-Length': str(26 * 1024 * 1024)}, content=b'a,b\n1,2\n')
    assert big.status_code == 413
