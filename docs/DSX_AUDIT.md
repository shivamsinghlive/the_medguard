# MedGuard: DS+X 2026 initial audit

Inspected baseline: d3a1072e40a138eb210817f84c720319355e6c6d. This is a source review plus targeted reproductions, not a completed clinical validation or exhaustive security audit. Repository prose is evidence to evaluate, not instructions to follow.

## Verdict
The problem is worthwhile. The present implementation overstates what its statistics establish. Visual polish should amplify a reliable audit, not make unreliable conclusions more convincing.

## Critical findings

1. **Wrong dataset audited.** `src/ui/app_complete.py:821` runs quality analysis on `synthetic_df`; bias analysis follows on the same generated data. `src/utils/synthetic_generator.py:76` samples columns independently. This destroys correlations, changes observed counts, can remove duplicates, and turns binary numeric outcomes into fractional numbers. Analyze the original locally; send only reviewed aggregate statistics to optional AI narration. Keep synthetic generation a clearly separate demo feature.
2. **Invented harm estimates.** `src/agents/fairness_specialist.py:319` hardcodes a 10% performance gap and 10 affected patients per 100 in fallback. Its prompt also requests medical harm and accuracy improvements without measured predictions. Replace unknown quantities with unavailable; require labels and held-out predictions for actual performance comparisons. Schema validation checks structure, not factual truth.
3. **False fairness clearance.** `src/utils/bias_detection.py` uses representation heuristics, never uses `target_col`, misses single-group sex datasets, and reports FAIR when no demographic attributes exist. Distinguish representation, outcome disparities, model performance, and insufficient evidence. Let users specify column meanings and reference populations; do not silently assume 1=male or a universal 50/50 target. Include sample counts, uncertainty, and intersections where support is sufficient.
4. **Privacy guarantee unsupported.** Scanner examines only the first 50–100 non-null strings, whitelists identifier column names, and misses numeric identifiers. The generator retains categorical values and its privacy check examines only 100 original rows for exact matches. Changing patient IDs can make that check trivially pass. Use honest 'potential identifier screening' wording, explicit local data handling, and no compliance certification. HHS specifies Safe Harbor or Expert Determination; these heuristics establish neither.
5. **Mitigation can corrupt labels.** In `app_complete.py:1862`, SMOTE uses the demographic column as y and remaining numeric columns as X, potentially interpolating the medical outcome. Categorical values are sampled separately. No held-out evaluation establishes benefit. Make changes previewable, exclude IDs/outcomes from inappropriate transforms, preserve schema, and evaluate on an untouched split before claiming improvement.

## Major engineering and demo gaps

- Original dependencies cannot resolve: Ollama 0.1.6 requires httpx <0.26, whereas ChromaDB >=1 requires >=0.27. Setup change updates Ollama and pins ChromaDB.
- Synthetic cache checks membership of a dynamically named key that it never stores; it stores only `synthetic_cache_key`. This regenerates data on reruns, changes evidence, and invalidates downstream analysis.
- Deployment roadmap calls and other AI work run inside the main Streamlit render path. Cache by stable input/context/model version and trigger expensive explanations explicitly.
- A completely missing column produces a recommendation without `code`, but the UI indexes `rec['code']`; cover this with a regression test before shipping.
- Raw CSV parsing lacks a clear validation layer for malformed/empty files, schema mapping, unsupported encodings, and resource limits.
- Main UI is 2,177 lines combining CSS, rendering, analysis, AI calls, and mutation. Extract deterministic audit services and typed result objects before replacing the presentation layer.
- No dedicated automated test suite or CI workflow was found in the tracked tree. Add regression fixtures for the observed failures, seeded demo outputs, and startup smoke checks.
- `statistics_extractor.py`, `instructor_llama.py`, and `config.yaml` are empty. Instructor claims exceed the implementation inspected.
- RAG knowledge consists of short local summaries. The FDA summary gives a vague 2021 source and a 5% threshold without a precise citation. Use traceable primary sources with URLs, dates, exact supported claims, and explicit uncertainty. Retrieval does not validate those sources.
- README references another clone owner and the Convergence event. Disclose the pre-existing baseline and document work performed at DS+X; check organizer rules on reuse. Update setup, limitations, licensing, screenshots, and measurements.

