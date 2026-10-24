# MedGuard DS+X 2026 Demo Script

Target length: 3 minutes. Run the guided demo with networking and AI services turned off.

## 0:00-0:25 - The decision

> Healthcare teams often start modeling before they can answer a simpler question: what evidence does this dataset actually contain? MedGuard creates a reviewable dataset-readiness record before training begins.

Point to the four promises in the hero: deterministic checks, source preservation, offline operation, and explicit unknowns.

## 0:25-0:55 - Trusted input

Keep **Guided demo** selected. Explain that it is a bundled synthetic cohort. Show the accepted row and column counts.

> Uploaded files follow the same path. MedGuard validates raw CSV bytes once and every downstream check uses the exact table returned by validation.

Mention the bounded first-release limits: 25 MB, 200,000 rows, and 500 columns.

## 0:55-1:35 - Representation without a verdict

Keep `sex` selected as the demographic column. Open **Cohort evidence** and show the observed shares and nonmissing denominator.

> MedGuard preserves recorded labels. It never silently turns a code such as 1 into a demographic category. Without a supplied reference, this is descriptive evidence.

Enable the illustrative 50/50 reference.

> The percentage-point difference is calculated, but MedGuard does not invent a universal threshold or call the dataset fair or biased.

## 1:35-2:10 - Privacy honesty

Open **Identifier screening**. Show coverage, matched signals, and limitations.

> This is deliberately called screening. It detects potential identifiers using documented heuristics, reports exactly how much it scanned, and always states that it does not certify de-identification.

## 2:10-2:35 - Reviewable evidence

Open **Data quality** and then download the JSON report.

> The interface and export share the same deterministic result. A reviewer can inspect counts, findings, limitations, coverage, and the dataset fingerprint without relying on an AI-generated conclusion.

## 2:35-3:00 - Close

Scroll to **Changes to the dataset**.

> Automatic mitigation stays disabled. Our next service creates a separate preview for a narrow allowlist of changes while protecting outcomes, identifiers, and demographic columns. MedGuard makes uncertainty visible and keeps consequential decisions with the researcher.

## Before presenting

- Start from `streamlit run src/ui/audit_workspace.py`.
- Confirm the guided demo reports 1,200 rows.
- Confirm all tests pass.
- Keep one exported JSON report ready as a backup.
- Rehearse with Wi-Fi disabled.
- Do not describe the screen as a fairness, privacy, HIPAA, FDA, or clinical-safety certification.
