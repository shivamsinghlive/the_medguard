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

from services.privacy_screening import screen_identifiers
from services.representation import analyze_representation
from utils.audit_input import dataset_fingerprint


REPORT_SCHEMA_VERSION = "1.0"


def run_audit(
    df: pd.DataFrame,
    *,
    demographic_columns: Sequence[str],
    reference_proportions: Optional[Mapping] = None,
    source_type: str,
    input_validation: dict,
) -> dict:
    """Package evidence from the validated frame without changing it.

    Upload callers must pass the validation result returned alongside ``df`` by
    ``validate_input``. Requiring it here prevents a rejected or independently
    re-parsed file from quietly reaching analysis.
    """

    if input_validation.get("status") != "accepted":
        raise ValueError("run_audit requires an accepted input-validation result.")
    if input_validation.get("row_count") != len(df):
        raise ValueError("The validated row count does not match the analysis frame.")
    if input_validation.get("column_count") != len(df.columns):
        raise ValueError("The validated column count does not match the analysis frame.")

    before = dataset_fingerprint(df)
    identifier_screening = screen_identifiers(df)
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
        "input_validation": input_validation,
        "quality": {
            "missing_cells": int(df.isna().sum().sum()),
            "columns_with_missing_values": len(missing_by_column),
            "missing_by_column": missing_by_column,
            "duplicate_rows": int(df.duplicated(keep=False).sum()),
        },
        "representation": representation,
        "identifier_screening": identifier_screening,
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


def reviewed_copy_csv(frame: pd.DataFrame) -> str:
    """Export a preview copy while retaining traceable source index labels."""

    index_label = "source_row_index"
    while index_label in frame.columns:
        index_label = f"_{index_label}"
    return frame.to_csv(index=True, index_label=index_label)


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
    screening = report["identifier_screening"]
    for finding in screening["findings"]:
        writer.writerow(
            {
                "row_type": "identifier_finding",
                "column": finding["column"],
                "status": screening["status"],
                "code": finding["code"],
                "priority": finding["priority"],
                "title": finding["title"],
                "summary": finding_summary(finding),
                "suggested_action": finding["suggested_action"],
            }
        )
    validation = report["input_validation"]
    for issue_type in ("errors", "warnings"):
        for issue in validation[issue_type]:
            writer.writerow(
                {
                    "row_type": f"validation_{issue_type[:-1]}",
                    "status": validation["status"],
                    "code": issue["code"],
                    "title": issue["message"],
                }
            )
    change_preview = report.get("change_preview")
    if change_preview:
        accepted = bool(change_preview.get("accepted_for_export", False))
        for action in change_preview["actions"]:
            warnings = "; ".join(action["warnings"])
            writer.writerow(
                {
                    "row_type": "change_action",
                    "status": action["status"],
                    "code": action["action"],
                    "title": action["reason"] or (
                        "Accepted preview action" if accepted else "Unaccepted preview action"
                    ),
                    "summary": json.dumps(action["evidence"], sort_keys=True),
                    "suggested_action": warnings,
                }
            )
    return output.getvalue()
