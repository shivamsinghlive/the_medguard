#!/usr/bin/env bash
# Build the Explorer front end if needed, then serve it with the local API on 127.0.0.1:8600.
set -euo pipefail
cd "$(dirname "$0")/.."
export ANONYMIZED_TELEMETRY=False

if [[ ! -f frontend/dist/index.html || "${1:-}" == "--build" ]]; then
  (cd frontend && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } && npm run build)
fi

exec .venv/bin/python src/explorer/server.py
