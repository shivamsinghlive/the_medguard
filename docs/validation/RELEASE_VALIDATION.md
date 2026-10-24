# W05 release validation

Independent acceptance pass of the first release at `main` `334fbee` (after S03), run on 2026-10-24.

**This is software acceptance testing, not clinical validation.** It checks that the deterministic audit behaves as specified on fabricated and bundled synthetic data. It does not show clinical safety, fairness, model performance, or de-identification.

## How to reproduce

```bash
python -m pytest -q tests                      # full suite, including acceptance
python -m pytest -q tests/analysis/test_release_acceptance.py
python tests/analysis/release_validation.py docs/validation/release_validation_results.json
```

No AI model, download, or network access is needed. The raw measurements are in [release_validation_results.json](release_validation_results.json).

## Release gates

[test_release_acceptance.py](../../tests/analysis/test_release_acceptance.py) sends raw CSV bytes through `validate_input` → `run_audit` → JSON/CSV export, which is the same path the workspace uses.

| Gate (from the handoff plan) | Result | Evidence |
|---|---|---|
| Original-data regressions | Pass | Source fingerprint, row count, duplicates and missing cells match the file read directly |
| Unavailable-harm regressions | Pass | `model_performance` is `not_measured`; no harm or accuracy figures appear in the report |
| Single-group, no-demographic, all-null cases | Pass | `review_needed`, `insufficient_evidence`, `insufficient_evidence`; status shown per attribute |
| Deterministic repeated results | Pass | Same bytes give identical JSON and CSV exports |
| Malformed input handling | Pass | Empty, header-only, ragged, duplicate-header, binary and non-UTF-8 files are rejected; `run_audit` refuses a rejected validation |
| Honest privacy coverage | Pass | Every row is screened; `certifies_deidentification` is false; limitations are included |
| Usable offline demo | Pass | Workspace demo renders with Ollama and outbound connections disabled |
| Export matches displayed measurements | Pass | JSON round-trips exactly; CSV cohort, finding and identifier rows match the report |
| Accepted preview export | Pass | Separate copy, `source_row_index` traceable, source file and fingerprint unchanged |

The full suite passed: 227 tests on Windows, Python 3.11.17, pandas 2.1.4.

## Known defects from DSX_AUDIT.md

| Original defect | Now |
|---|---|
| Generated copy audited instead of the source | Source records audited; fingerprint matches the file |
| Single-gender dataset reported FAIR | `review_needed` with a `single_group` finding |
| No demographic columns reported FAIR | `insufficient_evidence` |
| Email after row 100 passed the scanner | Found (`email_pattern`); value not echoed in exports |
| Numeric patient ID plus age 95 passed | Found (`identifier_column_name`, `age_over_89`) |
| SMOTE could interpolate outcomes | SMOTE and balancing are refused; outcome changes are blocked by default |
| Fabricated performance gap and affected patients | Reported as not measured |
| Hard-coded 50/50 target and "FDA 5%" rule | A reference is used only if the user supplies one; differences are reported, not judged |
| `1` silently mapped to Male | Recorded codes kept as labels |

## Latency and dataset size

Median of 3 runs per stage. Fabricated data, 12 columns, one machine (AMD64 laptop, Windows 11). Timings vary by machine and are not guarantees.

| Rows | CSV size | Validate | Screen | Representation | Full audit | Preview | End to end* |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.07 MB | 7 ms | 50 ms | 2 ms | 65 ms | 20 ms | 0.07 s |
| 10,000 | 0.67 MB | 42 ms | 371 ms | 5 ms | 445 ms | 71 ms | 0.49 s |
| 50,000 | 3.3 MB | 218 ms | 1.96 s | 19 ms | 2.21 s | 297 ms | 2.4 s |
| 200,000 (row limit) | 13.4 MB | 888 ms | 7.96 s | 69 ms | 7.97 s | 1.06 s | 8.9 s |

\*Validate + full audit + export. Export took under 1 ms at every size.

Identifier screening is about 90% of audit time. It grows roughly linearly with rows. At the 200,000-row limit, a user waits about 9 seconds per rerun of the workspace. Wider files (up to the 500-column limit) were not measured and will be slower.

## Bundled demo datasets

All 5 synthetic CSVs are accepted. With their `sex`/`race_ethnicity` columns selected and no reference supplied, representation is `descriptive_only` for each.

Identifier screening flags `patient_id` in every file (`identifier_column_name`, kind `record_identifier`). In 3 files it also flags `unique_values`. The other two contain duplicate rows, so their IDs are not all distinct. Synthetic IDs like `SYNTH_001` are not real identifiers, but the screen cannot know that, and flagging them is the intended behaviour.

## Where screening misses or over-flags

These probes ([release_validation.py](../../tests/analysis/release_validation.py)) document expected behaviour; they are not pass/fail gates.

| Probe | Flagged? | Meaning |
|---|---|---|
| Name without a title ("John Smith") in free text | No | **Missed** |
| Street address value ("12 Main Street") | No | **Missed** |
| ZIP-code values in a column named `region` | No | **Missed** |
| 9-digit numeric IDs, only 2 rows, neutral column name | No | **Missed** (too few rows for the distinct-value check) |
| Unhyphenated SSN in text ("ssn 123456789") | No | **Missed** |
| `drug_name` column | No | Correctly not flagged |
| 30 distinct lab codes (`L000`–`L029`) | `unique_values` | **False positive** |
| Firmware version `10.0.0.1` | `ip_address_pattern` | **False positive** (shape is identical to an IP) |

Unit tests in `tests/analysis/` add more positives (emails, SSN/phone shapes, titled names, URLs, dates, ages over 89) and benign lookalikes (`120/80`, years, `MS Clinic`, `stage`, `dosage`, `birth_weight`) that behave as intended.

## Limitations of this validation

- All data is fabricated or bundled synthetic data. No real clinical dataset was used.
- Screening is heuristic. A result of "no patterns found" is not de-identification under HIPAA Safe Harbor or Expert Determination.
- Representation results describe counts. They do not measure model fairness, outcome disparities, or clinical harm, and no uncertainty intervals are computed.
- Latency was measured on one machine with 12-column data.
- The UI was exercised through Streamlit AppTest, not a real browser, and accessibility was not assessed here.
