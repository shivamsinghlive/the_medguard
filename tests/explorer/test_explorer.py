"""MedGuard Explorer (swathi-al): planner, explanations, and local API. No real AI or network."""
from pathlib import Path
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from explorer import insights, llm, planner, server

DEMO = 'dataset3_heart_disease_indigenous.csv'
IDEA = {'title': '', 'question': 'Can we predict heart disease reliably for Indigenous patients and women?',
        'outcome': 'heart disease', 'population': 'US adults', 'groups': 'Indigenous patients, women'}


def columns_for(df):
    from services.readiness import _feature_profile
    from services.representation import _label
    cols = []
    for c in df.columns:
        p = _feature_profile(df[c], c, 'feature')
        cols.append({'name': c, 'kind': p['kind'], 'distinct': p['distinct'], 'id_like': p['id_like'], 'top': p['top'],
                     'labels': sorted(df[c].dropna().map(_label).unique()) if p['kind'] == 'categorical' else None})
    return cols


@pytest.fixture
def demo_columns():
    return columns_for(pd.read_csv(ROOT / 'data/synthetic' / DEMO))


def test_rule_plan_follows_the_research_idea(demo_columns):
    plan = planner.build_plan(demo_columns, IDEA, use_ai=False)
    assert plan['source'] == 'rules'
    assert plan['outcome']['column'] == 'heart_disease'
    assert [d['column'] for d in plan['demographics']] == ['sex', 'race_ethnicity']
    assert [i['column'] for i in plan['identifiers']] == ['patient_id']
    present = [(f['column'], f['label']) for f in plan['focus_groups'] if not f['missing']]
    missing = [(f['column'], f['concept']) for f in plan['focus_groups'] if f['missing']]
    assert present == [('sex', 'Female')] and missing == [('race_ethnicity', 'indigenous')]
    assert 'intersections' in plan['widgets']


def test_ai_plan_only_used_for_real_columns(demo_columns):
    fake = lambda cols, idea, model: {'outcome': 'heart_attack_flag', 'demographic_columns': ['gender'], 'identifier_columns': []}
    plan = planner.build_plan(demo_columns, IDEA, ai_planner=fake)
    assert plan['source'] == 'rules' and plan['outcome']['column'] == 'heart_disease'
    assert 'did not name usable columns' in plan['ai']['error']
    good = lambda cols, idea, model: {'outcome': 'heart_disease', 'demographic_columns': ['sex'], 'identifier_columns': ['patient_id'],
                                      'reasons': {'outcome': 'The study predicts heart disease.'}}
    plan = planner.build_plan(demo_columns, IDEA, ai_planner=good)
    assert plan['source'] == 'ai' and plan['outcome'] == {'column': 'heart_disease', 'source': 'ai',
                                                          'reason': 'The study predicts heart disease.'}


def test_unavailable_ai_falls_back_to_rules(demo_columns):
    def down(*args):
        raise llm.LLMUnavailable('offline')
    plan = planner.build_plan(demo_columns, IDEA, ai_planner=down)
    assert plan['source'] == 'rules' and plan['ai']['error'] == 'offline'
    assert plan['outcome']['column'] == 'heart_disease'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(llm, 'status', lambda *a, **k: {'available': False, 'model': 'test', 'reason': 'disabled in tests'})
    return TestClient(server.app)


def roles():
    return {'outcome': 'heart_disease', 'demographics': ['sex', 'race_ethnicity'], 'identifiers': ['patient_id']}


def test_api_loads_validates_and_analyzes_real_data(client):
    loaded = client.post(f'/api/datasets/demo/{DEMO}').json()
    assert loaded['accepted'] and loaded['validation']['row_count'] == 800
    source = pd.read_csv(ROOT / 'data/synthetic' / DEMO)
    result = client.post('/api/analyze', json={'dataset_id': loaded['dataset_id'], 'roles': roles(), 'idea': IDEA}).json()
    counts = {c['label']: c['count'] for c in result['readiness']['outcome']['classes']}
    assert counts == {str(k): int(v) for k, v in source['heart_disease'].value_counts().items()}
    assert {b['id'] for b in result['board']} == set(planner.WIDGETS)
    assert result['subset'] == {'filters': {}, 'ranges': {}, 'row_ids': 0, 'row_count': 800, 'total_rows': 800}


