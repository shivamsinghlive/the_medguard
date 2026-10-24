---
title: MedGuard Explorer
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Dataset-readiness evidence for healthcare ML, not verdicts
---

# MedGuard Explorer

Start from a research question, load a healthcare CSV, and explore a zoomable canvas of linked evidence:
class balance, coverage of the groups you care about, missing values, duplicates, leakage signals, and
potential identifiers. Every number is computed from the loaded file.

**Public demo.** Use the bundled synthetic datasets or data that is already de-identified. Do not upload
patient records. Files are processed in server memory, never written to disk, kept apart from other
visitors, and deleted after 60 minutes. The local AI model is not part of this demo; planning and
summaries use transparent rules.

MedGuard describes a dataset. It does not validate a model, certify fairness, or establish
de-identification.

Source: https://github.com/shivamsinghlive/the_medguard
