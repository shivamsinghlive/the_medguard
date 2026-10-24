# MedGuard Explorer (prototype, branch `swathi-al`)

A research-first, Orange-style workspace for dataset readiness. You describe your study, load a CSV,
confirm the suggested plan, then explore connected widgets. Every number is computed from the loaded file
by the deterministic services in `src/services/`; nothing is hard-coded.

## Run it (Windows PowerShell, from the repo root)

One-time frontend build (needs Node 18+):

```powershell
cd frontend
npm install
npm run build
cd ..
```

Start the app:

```powershell
.\.venv\Scripts\python.exe src\explorer\server.py
```

Open http://127.0.0.1:8600. Stop with `Ctrl + C`.

Optional AI: run Ollama with `llama3.2:3b` (`ollama pull llama3.2:3b`). Without it the app uses
rule-based planning and summaries and says so in the header.

Frontend development with hot reload: keep the server running, then `cd frontend; npm run dev` and open
http://127.0.0.1:5173 (API calls are proxied to port 8600).

## How it works

| Layer | File | Role |
|---|---|---|
| Readiness engine | `src/services/readiness.py` | Class balance, group x outcome cells, intersections, single-feature leakage/rank, weak-signal note, feature profile, missingness gaps, correlations, distributions, PCA map |
| Existing engines | `input_validation`, `privacy_screening`, `representation` | File checks, identifier screening, representation (unchanged) |
| Planner | `src/explorer/planner.py` | Research idea -> outcome, groups, identifiers, focus groups (local AI + transparent rules; flags focus groups absent from the data) |
| Insights | `src/explorer/insights.py` | Widget board, answers to the research question, explanations (AI output checked against the facts; rule-based fallback) |
| API | `src/explorer/server.py` | Local FastAPI on 127.0.0.1:8600; data held in memory only |
| UI | `frontend/` | React + React Flow canvas + ECharts; click-to-filter linked selection; save/open workflow JSON; JSON report export |

## Privacy and honesty rules

- The local AI receives column names, the research text, and aggregate counts - never cell values.
- AI text is labelled unverified and replaced when it makes claims outside the computed facts.
- Flag thresholds are adjustable settings shown in the plan, not clinical or regulatory standards.
- Readiness evidence does not show that a model will be accurate, fair, or safe; that needs held-out evaluation.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\analysis\test_readiness.py tests\explorer
```
