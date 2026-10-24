"""Bounded access to the local Ollama model. Every caller has a non-AI fallback."""
import json
import queue
import threading
from typing import Callable, Optional

DEFAULT_MODEL = 'llama3.2:3b'
HOST = 'http://127.0.0.1:11434'


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
        raise LLMUnavailable(f'The local model did not answer within {timeout:g} seconds.')
    ok, value = results.get()
    if not ok:
        raise LLMUnavailable(f'The local model is unavailable: {value}')
    return value


def status(model: str = DEFAULT_MODEL, timeout: float = 2.0) -> dict:
    """Report whether the local model can be reached; never raises."""
    def probe():
        import ollama
        listed = ollama.Client(host=HOST, timeout=timeout).list()
        return [m.get('name') or m.get('model') for m in listed.get('models', [])]
    try:
        models = _with_timeout(probe, timeout + 1)
    except LLMUnavailable as exc:
        return {'available': False, 'model': model, 'reason': str(exc)}
    found = any(name == model or name.split(':')[0] == model.split(':')[0] and name.endswith(model.split(':')[-1])
                for name in models if name)
    return {'available': found, 'model': model,
            'reason': None if found else f'Model {model} is not installed in Ollama.'}


def chat_json(system: str, user: str, *, model: str = DEFAULT_MODEL, timeout: float = 30.0) -> dict:
    """Ask for a JSON object; raise LLMUnavailable on timeout, error, or invalid JSON."""
    def call():
        import ollama
        client = ollama.Client(host=HOST, timeout=timeout)
        response = client.chat(model=model, format='json', options={'temperature': 0, 'seed': 7},
                               messages=[{'role': 'system', 'content': system},
                                         {'role': 'user', 'content': user}])
        return response['message']['content']
    raw = _with_timeout(call, timeout + 2)
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f'The local model returned invalid JSON: {exc}')
    if not isinstance(value, dict):
        raise LLMUnavailable('The local model did not return a JSON object.')
    return value
