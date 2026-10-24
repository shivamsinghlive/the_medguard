"""Contract-focused tests for the interactive visual helpers."""

from pathlib import Path
import json
import sys

import pandas as pd
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from services.audit_runner import run_audit
from services.input_validation import validate_input
from ui.visuals import (
    allocate_squares,
    build_readiness_funnel,
    build_change_payload,
    build_cohort_payload,
    build_coverage_payload,
    build_mosaic_payload,
    build_quality_tiles,
    build_status_tiles,
    completeness_donut,
    format_gap,
    missingness_lollipop,
    recorded_label,
)
from ui.visuals.components import GROUP_COLORS


def audit(frame, demographic_columns, reference=None):
    validation = {
        "status": "accepted", "row_count": len(frame), "column_count": len(frame.columns),
        "warnings": [],
    }
    return run_audit(
        frame, demographic_columns=demographic_columns, reference_proportions=reference,
        source_type="test", input_validation=validation,
    )


def coded_frame():
    return pd.DataFrame(
        {
            "sex": [0, 1, 1, 0, None, 0],
            "secret_value": ["alpha", None, "omega", "alpha", None, "alpha"],
            "visit": [1, 2, 3, 1, 5, 1],
        }
    )


def test_mosaic_payload_contains_only_aggregate_row_flags():
    frame = coded_frame()
    payload = build_mosaic_payload(
        frame, audit(frame, ["sex"]), demographic_column="sex", focus_column="secret_value"
    )
    text = json.dumps(payload)

    assert payload["labels"] == ["sex = 0", "sex = 1"]
    assert set(payload["rows"][0]) == {"id", "row", "group", "missing", "duplicate", "focus", "drop"}
    assert [row["drop"] for row in payload["rows"]] == [0, 2, 0, 1, 2, 1]
    assert "alpha" not in text and "omega" not in text
    assert "secret_value" not in text and "visit" not in text
    assert [row["focus"] for row in payload["rows"]] == [False, True, False, False, True, False]
    assert payload["rows"][4]["group"] == -1
    assert payload["focusMissing"] == 2
    assert payload["initialLens"] == "missing"
    assert [row["duplicate"] for row in payload["rows"]] == [True, False, False, True, False, True]


def test_mosaic_evenly_samples_large_frames_and_reports_it():
    frame = pd.DataFrame({"group": ["recorded"] * 1_205})
    payload = build_mosaic_payload(frame, audit(frame, ["group"]), demographic_column="group")

    assert payload["sampled"] is True
    assert payload["sampleCount"] == 1_200
    assert payload["rows"][0]["row"] == 1
    assert payload["rows"][-1]["row"] == 1_205


def test_labels_are_shown_exactly_as_recorded():
    assert recorded_label("sex", "0") == "sex = 0"
    assert recorded_label("sex", "Female ") == "sex = Female "


def test_status_tiles_use_contract_vocabulary_without_clearance():
    frame = coded_frame()
    tiles = build_status_tiles(audit(frame, ["sex"]))
    allowed = {"review_needed", "descriptive_only", "insufficient_evidence", "no_patterns_found"}

    assert [tile["label"] for tile in tiles] == ["Structure", "Identifiers", "Quality", "Representation"]
    assert {tile["status"] for tile in tiles} <= allowed
    assert tiles[2]["status"] == "review_needed"
    assert "pass" not in json.dumps(tiles).lower()
    assert "fair" not in json.dumps(tiles).lower().replace("no fairness verdict", "")


def test_waffle_allocation_always_fills_one_hundred_squares():
    assert sum(allocate_squares([703, 328, 0])) == 100
    assert allocate_squares([1, 1, 1]) == [34, 33, 33]
    assert allocate_squares([0, 0]) == [0, 0]


def test_cohort_payload_keeps_missing_segment_and_reference_outline():
    frame = pd.DataFrame({"sex": ["Male"] * 60 + ["Female"] * 30 + [None] * 10})
    report = audit(frame, ["sex"], {"sex": {"Male": 0.5, "Female": 0.5}})
    payload = build_cohort_payload(report["representation"]["attributes"][0])

    assert len(payload["cells"]) == 100
    assert payload["missingSquares"] == 10
    assert sum(1 for cell in payload["cells"] if cell["group"] == -1) == 10
    assert payload["observedCount"] == 90
    assert payload["groups"][0]["label"] == "sex = Male"
    assert payload["referenceSquares"] == 45
    assert sum(cell["reference"] for cell in payload["cells"]) == 45
    assert payload["groups"][0]["gap"] > 0


def test_gap_text_uses_percentage_points_and_a_true_minus():
    assert format_gap(23.0) == "+23 pp"
    assert format_gap(-23.0) == "−23 pp"
    assert format_gap(18.18) == "+18.2 pp"
    assert format_gap(0.0) == "0 pp"
    assert format_gap(None) is None


