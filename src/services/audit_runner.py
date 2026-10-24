"""Shivam-owned orchestration between deterministic services and the UI.

This module does not change the representation contract. It packages source
identity, basic dataset-quality evidence, representation results, and honest
unavailable states into exportable reports.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Mapping, Optional, Sequence

import pandas as pd

from services.representation import analyze_representation
from utils.audit_input import dataset_fingerprint


REPORT_SCHEMA_VERSION = "1.0"


def run_audit(
    df: pd.DataFrame,
    *,
    demographic_columns: Sequence[str],
    reference_proportions: Optional[Mapping] = None,
    source_type: str,
) -> dict:
    """Run deterministic evidence available before W02 screening lands."""

    before = dataset_fingerprint(df)
    representation = analyze_representation(
        df,
        demographic_columns=demographic_columns,
        reference_proportions=reference_proportions,
    )
    after = dataset_fingerprint(df)
    if after != before:
        raise RuntimeError("Audit services changed the source dataset.")

    missing_by_column = {
        str(column): int(count)
        for column, count in df.isna().sum().items()
        if int(count) > 0
    }
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "dataset": {
            "fingerprint": before,
            "source_type": source_type,
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
        },
        "quality": {
            "missing_cells": int(df.isna().sum().sum()),
            "columns_with_missing_values": len(missing_by_column),
            "missing_by_column": missing_by_column,
            "duplicate_rows": int(df.duplicated(keep=False).sum()),
        },
        "representation": representation,
        "identifier_screening": {
            "status": "not_run",
            "reason": "W02 identifier screening is not integrated yet.",
            "certifies_deidentification": False,
        },
        "model_performance": {
            "status": "not_measured",
            "reason": (
                "No held-out predictions or model-evaluation protocol were "
                "provided to this dataset review."
            ),
        },
    }
    json.dumps(report, allow_nan=False)
    return report


def finding_summary(finding: dict) -> str:
    """Create UI copy from contracted evidence when `summary` is absent."""

    if finding.get("summary"):
        return str(finding["summary"])
    evidence = finding.get("evidence", {})
    code = finding.get("code")
    if code == "single_group":
        count = evidence.get("observed_count", "the available")
        return f"All {count} observed records use one recorded group label."
    if code == "missing_reference_group":
        groups = ", ".join(map(str, evidence.get("missing_groups", []))) or "Expected groups"
        return f"No observed rows match these supplied reference groups: {groups}."
    if code == "group_not_in_reference":
        groups = ", ".join(map(str, evidence.get("groups", []))) or "Recorded groups"
        return f"These recorded groups are absent from the supplied reference: {groups}."
    if code == "no_observed_values":
        missing = evidence.get("missing_count", "All")
        return f"The selected column has no observed values; {missing} values are missing."
    return f"Review the measured evidence for {finding.get('column', 'this attribute')}."


def report_json(report: dict) -> str:
    """Return stable, strict JSON for download or review."""

    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False)


def report_csv(report: dict) -> str:
    """Flatten cohort evidence and findings into one reviewable CSV."""

    output = io.StringIO(newline="")
    fields = [
        "row_type", "column", "status", "code", "priority", "label", "count",
        "proportion", "reference_proportion", "difference_pp", "title", "summary",
        "suggested_action",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    representation = report["representation"]
    for attribute in representation["attributes"]:
        for group in attribute["groups"]:
            writer.writerow(
                {
                    "row_type": "cohort",
                    "column": attribute["column"],
                    "status": attribute["status"],
                    "label": group["label"],
                    "count": group["count"],
                    "proportion": group["proportion"],
                    "reference_proportion": group["reference_proportion"],
                    "difference_pp": group["difference_pp"],
                }
            )
    for finding in representation["findings"]:
        writer.writerow(
            {
                "row_type": "finding",
                "column": finding["column"],
                "status": representation["status"],
                "code": finding["code"],
                "priority": finding["priority"],
                "title": finding["title"],
                "summary": finding_summary(finding),
                "suggested_action": finding["suggested_action"],
            }
        )
    return output.getvalue()
