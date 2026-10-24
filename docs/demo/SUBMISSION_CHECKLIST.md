# DS+X 2026 submission checklist

Checked against the official DS+X pages on October 24, 2026. The submission deadline shown by Devpost is **October 25, 2026 at 10:00 a.m. EDT**.

## Resolve before submission

| Item | Status | Required action |
|---|---|---|
| Team size | **Blocked** | The [event overview](https://ds-x-hackathon-2026.devpost.com/) lists teams of 3–5. The current plan names Shivam and Swathi. Add a registered teammate or obtain a written organizer exception. |
| Pre-existing work | **Needs organizer answer** | The [published rules](https://ds-x-hackathon-2026.devpost.com/rules) do not state a reuse policy. Disclose baseline commit `d3a1072` and ask whether the October 24 work is eligible. Keep the written answer. |
| Registration | **Verify manually** | The overview says Devpost registration alone is insufficient and links a separate registration form. Confirm every teammate completed it. |
| Source-grounded RAG | **Out of scope** | W04 is absent from `main`. Keep RAG disabled and do not claim medical-source grounding. |

Do not submit until the first three rows are resolved. They are event-administration questions, not code defects.

## Required deliverables

The [event overview](https://ds-x-hackathon-2026.devpost.com/) requests these items:

- [x] Public GitHub repository with a detailed README.
- [ ] Deployed application link, if applicable. Use the synthetic demo only; do not upload patient data.
- [ ] Slide deck. Build from [`SLIDES_OUTLINE.md`](SLIDES_OUTLINE.md).
- [ ] Setup and use video. Record from [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md).
- [ ] Devpost project entry with the Health+BioTech track and accurate limitations.

## Release evidence

- [x] `main` contains Swathi W05 release validation (`7d3ad51`).
- [x] `main` contains Shivam S04 optional AI (`c9545a9`).
- [x] Guided demo renders 1,200 synthetic rows and 14 columns.
- [x] Browser rehearsal completed with Ollama unavailable on October 24, 2026. The explanation request timed out visibly and returned the deterministic fallback; the audit and exports remained available.
- [x] No AI call occurs during page load or deterministic audit execution.
- [x] Run `python -m pytest -q` on the release-polish branch: 243 passed on October 24, 2026.
- [ ] Export one JSON report and keep it with the presenter as a backup.
- [ ] Test the deployed URL in a private browser window and at a narrow viewport.

Final test result before submission: rerun after this branch merges and replace the branch result if it changes.

## Claim check

Use these phrases:

- “dataset-readiness evidence”
- “potential identifier screening”
- “descriptive representation measurement”
- “source-preserving preview”
- “optional, unverified local explanation”

Avoid these claims:

- fair, unbiased, safe, HIPAA compliant, de-identified, clinically validated
- improved accuracy or reduced patient harm
- automatic mitigation, demographic balancing, or recommended recruitment targets
- medically grounded AI explanation while W04 is absent

## Final five-minute check

1. Open the guided demo from a clean session.
2. Confirm 1,200 rows, 14 columns, `sex` selected, and two identifier signals.
3. Open cohort, identifier, and quality evidence.
4. Generate and accept an exact-duplicate preview.
5. Request the optional explanation with Ollama stopped and show the fallback.
6. Download JSON and CSV evidence.
7. Confirm the footer limitations are visible.