def test_quality_tiles_count_rows_with_gaps_and_duplicate_sets():
    frame = coded_frame()
    tiles = {tile["label"]: tile["value"] for tile in build_quality_tiles(frame, audit(frame, ["sex"]))}

    assert tiles == {
        "Missing cells": 3,
        "Rows with a gap": 2,
        "Rows in exact-duplicate sets": 3,
        "Columns checked": 3,
    }


def test_coverage_payload_reports_scan_coverage_not_clearance():
    frame = coded_frame()
    payload = build_coverage_payload(audit(frame, ["sex"])["identifier_screening"])

    assert payload["percent"] == 100.0
    assert payload["columnCount"] == 3
    assert payload["status"] in {"review_needed", "insufficient_evidence", "no_patterns_found"}


def test_change_payload_marks_removed_rows_and_protected_roles():
    frame = coded_frame()
    copy = frame[~frame.duplicated(keep="first")]
    payload = build_change_payload(
        frame,
        source_fingerprint="ab" * 32,
        preview_result={
            "status": "preview_ready", "output_fingerprint": "cd" * 32,
            "actions": [{"action": "drop_duplicate_rows", "status": "applied", "evidence": {"rows_removed": 2}}],
        },
        preview_frame=copy,
        column_roles={"sex": "demographic", "secret_value": "feature", "visit": "identifier"},
        accepted=True,
    )

    assert payload["removed"] == [4, 6]
    assert payload["removedRows"] == 2 and payload["copyRows"] == 4
    assert payload["protectedRoles"] == ["demographic", "identifier"]
    assert payload["accepted"] is True
    assert "secret_value" not in json.dumps(payload)


def test_change_payload_without_preview_keeps_every_row():
    frame = coded_frame()
    payload = build_change_payload(
        frame, source_fingerprint="ab" * 32, preview_result=None, preview_frame=None,
        column_roles={}, accepted=False,
    )

    assert payload["removed"] == [] and payload["copyRows"] == len(frame)
    assert payload["previewReady"] is False and payload["outputFingerprint"] is None


def test_plotly_visuals_share_template_and_reserve_tangerine_for_review():
    assert "medguard" in pio.templates
    assert "#FF8A3D" not in GROUP_COLORS

    completeness = completeness_donut(total_cells=100, missing_cells=12)
    lollipop = missingness_lollipop(
        {"bmi": 12, "sex": 3}, row_count=100, column_roles={"sex": "demographic"}
    )
    rendered = json.dumps(lollipop.to_plotly_json(), default=str, ensure_ascii=False)

    assert completeness.data[0].values == (88, 12)
    assert "#FF8A3D" in rendered
    assert "sex  · protected" in rendered
    assert not lollipop.to_plotly_json()["layout"].get("shapes")


def test_guided_demo_visual_payloads_match_the_audit():
    data_bytes = (ROOT / "data/synthetic/dataset4_diabetes_combined.csv").read_bytes()
    validation, frame = validate_input(data_bytes)
    report = run_audit(
        frame, demographic_columns=["sex"], source_type="bundled_synthetic_demo",
        input_validation=validation,
    )
    tiles = {tile["label"]: tile["value"] for tile in build_quality_tiles(frame, report)}
    mosaic = build_mosaic_payload(frame, report, demographic_column="sex")

    assert tiles["Missing cells"] == 340
    assert tiles["Rows in exact-duplicate sets"] == 62
    assert tiles["Columns checked"] == 17
    assert mosaic["rowCount"] == 1_031 and mosaic["sampled"] is False
    assert sum(row["duplicate"] for row in mosaic["rows"]) == 62
    assert sum(row["missing"] for row in mosaic["rows"]) == 340


def test_readiness_funnel_counts_rows_through_each_check():
    frame = coded_frame()
    funnel = build_readiness_funnel(frame, "sex")

    assert [stage["key"] for stage in funnel] == ["all", "unique", "complete", "labelled"]
    assert [stage["rows"] for stage in funnel] == [6, 4, 2, 2]
    assert [stage["dropped"] for stage in funnel] == [0, 2, 2, 0]
    assert build_readiness_funnel(frame, None)[-1]["key"] == "complete"


def test_mosaic_row_ids_follow_the_filtered_frame_index():
    frame = coded_frame().iloc[[1, 3, 5]]
    payload = build_mosaic_payload(frame, audit(frame, ["sex"]), demographic_column="sex")

    assert [row["id"] for row in payload["rows"]] == [1, 3, 5]
    assert [row["row"] for row in payload["rows"]] == [2, 4, 6]


def test_payloads_module_has_no_streamlit_dependency():
    import importlib, sys as _sys
    _sys.modules.pop("ui.visuals.payloads", None)
    source = (ROOT / "src/ui/visuals/payloads.py").read_text()
    assert "streamlit" not in source.split('"""', 2)[2]
    assert "plotly" not in source.split('"""', 2)[2]
    importlib.import_module("ui.visuals.payloads")
