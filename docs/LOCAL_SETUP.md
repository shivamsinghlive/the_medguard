# Local development

Python 3.11 environment: `.venv`. The original requirements had incompatible HTTPX constraints. Ollama is now pinned to 0.2.1 and ChromaDB to 1.0.0; PyArrow is pinned to 17.0.0 for NumPy 1.x compatibility. `requirements.lock.txt` captures the resolved environment on this Mac; it is not a cross-platform lock.

```bash
cd '/Users/shivam/Documents/sem 5 final sem masters/busparx/medguard'
uv venv --python python3.11 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
ollama pull llama3.2:3b
bash scripts/run_local.sh
```

Ollama must be running locally. The app opens at http://127.0.0.1:8501. Streamlit usage statistics and Chroma anonymized telemetry are disabled by the launcher and the server binds to localhost.

Use the bundled synthetic demos while addressing the critical audit findings in `DSX_AUDIT.md`. Successful startup does not validate the statistical or privacy claims. Google Fonts is still referenced by the original UI CSS, so the browser can make external font requests.

```bash
.venv/bin/python scripts/audit_repro.py
uv pip check --python .venv/bin/python
```

The diagnostic script reproduces defects in the current baseline, rather than asserting they have been fixed.

## Verified status and remaining limitation

- Onboarding and Demo 1 fallback rendering passed Streamlit AppTest.
- `llama3.2:3b` downloaded; Python-client generation returned `OK`.
- Embedding call failed: `This server does not support embeddings. Start it with --embeddings`.
- Therefore medical-document retrieval is not verified/working against the current service on port 11434. Resolve its embedding support (or use a dedicated compatible embedding service and update the knowledge-base configuration) before relying on Medical Advisor RAG. The existing shared service was not restarted or reconfigured.
