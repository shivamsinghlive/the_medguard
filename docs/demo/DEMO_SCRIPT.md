# MedGuard DS+X 2026 Demo Script

Target length: 3 minutes, in **MedGuard Explorer** (`bash scripts/run_explorer.sh`, then http://127.0.0.1:8600).
Turn "Local AI" off in the header and rehearse with networking off.

## 0:00-0:25 - The decision

> Healthcare teams often start modeling before they can answer a simpler question: what evidence does this dataset actually contain, for the question we care about? MedGuard builds a reviewable dataset-readiness record around that question, before training begins.

Type the research question: *Can we predict diabetes reliably for women in primary care?* Outcome `diabetes`, groups `women`. Choose the bundled **Diabetes Combined** dataset and show the accepted row and column counts.

> Uploaded files follow the same path. MedGuard validates raw CSV bytes once, and every check uses the exact table returned by validation. First-release limits: 25 MB, 200,000 rows, 500 columns.

## 0:25-0:45 - A plan you can see

Click **Plan my analysis**. Show the suggested outcome, groups, identifier, and the focus group taken from the question, each with its reason. Click **Run analysis**.

> The plan comes from transparent rules here; the local model is optional, and any role it suggests must exist in the file.

## 0:45-1:25 - Evidence without a verdict

Point to the four status tiles: one summary, measured once. Scroll the **workflow canvas**: zoom, pan, and use the minimap. Tangerine edges mark findings to review.

Double-click **Row map**. Show the readiness funnel (all rows, unique, complete, labelled) and click **No missing cells** to light up the rows that leave there. Scroll to zoom into the grid.

> Nothing is removed. The funnel describes how many rows pass each measured check, in sequence.

Use the arrow to **Representation**: observed shares, the 100-square view, and the non-missing denominator.

> Labels stay exactly as recorded. Without a supplied reference this is descriptive; with one, the gap is shown in percentage points, with no universal threshold and no fair or biased label.

## 1:25-2:00 - Linked filtering

Open **Distributions**, pick `age`, and drag across 45 to 55. Click **Filter the workspace**. Close the panel: the chip reads `age 44.6–54.4`, the row count drops, and every widget, tile, and answer recomputes for that subset. Click **Undo**.

> Every filter is a view of the same locked file. Undo and redo make each step reversible.

## 2:00-2:20 - Privacy honesty

Open **Identifier screen**. Show the coverage ring, the scanned columns, and the always-visible callout.

> This is deliberately called screening. It reports exactly how much it scanned and never certifies de-identification.

## 2:20-3:00 - Close

Scroll to **Prepare a reviewed copy**. Keep **Remove exact duplicate rows** and click **Generate preview**. Show the removed rows dropping out of the row map, the ledger (1,031 → 1,000), the before and after diff, and the two fingerprint identicons. Click **Accept for export** and point to the **ready to export** stamp. Download the JSON report.

> The source stays locked; the reviewed copy has its own fingerprint and is recorded in the report. Demographics, outcomes, predictions, and identifiers are never change targets, and SMOTE or demographic balancing are not offered, because a cleaner copy does not establish fairness or accuracy.

If time allows, click **Explain this view** in any panel.

> Explanations run only on request, receive aggregate facts rather than records, and fall back to a rule-based summary when the local model is off or unavailable.

## Before presenting

- Run `bash scripts/run_explorer.sh --build` once after pulling.
- Confirm Diabetes Combined reports 1,031 rows and the tour is dismissed (or clear site data to show it).
- Confirm all tests pass: `python -m pytest -q` and `cd frontend && npm run build`.
- Keep one exported JSON report ready as a backup.
- Rehearse with Wi-Fi disabled and "Local AI" off.
- The Streamlit workspace (`bash scripts/run_local.sh`) remains a fallback.
- Do not describe the screen as a fairness, privacy, HIPAA, FDA, or clinical-safety certification.

## Latest offline rehearsal

October 24, 2026 on `shivam/explorer-ui`: with "Local AI" off, Diabetes Combined loaded 1,031 rows, rule-based planning completed, and the canvas, row map zoom and funnel, histogram range filter, row-map selection filter, drill-down panels, tour, and reviewed-copy accept flow all worked. The earlier Streamlit rehearsal on merged `main` after S04 is unchanged.

Before submission, resolve the team-size and pre-existing-work items in [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).
