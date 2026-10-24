"""Integration tests for representation, evidence packaging, and exports."""

import csv
import io
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from services.audit_runner import (
    finding_summary, report_csv, report_json, reviewed_copy_csv, run_audit,
)
from services.change_preview import preview_changes
from services.input_validation import validate_input
from utils.audit_input import dataset_fingerprint


def accepted_result(frame):
    return {"status": "accepted", "row_count": len(frame), "column_count": len(frame.columns),
            "byte_count": 0, "limits": {}, "errors": [], "warnings": [], "limitations": []}


def test_validated_bytes_feed_the_exact_checked_frame_to_the_runner():
    raw = b"sex,outcome,notes\nMale,1,ok\nFemale,0,contact person@example.org\nFemale,1,ok\n,0,ok\n"
    validation, frame = validate_input(raw)
    before = frame.copy(deep=True)
    fingerprint = dataset_fingerprint(frame)

    report = run_audit(
        frame,
        demographic_columns=["sex"],
        source_type="test_fixture",
        input_validation=validation,
    )

    pd.testing.assert_frame_equal(frame, before)
    assert report["dataset"]["fingerprint"] == fingerprint
    assert report["quality"] == {
        "missing_cells": 1,
        "columns_with_missing_values": 1,
        "missing_by_column": {"sex": 1},
        "duplicate_rows": 0,
    }
    assert report["representation"]["status"] == "descriptive_only"
    assert report["input_validation"] == validation
    assert report["identifier_screening"]["status"] == "review_needed"
    assert any(f["code"] == "email_pattern" for f in report["identifier_screening"]["findings"])
    assert report["identifier_screening"]["certifies_deidentification"] is False
    assert report["model_performance"]["status"] == "not_measured"


def test_runner_accepts_all_w01_finding_codes_without_summary_field():
    cases = {
        "single_group": (
            pd.DataFrame({"group": ["A", "A"]}), None, "All 2 observed records"
        ),
        "missing_reference_group": (
            pd.DataFrame({"group": ["A", "A"]}), {"group": {"A": 0.5, "B": 0.5}}, "B"
        ),
        "group_not_in_reference": (
            pd.DataFrame({"group": ["A", "B"]}), {"group": {"A": 1.0}}, "B"
        ),
        "no_observed_values": (
            pd.DataFrame({"group": [None, None]}), None, "no observed values"
        ),
    }
    observed = {}
    for frame, reference, _ in cases.values():
        report = run_audit(
            frame,
            demographic_columns=["group"],
            reference_proportions=reference,
            source_type="test_fixture",
            input_validation=accepted_result(frame),
        )
        for finding in report["representation"]["findings"]:
            summary = finding_summary(finding)
            assert summary
            observed[finding["code"]] = summary
    assert set(cases) <= set(observed)
    for code, (_, _, expected_text) in cases.items():
        assert expected_text.lower() in observed[code].lower()


def test_gap_is_exported_without_becoming_a_flag():
    frame = pd.DataFrame({"sex": ["Male"] * 73 + ["Female"] * 27})
    report = run_audit(
        frame,
        demographic_columns=["sex"],
        reference_proportions={"sex": {"Male": 0.5, "Female": 0.5}},
        source_type="test_fixture",
        input_validation=accepted_result(frame),
    )
    assert report["representation"]["status"] == "descriptive_only"
    assert report["representation"]["findings"] == []
    groups = {g["label"]: g for g in report["representation"]["attributes"][0]["groups"]}
    assert groups["Male"]["difference_pp"] == 23.0

    encoded = report_json(report)
    assert json.loads(encoded) == report
    rows = list(csv.DictReader(io.StringIO(report_csv(report))))
    assert {row["label"] for row in rows} == {"Male", "Female"}
    assert {row["row_type"] for row in rows} == {"cohort"}


def test_single_group_with_reference_keeps_both_findings_in_export():
    report = run_audit(
        pd.DataFrame({"sex": ["Male"] * 100}),
        demographic_columns=["sex"],
        reference_proportions={"sex": {"Male": 0.5, "Female": 0.5}},
        source_type="test_fixture",
        input_validation=accepted_result(pd.DataFrame({"sex": ["Male"] * 100})),
    )
    codes = [finding["code"] for finding in report["representation"]["findings"]]
    assert codes == ["single_group", "missing_reference_group"]
    rows = list(csv.DictReader(io.StringIO(report_csv(report))))
    assert {row["code"] for row in rows if row["row_type"] == "finding"} == set(codes)


def test_runner_rejects_unvalidated_or_mismatched_input():
    frame = pd.DataFrame({"sex": ["F", "M"]})
    rejected = {"status": "rejected", "row_count": None, "column_count": None}
    import pytest
    with pytest.raises(ValueError, match="accepted"):
        run_audit(frame, demographic_columns=["sex"], source_type="test", input_validation=rejected)
    wrong_shape = {"status": "accepted", "row_count": 99, "column_count": 1}
    with pytest.raises(ValueError, match="row count"):
        run_audit(frame, demographic_columns=["sex"], source_type="test", input_validation=wrong_shape)


def test_csv_export_includes_identifier_findings():
    validation, frame = validate_input(b"sex,notes\nF,ok\nM,call 617-555-0100\n")
    report = run_audit(frame, demographic_columns=["sex"], source_type="test",
                       input_validation=validation)
    rows = list(csv.DictReader(io.StringIO(report_csv(report))))
    privacy_rows = [row for row in rows if row["row_type"] == "identifier_finding"]
    assert [row["code"] for row in privacy_rows] == ["phone_pattern"]
    assert report["identifier_screening"]["certifies_deidentification"] is False


def test_exports_include_change_preview_and_acceptance_state():
    validation, frame = validate_input(b"sex,value\nF,10\nM,10\nM,10\n")
    report = run_audit(frame, demographic_columns=["sex"], source_type="test",
                       input_validation=validation)
    preview, output = preview_changes(
        frame,
        [{"action": "drop_duplicate_rows"}],
        column_roles={"sex": "demographic", "value": "feature"},
    )
    assert output is not None and len(output) == 2
    report["change_preview"] = {**preview, "accepted_for_export": True}

    encoded = json.loads(report_json(report))
    assert encoded["change_preview"]["accepted_for_export"] is True
    rows = list(csv.DictReader(io.StringIO(report_csv(report))))
    change_rows = [row for row in rows if row["row_type"] == "change_action"]
    assert len(change_rows) == 1
    assert change_rows[0]["code"] == "drop_duplicate_rows"
    assert change_rows[0]["status"] == "applied"
    assert change_rows[0]["title"] == "Accepted preview action"
    assert json.loads(change_rows[0]["summary"]) == {"rows_removed": 1}

    reviewed_rows = list(csv.DictReader(io.StringIO(reviewed_copy_csv(output))))
    assert [row["source_row_index"] for row in reviewed_rows] == ["0", "1"]


def test_reviewed_copy_uses_collision_safe_source_index_header():
    frame = pd.DataFrame({"source_row_index": ["existing"]}, index=[42])
    rows = list(csv.DictReader(io.StringIO(reviewed_copy_csv(frame))))
    assert rows == [{"_source_row_index": "42", "source_row_index": "existing"}]
