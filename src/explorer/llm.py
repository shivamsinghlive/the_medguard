"""Bounded access to an optional language model. Every caller has a non-AI fallback.

The provider is chosen with environment variables, so the same code runs on a
laptop (local Ollama, the default) and on a host (a hosted API):

    MEDGUARD_AI_PROVIDER   ollama (default) | openai | anthropic | off
    MEDGUARD_AI_MODEL      model name; defaults per provider (below)
    MEDGUARD_AI_BASE_URL   OpenAI-compatible endpoint (default: Groq)
    MEDGUARD_AI_API_KEY    key for the hosted provider (or GROQ_API_KEY / ANTHROPIC_API_KEY)

Callers send only the research text, column names, and aggregate counts, never
rows or cell values; see planner.py and insights.py.
"""
import json
import os
import queue
import threading
import urllib.error
import urllib.request
from typing import Callable, Optional
from urllib.parse import urlparse

HOST = 'http://127.0.0.1:11434'
PROVIDER_MODELS = {
    'ollama': 'llama3.2:3b',
    'openai': 'llama-3.1-8b-instant',
    'anthropic': 'claude-opus-5-5',
}
DEFAULT_BASE_URL = 'https://api.groq.com/openai/v1'
# Claude models that accept server-side refusal fallbacks in the "default" form.
FALLBACK_MODELS = {'claude-opus-5-5', 'claude-opus-5', 'claude-fable-5-1', 'claude-sonnet-5-5'}


def provider() -> str:
    value = os.environ.get('MEDGUARD_AI_PROVIDER', 'ollama').strip().lower()
    return value if value in PROVIDER_MODELS or value == 'off' else 'ollama'


def is_local() -> bool:
    return provider() == 'ollama'


DEFAULT_MODEL = os.environ.get('MEDGUARD_AI_MODEL') or PROVIDER_MODELS.get(provider(), PROVIDER_MODELS['ollama'])


def _base_url() -> str:
    return (os.environ.get('MEDGUARD_AI_BASE_URL') or DEFAULT_BASE_URL).rstrip('/')


def _api_key() -> Optional[str]:
    fallback = {'openai': 'GROQ_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}.get(provider())
    return os.environ.get('MEDGUARD_AI_API_KEY') or (os.environ.get(fallback) if fallback else None)


def provider_label() -> str:
    name = provider()
    if name == 'anthropic':
        return 'Anthropic'
    if name == 'openai':
        host = urlparse(_base_url()).hostname or 'hosted API'
        for key, label in (('groq', 'Groq'), ('openrouter', 'OpenRouter'), ('together', 'Together'), ('openai', 'OpenAI')):
            if key in host:
                return label
        return host
    return 'Local' if name == 'ollama' else 'Off'


class LLMUnavailable(RuntimeError):
    pass


def _with_timeout(fn: Callable, timeout: float):
    results = queue.Queue(maxsize=1)

    def run():
        try:
            results.put((True, fn()))
        except Exception as exc:  # reported to the caller as unavailable
            results.put((False, exc))
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise LLMUnavailable(f'The AI model did not answer within {timeout:g} seconds.')
    ok, value = results.get()
    if not ok:
        if isinstance(value, LLMUnavailable):
            raise value
        raise LLMUnavailable(f'The AI model is unavailable: {value}')
    return value


def status(model: str = DEFAULT_MODEL, timeout: float = 2.0) -> dict:
    """Report whether the model can be used; never raises and never spends hosted-API credit."""
    name = provider()
    base = {'model': model, 'provider': provider_label()}
    if name == 'off':
        return {**base, 'available': False, 'reason': 'AI is turned off on this server.'}
    if name != 'ollama':
        if not _api_key():
            return {**base, 'available': False, 'reason': f'No API key is set for {provider_label()}.'}
        return {**base, 'available': True, 'reason': None}

    def probe():
        import ollama
        listed = ollama.Client(host=HOST, timeout=timeout).list()
        return [m.get('name') or m.get('model') for m in listed.get('models', [])]
    try:
        models = _with_timeout(probe, timeout + 1)
    except LLMUnavailable as exc:
        return {**base, 'available': False, 'reason': str(exc)}
    found = any(n == model or n.split(':')[0] == model.split(':')[0] and n.endswith(model.split(':')[-1])
                for n in models if n)
    return {**base, 'available': found, 'reason': None if found else f'Model {model} is not installed in Ollama.'}


def _ollama_chat(system: str, user: str, model: str, timeout: float) -> str:
    import ollama
    client = ollama.Client(host=HOST, timeout=timeout)
    response = client.chat(model=model, format='json', options={'temperature': 0, 'seed': 7},
                           messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}])
    return response['message']['content']


