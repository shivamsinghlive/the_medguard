"""Switchable AI providers (Ollama, OpenAI-compatible such as Groq, Claude) with fakes: no network, no keys."""
from pathlib import Path
from types import SimpleNamespace
import io
import json
import sys
import urllib.error

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from explorer import insights, llm, planner, server

SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setenv('MEDGUARD_AI_PROVIDER', 'openai')
    monkeypatch.setenv('MEDGUARD_AI_API_KEY', 'test-key-not-real')
    monkeypatch.delenv('MEDGUARD_AI_BASE_URL', raising=False)


@pytest.fixture
def claude(monkeypatch):
    monkeypatch.setenv('MEDGUARD_AI_PROVIDER', 'anthropic')
    monkeypatch.setenv('MEDGUARD_AI_API_KEY', 'test-key-not-real')


def test_status_never_calls_hosted_apis_and_reports_missing_keys(monkeypatch):
    monkeypatch.setenv('MEDGUARD_AI_PROVIDER', 'openai')
    monkeypatch.delenv('MEDGUARD_AI_API_KEY', raising=False)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setattr(llm.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('status must not call the API'))
    missing = llm.status('llama-3.1-8b-instant')
    assert missing['available'] is False and 'No API key' in missing['reason'] and missing['provider'] == 'Groq'

    monkeypatch.setenv('GROQ_API_KEY', 'test-key-not-real')
    assert llm.status('llama-3.1-8b-instant')['available'] is True

    monkeypatch.setenv('MEDGUARD_AI_PROVIDER', 'off')
    assert llm.status()['available'] is False
    with pytest.raises(llm.LLMUnavailable):
        llm.chat_json('s', 'u')


def test_openai_compatible_request_shape_and_json_reply(groq, monkeypatch):
    seen = {}

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        seen.update(url=request.full_url, auth=request.headers['Authorization'], body=json.loads(request.data))
        return Reply(json.dumps({'choices': [{'message': {'content': '{"ok": true}'}}]}).encode())

    monkeypatch.setattr(llm.urllib.request, 'urlopen', urlopen)
    assert llm.chat_json('Return JSON.', 'hi', model='llama-3.1-8b-instant') == {'ok': True}
    assert seen['url'] == 'https://api.groq.com/openai/v1/chat/completions'
    assert seen['auth'] == 'Bearer test-key-not-real'
    assert seen['body']['response_format'] == {'type': 'json_object'} and seen['body']['temperature'] == 0


def test_openai_errors_fall_back_without_leaking_the_key(groq, monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, None)

    monkeypatch.setattr(llm.urllib.request, 'urlopen', urlopen)
    with pytest.raises(llm.LLMUnavailable) as err:
        llm.chat_json('s', 'u')
    assert 'HTTP 401' in str(err.value) and 'test-key' not in str(err.value)


def fake_claude(monkeypatch, *, text='{"ok": true}', stop_reason='end_turn'):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type='text', text=text)])

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, '_anthropic_client', lambda timeout: client)
    return calls


def test_claude_uses_structured_output_low_effort_and_fallbacks(claude, monkeypatch):
    calls = fake_claude(monkeypatch)
    assert llm.chat_json('Return JSON.', 'hi', model='claude-opus-5-5', schema=SCHEMA) == {'ok': True}
    sent = calls[0]
    assert sent['model'] == 'claude-opus-5-5' and sent['system'] == 'Return JSON.'
    assert sent['output_config'] == {'effort': 'low', 'format': {'type': 'json_schema', 'schema': SCHEMA}}
    assert sent['fallbacks'] == 'default' and sent['betas'] == ['server-side-fallback-2026-07-01']
    assert 'temperature' not in sent and 'thinking' not in sent

    llm.chat_json('Return JSON.', 'hi', model='claude-haiku-5-5', schema=SCHEMA)
    assert 'fallbacks' not in calls[1] and 'betas' not in calls[1]


def test_claude_refusal_becomes_a_rule_based_fallback(claude, monkeypatch):
    fake_claude(monkeypatch, stop_reason='refusal')
    with pytest.raises(llm.LLMUnavailable, match='declined'):
        llm.chat_json('s', 'u', model='claude-opus-5-5')


def test_planner_and_explainer_pass_their_schemas(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, 'chat_json', lambda system, user, **k: seen.append(k.get('schema')) or {})
    planner._ai_plan([{'name': 'sex', 'kind': 'categorical', 'distinct': 2}], {'question': 'q'}, 'm')
    assert seen[-1] is planner.PLAN_SCHEMA
    assert insights.EXPLAIN_SCHEMA['required'] == ['summary', 'points', 'caution']


def test_public_server_uses_a_configured_hosted_provider(groq, monkeypatch):
    monkeypatch.setenv('MEDGUARD_PUBLIC', '1')
    server._SESSIONS.clear()
    client = TestClient(server.app)
    health = client.get('/api/health').json()
    assert health['ai']['available'] is True and health['ai']['provider'] == 'Groq'

    monkeypatch.setattr(planner, '_ai_plan', lambda cols, idea, model: {
        'outcome': 'diabetes', 'demographic_columns': ['sex'], 'identifier_columns': ['patient_id'],
        'reasons': {'outcome': 'named', 'demographic_columns': 'named', 'identifier_columns': 'named'}})
    headers = {'X-MedGuard-Session': 'hosted-ai-session-0001'}
    dataset_id = client.post('/api/datasets/demo/dataset4_diabetes_combined.csv', headers=headers).json()['dataset_id']
    plan = client.post('/api/plan', headers=headers, json={'dataset_id': dataset_id, 'use_ai': True,
                       'idea': {'question': 'Can we predict diabetes for women?', 'outcome': 'diabetes'}}).json()
    assert plan['source'] == 'ai'
