# MedGuard Explorer

A research-first, Orange-style workspace for dataset readiness. You describe your study, load a CSV,
confirm the suggested plan, then explore a zoomable canvas of linked widgets. Every number is computed from
the loaded file by the deterministic services in `src/services/`; nothing is hard-coded.

## Run it

macOS or Linux, from the repo root (builds the front end on first run; needs Node 18+):

```bash
bash scripts/run_explorer.sh            # add --build to force a fresh front-end build
```

Windows PowerShell:

```powershell
cd frontend; npm install; npm run build; cd ..
.\.venv\Scripts\python.exe src\explorer\server.py
```

Open http://127.0.0.1:8600. Stop with `Ctrl + C`.

## Optional AI

Everything works without AI; planning and summaries then use transparent rules. Choose a provider with
environment variables:

| Setting | Local (default) | Groq (Llama) | Claude |
|---|---|---|---|
| `MEDGUARD_AI_PROVIDER` | `ollama` | `openai` | `anthropic` |
| `MEDGUARD_AI_MODEL` | `llama3.2:3b` | `llama-3.1-8b-instant` | `claude-opus-5-5` (or `claude-haiku-5-5`) |
| `MEDGUARD_AI_BASE_URL` | – | `https://api.groq.com/openai/v1` | – |
| `MEDGUARD_AI_API_KEY` | – | your Groq key | your Anthropic key |

Locally, run Ollama with `llama3.2:3b` (`ollama pull llama3.2:3b`). Any OpenAI-compatible endpoint works with
`openai` by changing the base URL. Claude requests use structured outputs, low effort, and server-side
refusal fallbacks on models that support them. A public server (`MEDGUARD_PUBLIC=1`) never uses a local
Ollama model; it uses a hosted provider when one is configured, and says which in the header and banner.

Front-end development with hot reload: keep the server running, then `cd frontend && npm run dev` and open
http://127.0.0.1:5173 (API calls are proxied to port 8600).

## What you can do

- **Zoom and pan everywhere**: the workflow canvas (minimap, fit-to-view, arrow keys), the row map (wheel
  zoom, drag to pan, minimap), and charts (wheel zoom plus sliders on histograms, heatmaps, and the 2-D map).
- **Brush to filter**: drag across a histogram for a numeric range, or select rows on the row map or the 2-D
  map. Click bars for category filters. Every widget recomputes for the subset; chips and undo/redo show and
  reverse each step. The stored dataset never changes.
- **Drill down**: double-click a card (or press Enter) for a full-screen panel with Chart, Table, Evidence,
  and Limits tabs. Panels are linkable as `#/w/<widget>`.
- **Prepare a reviewed copy**: preview allowlisted cleaning actions on a separate copy, watch removed rows drop
  out, compare before and after, then accept it for the report and download the CSV.
- **Guided tour**: runs once on first visit; replay it from "Tour" in the header.

## How it works

| Layer | File | Role |
|---|---|---|
| Readiness engine | `src/services/readiness.py` | Class balance, group x outcome cells, intersections, single-feature leakage/rank, weak-signal note, feature profile, missingness gaps, correlations, distributions, PCA map |
| Audit engines | `audit_runner`, `input_validation`, `privacy_screening`, `representation`, `change_preview` | File checks, identifier screening, representation, quality counts, reviewed-copy previews (unchanged) |
| Evidence payloads | `src/ui/visuals/payloads.py` | Status strip, row map and readiness funnel, cohort dumbbell/waffle, coverage, change map; shared with the Streamlit workspace |
| Planner | `src/explorer/planner.py` | Research idea -> outcome, groups, identifiers, focus groups (local AI + transparent rules; flags focus groups absent from the data) |
| Insights | `src/explorer/insights.py` | Widget board, answers to the research question, explanations (AI output checked against the facts; rule-based fallback) |
| API | `src/explorer/server.py` | Local FastAPI on 127.0.0.1:8600; label, range, and row filters; preview/accept/copy endpoints; data held in memory only |
| UI | `frontend/` | React + React Flow canvas + ECharts; daylight palette with dark mode; linked filtering; drill-down panels; tour |

## Privacy and honesty rules

- The AI (local or hosted) receives column names, the research text, and aggregate counts - never rows or
  cell values. With a hosted provider, that text leaves the server; the public banner says so.
- AI text is labelled unverified and replaced when it makes claims outside the computed facts.
- Status chips use the contract vocabulary. Nothing is shown as a green pass; "no patterns found" is not
  de-identification. Tangerine marks review evidence only.
- Flag thresholds are adjustable settings shown in the plan, not clinical or regulatory standards.
- Readiness evidence does not show that a model will be accurate, fair, or safe; that needs held-out evaluation.

## Tests

```bash
.venv/bin/python -m pytest -q tests/analysis/test_readiness.py tests/explorer
cd frontend && npm run build   # includes the TypeScript check
```