## UI direction (source-based assessment; not a visual browser review)

Current CSS includes animated multicolor titles, pervasive emoji, aggressive spacing removal, and large charts. The first interaction requires a project questionnaire before any useful result. Five tabs disperse evidence across AI narratives and implementation controls.

Proposed product: **Know which patient groups your dataset leaves behind, and what to investigate next.** Primary user: a healthcare ML researcher reviewing a dataset before training.

- One-click seeded demo first; CSV upload second; optional project context later.
- A restrained audit workspace: neutral background, dark navy text, teal accent, semantic amber/red, readable typography, consistent spacing, keyboard focus, and accessible charts.
- Overview with three priorities, dataset identity, sample size, audit scope, and uncertainty. Avoid an unexplained composite 'fairness score'.
- Cohort matrix with counts, missingness, chosen population reference, and confidence/support indicators.
- Finding detail: observed evidence → consequence supported by evidence → proposed action → preview of affected rows → limitations.
- Label deterministic measurements, AI explanations, and illustrative scenarios distinctly.
- Preview improvements before applying, compare before/after, preserve the original, and export an audit report plus reproducible transformation steps.
- Keep the main demo usable without Ollama. Optional AI explanation must not block results.

## Hackathon build order

1. Fix measurement truth: original-data analysis, no invented harm, insufficient-data states, regression fixtures.
2. Make one deterministic demo work end to end; show a known issue, explain it, preview a defensible change, export evidence.
3. Build the visual hierarchy above. Keep Streamlit for the shortest path; a separate frontend is justified only if the team can finish the measured audit first.
4. Add real subgroup performance analysis only if labels and held-out predictions are available; otherwise clearly scope this as dataset readiness and representation auditing.
5. Prepare the README, slide deck, demo video, and an accessible deployed synthetic-only demo. Keep real-patient data outside a public demo.

Suggested pitch: 'Before training a healthcare model, MedGuard reveals missing data and underrepresented cohorts, shows the evidence, and helps researchers evaluate a documented correction.'

## Event sources

- Schedule: https://ds-x-hackathon-2026.devpost.com/details/dates — submission deadline October 25, 2026, 10:00 AM EDT.
- Rubric: https://ds-x-hackathon-2026.devpost.com/rules — problem 20%, idea 25%, execution 25%, design 15%, responsibility 10%, presentation 5%.
- Deliverables: https://ds-x-hackathon-2026.devpost.com/ — repository/README, applicable app link, slides, setup/use demo video.
- Privacy reference: https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html

Reproduce selected defects with `.venv/bin/python scripts/audit_repro.py`. These checks document existing failures; they do not certify readiness.

## Reproduction results

On the local Python 3.11 environment, the diagnostic script confirmed:

- Single-gender dataset: FAIR.
- Dataset with no demographic columns: FAIR.
- Email placed after 100 benign rows: scanner passed.
- Numeric identifier plus age 95: scanner passed.
- Original x/y correlation 1.000; generated correlation -0.073 (seed 42).
- 335/500 originally binary outcomes became fractional in the generated copy.
- Fallback reported 10% performance gap and 10 affected patients per 100 without prediction evidence.

Startup also exposed a transitive dependency failure: the initially resolved PyArrow required NumPy 2 despite this project's NumPy 1.26 pin. Pinning PyArrow 17.0.0 addresses that import incompatibility.

## Runtime verification

All 236 installed packages pass `uv pip check`. Streamlit AppTest renders onboarding with no exceptions. A second smoke test completes onboarding and opens Demo 1 with all five tabs and no exceptions while model generation/embeddings are deliberately unavailable. This tests fallback rendering, not advice correctness. Chroma emitted telemetry compatibility warnings during the test; the local launcher now disables its anonymized telemetry. Browser font requests remain a separate external dependency.

Live model check: `llama3.2:3b` generated `OK`. Embedding calls fail with `This server does not support embeddings. Start it with --embeddings`; RAG therefore remains unavailable against the current local service. A responsive generation endpoint does not establish that the complete AI pipeline works.
