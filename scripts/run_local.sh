#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export ANONYMIZED_TELEMETRY=False
exec .venv/bin/python -m streamlit run src/ui/audit_workspace.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false "$@"
