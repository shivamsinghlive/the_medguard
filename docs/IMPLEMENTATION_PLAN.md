# MedGuard implementation backlog

Working branch: `fix/audit-correctness`.
Baseline audit: `DSX_AUDIT.md`. That document describes the initial state; use this checklist for current progress.

## Principles to preserve

- Compute evidence deterministically from the original records. Preserve the input.
- Distinguish observations, assumptions, model explanations, and unknowns.
- Never infer clinical harm or model performance from representation alone.
- No fairness or privacy clearance when checks are missing or insufficient.
- Validate changes before claiming improvement; make previews reproducible.
- Keep the core demo usable without AI. Prioritize correctness, then visual polish.
- Deliver small commits with meaningful regression coverage and candid limitations.
- Target healthcare ML researchers reviewing dataset readiness before training.

## Ordered work

- [x] 1. Audit original data; remove replacement-data generation from the main workflow.
- [x] 2a. Remove independent synthetic generation from the audit path. Standalone generator remains unvalidated.
- [ ] 2b. Decide whether to retain or retire the separate synthetic generator; validate it if retained.
- [ ] 3. Remove invented harm and accuracy estimates from prompts, schemas, fallbacks, and UI.
- [ ] 4. Replace false FAIR verdicts with scoped representation findings and insufficient-evidence states.
- [ ] 5. Explicit column roles, category mappings, reference populations, support, and uncertainty.
- [ ] 6. Improve identifier-screening coverage and document its limits.
- [ ] 7. Remove unsupported synthetic privacy validation/clearance throughout the repository.
- [ ] 8. Correct compliance, anti-hallucination, clinical, and regulatory claims throughout README and UI. Main workflow privacy copy is partially corrected.
- [ ] 9. Prevent invalid SMOTE/label transformations; evaluate mitigation on untouched held-out data.
- [ ] 10. Context-aware cleaning with source-preserving previews, valid code, and tradeoff explanations.
- [x] 11a. Stable source fingerprint; no random generation on rerun; discard stale dataset results/selections.
- [ ] 11b. Include user context and model versions in AI cache identities.
- [ ] 12. Move expensive AI work out of automatic rendering; make explanations optional and cached.
- [ ] 13. CSV validation and edge-case coverage. Empty-column recommendation rendering is guarded in step 1.
- [ ] 14. Traceable RAG sources and evidence-linked explanations.
- [ ] 15. Restore embedding support and verify the complete RAG path. Dependency/startup fixes are already on main.
- [ ] 16. Separate audit engine, state, transformations, AI explanations, and presentation.
- [ ] 17. Broader regression suite, CI, benchmark fixtures, latency measurements, and source/data privacy tests.
- [ ] 18. Focus product scope on dataset readiness and representation auditing.
- [ ] 19. Redesign: instant demo, prioritized findings, cohort matrix, evidence detail, accessible visuals, preview/export.
- [ ] 20. Update README, project provenance, reuse eligibility, slides, demo video, and reproducible pitch.

## Step 1 acceptance evidence

`python -m pytest -q tests/test_original_audit.py`

Coverage: stable fingerprints distinguish changed values/schema/order; Demo 1 analyzes source row counts, duplicates, and missingness; unchanged reruns retain measurements; dataset changes invalidate modified-data and recommendation state; an all-missing column renders without requiring generated code. AI is deliberately unavailable in UI tests. No model claims are validated by these tests.

The original synthetic demo CSVs remain supported as input datasets. They are analyzed as supplied, without generating a second dataset. Existing transformation and fairness defects remain open and must not be presented as resolved.
