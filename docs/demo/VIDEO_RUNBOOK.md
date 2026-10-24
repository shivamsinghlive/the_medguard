# Setup and use video runbook

Target length: 3–4 minutes. Record at 1440×900 or higher with browser zoom at 100%. Use only the bundled synthetic dataset. Keep notifications hidden and Ollama stopped so the fallback is reproducible.

## Preparation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
streamlit run src/ui/audit_workspace.py
```

Before recording, close unrelated tabs, open `http://localhost:8501`, and keep a JSON export ready as backup.

## Recording sequence

### 0:00–0:25 — Purpose

Show the hero and sidebar steps.

> MedGuard creates a reviewable dataset-readiness record before healthcare model training. It measures evidence, preserves the source, and states what remains unknown.

### 0:25–0:55 — Setup and input

Briefly show the README run command, then return to the guided demo and its accepted dimensions.

> The demo uses a bundled synthetic cohort. Uploaded CSVs go through bounded structural validation and potential-identifier screening before analysis.

### 0:55–1:35 — Representation and privacy

Open **Cohort evidence**, enable the illustrative reference, and open **Identifier screening**.

> The reference is explicitly supplied for illustration. The difference remains descriptive. Screening reports potential signals and coverage; it does not certify de-identification.

### 1:35–2:20 — Reviewable change

Select **Remove exact duplicate rows**, generate the preview, show before/after evidence, and accept it.

> The preview runs on a separate copy. Protected roles cannot be selected, and MedGuard makes no accuracy or fairness claim about the change.

### 2:20–2:50 — AI-unavailable path

Click **Generate optional explanation** with Ollama stopped and wait for the deterministic fallback.

> AI is optional and never blocks the audit. The local prompt excludes original records and identifying schema details. Failed or unsafe output becomes a visible fallback.

### 2:50–3:20 — Export and limits

Show JSON/CSV downloads and the footer limitations.

> The export preserves the measured evidence, preview state, and optional explanation state. MedGuard is not clinical validation, privacy certification, or a fairness verdict.

## Recording checks

- Text is readable without pausing the video.
- No real patient data, local file paths, notifications, API keys, or terminal secrets are visible.
- The fallback state, limitations, and source-preservation language are visible.
- Captions match the spoken claim language.
- The final description links the repository, deployed demo, slide deck, and provenance section.
