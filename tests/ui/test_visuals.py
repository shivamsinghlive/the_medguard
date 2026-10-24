"""Contract-focused tests for the interactive visual helpers."""

from pathlib import Path
import sys

import pandas as pd
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ui.visuals import (
    build_mosaic_payload,
    cohort_dumbbell,
    completeness_donut,
    missingness_bars,
)


def test_mosaic_payload_contains_only_aggregate_row_flags():
    frame = pd.DataFrame(
        {
            "recorded_group": [0, 1, 1],
            "secret_value": ["alpha", None, "omega"],
        }
    )

    payload = build_mosaic_payload(
        frame,
        demographic_column="recorded_group",
        selected_missing_column="secret_value",
    )

    assert payload["labels"] == ["0", "1"]
    assert set(payload["rows"][0]) == {
        "row", "group", "missing", "duplicate", "selectedMissing"
    }
    assert "alpha" not in str(payload)
    assert "omega" not in str(payload)
    assert "secret_value" not in str(payload)
    assert payload["rows"][1]["selectedMissing"] is True


def test_mosaic_evenly_samples_large_frames_and_reports_it():
    frame = pd.DataFrame({"group": ["recorded"] * 1_205})
    payload = build_mosaic_payload(frame, demographic_column="group")

    assert payload["sampled"] is True
    assert payload["sampleCount"] == 1_200
    assert payload["rows"][0]["row"] == 1
    assert payload["rows"][-1]["row"] == 1_205


def test_dumbbell_uses_contract_values_without_threshold_shapes():
    attribute = {
        "groups": [
            {
                "label": "sex = 0",
                "count": 73,
                "proportion": 0.73,
                "reference_proportion": 0.5,
                "difference_pp": 23.0,
            },
            {
                "label": "sex = 1",
                "count": 27,
                "proportion": 0.27,
                "reference_proportion": 0.5,
                "difference_pp": -23.0,
            },
        ]
    }

    figure = cohort_dumbbell(attribute)
    rendered = figure.to_plotly_json()

    assert "sex = 0" in str(rendered)
    assert "+23 pp" in str(rendered)
    assert "-23 pp" in str(rendered)
    assert not rendered["layout"].get("shapes")


def test_plotly_visuals_share_medguard_template_and_daylight_colors():
    assert "medguard" in pio.templates

    completeness = completeness_donut(total_cells=100, missing_cells=12)
    missingness = missingness_bars({"feature": 12}, row_count=100)

    assert completeness.data[0].values == (88, 12)
    assert "#FF8A3D" in str(missingness.to_plotly_json())