def _openai_chat(system: str, user: str, model: str, timeout: float) -> str:
    """Any OpenAI-compatible chat endpoint (Groq by default) over plain HTTPS."""
    body = json.dumps({'model': model, 'temperature': 0, 'response_format': {'type': 'json_object'},
                       'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]})
    request = urllib.request.Request(f'{_base_url()}/chat/completions', data=body.encode(), method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {_api_key()}'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise LLMUnavailable(f'{provider_label()} returned HTTP {exc.code}.')
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMUnavailable(f'{provider_label()} could not be reached: {getattr(exc, "reason", exc)}')
    try:
        return payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise LLMUnavailable(f'{provider_label()} returned an unexpected response.')


def _anthropic_client(timeout: float):
    import anthropic
    return anthropic.Anthropic(api_key=_api_key(), timeout=timeout, max_retries=1)


def _anthropic_chat(system: str, user: str, model: str, timeout: float, schema: Optional[dict]) -> str:
    """Claude through the official SDK; structured outputs guarantee valid JSON when a schema is given."""
    import anthropic
    output_config = {'effort': 'low'}
    if schema:
        output_config['format'] = {'type': 'json_schema', 'schema': schema}
    extra = {'betas': ['server-side-fallback-2026-07-01'], 'fallbacks': 'default'} if model in FALLBACK_MODELS else {}
    try:
        response = _anthropic_client(timeout).beta.messages.create(
            model=model, max_tokens=16000, system=system, output_config=output_config,
            messages=[{'role': 'user', 'content': user}], **extra)
    except anthropic.AuthenticationError:
        raise LLMUnavailable('Anthropic rejected the API key.')
    except anthropic.RateLimitError:
        raise LLMUnavailable('Anthropic rate limit reached; try again shortly.')
    except anthropic.APIStatusError as exc:
        raise LLMUnavailable(f'Anthropic returned HTTP {exc.status_code}.')
    except anthropic.APIConnectionError:
        raise LLMUnavailable('Anthropic could not be reached.')
    if response.stop_reason == 'refusal':
        raise LLMUnavailable('The model declined this request.')
    text = next((block.text for block in response.content if block.type == 'text'), None)
    if text is None:
        raise LLMUnavailable('Anthropic returned no text.')
    return text


def chat_json(system: str, user: str, *, model: str = DEFAULT_MODEL, timeout: float = 30.0,
              schema: Optional[dict] = None) -> dict:
    """Ask for a JSON object; raise LLMUnavailable on timeout, error, refusal, or invalid JSON.

    `schema` (a JSON Schema object) is enforced where the provider supports it (Claude);
    callers still validate the shape they receive.
    """
    name = provider()
    if name == 'off':
        raise LLMUnavailable('AI is turned off on this server.')
    if name != 'ollama' and not _api_key():
        raise LLMUnavailable(f'No API key is set for {provider_label()}.')
    calls = {
        'ollama': lambda: _ollama_chat(system, user, model, timeout),
        'openai': lambda: _openai_chat(system, user, model, timeout),
        'anthropic': lambda: _anthropic_chat(system, user, model, timeout, schema),
    }
    raw = _with_timeout(calls[name], timeout + 2)
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f'The AI model returned invalid JSON: {exc}')
    if not isinstance(value, dict):
        raise LLMUnavailable('The AI model did not return a JSON object.')
    return value