def test_api_filters_recompute_from_the_subset(client):
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']
    female = client.post('/api/analyze', json={'dataset_id': dataset_id, 'roles': roles(), 'filters': {'sex': ['Female']}}).json()
    source = pd.read_csv(ROOT / 'data/synthetic' / DEMO)
    assert female['subset']['row_count'] == int((source['sex'] == 'Female').sum())
    assert female['readiness']['outcome']['labeled_count'] == female['subset']['row_count']


def test_api_answers_flag_missing_focus_group(client):
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']
    focus = [{'column': 'race_ethnicity', 'label': None, 'concept': 'indigenous', 'missing': True, 'reason': ''}]
    result = client.post('/api/analyze', json={'dataset_id': dataset_id, 'roles': roles(), 'focus_groups': focus}).json()
    answer = next(a for a in result['answers'] if 'focus group' in a['question'])
    assert answer['status'] == 'review_needed' and 'indigenous' in answer['answer']


def test_api_rejects_bad_upload_and_unknown_dataset(client):
    rejected = client.post('/api/datasets/upload?filename=bad.csv', content=b'a,a\n1,2\n').json()
    assert rejected['accepted'] is False and rejected['validation']['errors'][0]['code'] == 'duplicate_column_names'
    assert client.post('/api/analyze', json={'dataset_id': 'nope', 'roles': roles()}).status_code == 404
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']
    bad = client.post('/api/analyze', json={'dataset_id': dataset_id, 'roles': {'outcome': 'missing'}})
    assert bad.status_code == 422


def test_api_report_and_rule_explanation(client):
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']
    body = {'dataset_id': dataset_id, 'roles': roles(), 'idea': IDEA}
    report = client.post('/api/report', json=body).json()
    assert len(report['report_digest']) == 64 and 'Not model validation' in report['disclaimer']
    explanation = client.post('/api/explain', json={**body, 'widget': 'outcome', 'use_ai': False}).json()
    assert explanation['source'] == 'rules' and explanation['points'][0].startswith('Classes:')


def _results(client, focus=()):
    dataset_id = client.post(f'/api/datasets/demo/{DEMO}').json()['dataset_id']
    return server._analyze(server.AnalyzeRequest(dataset_id=dataset_id, roles=roles(), focus_groups=list(focus)))


@pytest.mark.parametrize('reply,source', [
    ({'summary': 'The data is fair and safe.', 'points': [], 'caution': ''}, 'rules'),
    ({'summary': 'Asian patients are rare.', 'points': [], 'caution': ''}, 'rules'),
    ({'summary': 'Women make up 336 rows.', 'points': ['Female has 146 positive cases.'], 'caution': 'Descriptive only.'}, 'ai'),
    ({'summary': 42, 'points': 'x'}, 'rules'),
    ({'summary': "No data on women's outcomes.", 'points': [], 'caution': ''}, 'rules'),
])
def test_ai_explanations_are_checked_against_evidence(client, reply, source):
    results = _results(client)
    out = insights.explain('groups', results, IDEA, chat=lambda *a, **k: reply)
    assert out['source'] == source


def test_ai_may_mention_focus_group_that_is_absent_when_facts_say_so(client):
    focus = [{'column': 'race_ethnicity', 'label': None, 'concept': 'indigenous', 'missing': True, 'reason': ''}]
    reply = {'summary': 'There are no Indigenous rows.', 'points': [], 'caution': 'Descriptive only.'}
    assert insights.explain('groups', _results(client, focus), IDEA, chat=lambda *a, **k: reply)['source'] == 'ai'
    assert insights.explain('groups', _results(client), IDEA, chat=lambda *a, **k: reply)['source'] == 'rules'
