"""Integration tests for representation, evidence packaging, and exports."""

import csv
import io
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from services.audit_runner import finding_summary, report_csv, report_json, run_audit
from utils.audit_input import dataset_fingerprint


def test_runner_preserves_source_and_packages_unknown_states():
    frame = pd.DataFrame(
        {"sex": ["Male", "Female", "Female", None], "outcome": [1, 0, 1, 0]}
    )
    before = frame.copy(deep=True)
    fingerprint = dataset_fingerprint(frame)

    report = run_audit(
        frame,
        demographic_columns=["sex"],
        source_type="test_fixture",
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
    assert report["identifier_screening"]["status"] == "not_run"
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
    )
    codes = [finding["code"] for finding in report["representation"]["findings"]]
    assert codes == ["single_group", "missing_reference_group"]
    rows = list(csv.DictReader(io.StringIO(report_csv(report))))
    assert {row["code"] for row in rows if row["row_type"] == "finding"} == set(codes)
