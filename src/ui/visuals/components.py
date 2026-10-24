"""UI-only visual helpers mapped to MedGuard's existing report contract.

Every payload sent to the browser carries aggregate evidence only: counts,
shares, contract statuses, per-row flags, and the demographic group labels the
cohort section already displays. Cell values, other column names, and file
names stay in Python. Nothing here changes the audited frame.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit.components.v1 as components


DAYLIGHT = {
    "paper": "#F4F6FB",
    "card": "#FFFFFF",
    "ink": "#1A2340",
    "ink_2": "#4E5874",
    "ink_3": "#8790A8",
    "line": "#DDE2EE",
    "cobalt": "#2F5BFF",
    "cobalt_soft": "#E6ECFF",
    "cobalt_text": "#1E3AB8",
    "teal": "#13B5A6",
    "teal_soft": "#DDF6F3",
    "review": "#FF8A3D",
    "review_soft": "#FFEBDD",
    "review_text": "#8A3A05",
    "review_cell": "#FFC9A3",
    "neutral": "#1A2340",
    "neutral_soft": "#E7EAF3",
    "scan": "#8FA4FF",
    "scan_dim": "#C9D3F5",
    "dim": "#DDE2EE",
    "dim_2": "#E8ECF4",
}
# Groups beyond the first two use scan and ink tones; tangerine stays reserved
# for review evidence (review_needed, missing values, duplicates, removed rows).
GROUP_COLORS = (DAYLIGHT["cobalt"], DAYLIGHT["teal"], DAYLIGHT["scan"], DAYLIGHT["ink_2"])
STATUS_LABELS = {
    "review_needed": "review needed",
    "descriptive_only": "descriptive only",
    "insufficient_evidence": "insufficient evidence",
    "no_patterns_found": "no patterns found",
}
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
MOSAIC_LIMIT = 1_200
FONT_STACK = '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif'
_TEMPLATE = Path(__file__).with_name("component.html").read_text(encoding="utf-8")


pio.templates["medguard"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(GROUP_COLORS),
        font={"family": FONT_STACK, "color": DAYLIGHT["ink_2"], "size": 13},
        margin={"l": 12, "r": 12, "t": 12, "b": 12},
        xaxis={"showgrid": False, "zeroline": False, "showline": False, "ticks": ""},
        yaxis={
            "showgrid": True,
            "gridcolor": DAYLIGHT["line"],
            "gridwidth": 1,
            "zeroline": False,
            "showline": False,
            "ticks": "",
        },
        hoverlabel={
            "bgcolor": DAYLIGHT["ink"],
            "bordercolor": DAYLIGHT["ink"],
            "font": {"color": "#FFFFFF", "family": FONT_STACK},
        },
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"color": DAYLIGHT["ink_2"]}},
    )
)


def _plain_label(value: object) -> str:
    """Mirror the representation service's label text; no meaning is assigned."""

    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def recorded_label(column: str, label: object) -> str:
    """Show a group exactly as recorded, for example ``sex = 0``."""

    return f"{column} = {label}"


def even_sample_indices(row_count: int, limit: int = MOSAIC_LIMIT) -> list[int]:
    if row_count <= limit:
        return list(range(row_count))
    return np.linspace(0, row_count - 1, limit, dtype=int).tolist()


def quality_status(quality: Mapping) -> str:
    """Quality has no contract status; any measured gap or duplicate needs review."""

    return "review_needed" if quality["missing_cells"] or quality["duplicate_rows"] else "descriptive_only"


def structure_status(validation: Mapping) -> str:
    return "review_needed" if validation.get("warnings") else "descriptive_only"


def allocate_squares(shares: Sequence[float], total: int = 100) -> list[int]:
    """Largest-remainder rounding so the squares always add up to ``total``."""

    if not shares or sum(shares) <= 0:
        return [0] * len(shares)
    scale = total / sum(shares)
    raw = [share * scale for share in shares]
    counts = [math.floor(value) for value in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - counts[i]), i))
    for index in order[: total - sum(counts)]:
        counts[index] += 1
    return counts


def build_status_tiles(report: Mapping) -> list[dict]:
    dataset = report["dataset"]
    quality = report["quality"]
    screening = report["identifier_screening"]
    representation = report["representation"]
    return [
        {
            "label": "Structure",
            "value": dataset["row_count"],
            "unit": f"rows × {dataset['column_count']:,} columns",
            "status": structure_status(report["input_validation"]),
            "note": "Validated before any analysis ran.",
        },
        {
            "label": "Identifiers",
            "value": len(screening["findings"]),
            "unit": "matched signals",
            "status": screening["status"],
            "note": "Screening only; not de-identification.",
        },
        {
            "label": "Quality",
            "value": quality["missing_cells"],
            "unit": f"missing cells · {quality['duplicate_rows']:,} rows in duplicate sets",
            "status": quality_status(quality),
            "note": "Counts only; nothing was cleaned.",
        },
        {
            "label": "Representation",
            "value": len(representation["findings"]),
            "unit": (
                f"flags across {len(representation['attributes']):,} "
                f"attribute{'' if len(representation['attributes']) == 1 else 's'}"
            ),
            "status": representation["status"],
            "note": "Descriptive; no fairness verdict.",
        },
    ]


def build_mosaic_payload(
    frame: pd.DataFrame,
    report: Mapping,
    *,
    demographic_column: str | None,
    focus_column: str | None = None,
) -> dict:
    """Per-row aggregate flags for the mosaic; no cell values or other column names."""

    indices = even_sample_indices(len(frame))
    sampled = frame.iloc[indices]
    quality = report["quality"]
    screening = report["identifier_screening"]
    attribute = next(
        (item for item in report["representation"]["attributes"] if item["column"] == demographic_column),
        None,
    )

    labels: list[str] = []
    label_index: dict[str, int] = {}
    if attribute is not None:
        observed = [group for group in attribute["groups"] if group["count"]]
        labels = [recorded_label(attribute["column"], group["label"]) for group in observed]
        label_index = {group["label"]: index for index, group in enumerate(observed)}

    if attribute is not None:
        groups = [
            -1 if pd.isna(value) else label_index.get(_plain_label(value), -1)
            for value in sampled[demographic_column]
        ]
    else:
        groups = [-1] * len(sampled)
    duplicates = frame.duplicated(keep=False).iloc[indices].tolist()
    missing = sampled.isna().sum(axis=1).astype(int).tolist()
    focus_active = bool(focus_column and focus_column in frame.columns)
    focus = sampled[focus_column].isna().tolist() if focus_active else [False] * len(sampled)

    return {
        "rowCount": int(len(frame)),
        "sampled": len(indices) < len(frame),
        "sampleCount": len(indices),
        "labels": labels,
        "labelCounts": [group["count"] for group in attribute["groups"] if group["count"]] if attribute else [],
        "cohortStatus": attribute["status"] if attribute else "insufficient_evidence",
        "observedCount": attribute["observed_count"] if attribute else 0,
        "missingCells": quality["missing_cells"],
        "missingColumns": quality["columns_with_missing_values"],
        "duplicateRows": quality["duplicate_rows"],
        "qualityStatus": quality_status(quality),
        "focusActive": focus_active,
        "focusMissing": int(quality["missing_by_column"].get(focus_column, 0)) if focus_active else 0,
        "screeningStatus": screening["status"],
        "screeningMatches": len(screening["findings"]),
        "rowsScanned": screening["coverage"]["rows_scanned"],
        "initialLens": "missing" if focus_active else "cohort",
        "rows": [
            {
                "row": int(source) + 1,
                "group": int(group),
                "missing": int(count),
                "duplicate": bool(duplicate),
                "focus": bool(flag),
            }
            for source, group, count, duplicate, flag in zip(indices, groups, missing, duplicates, focus)
        ],
    }


def build_cohort_payload(attribute: Mapping) -> dict:
    """Dumbbell and waffle data for one attribute, straight from the contract."""

    column = attribute["column"]
    groups = attribute["groups"]
    has_reference = any(group["reference_proportion"] is not None for group in groups)
    total_rows = attribute["observed_count"] + attribute["missing_count"]

    counts = [group["count"] for group in groups] + [attribute["missing_count"]]
    squares = allocate_squares(counts) if total_rows else [0] * len(counts)
    cells = [{"group": index} for index, count in enumerate(squares[:-1]) for _ in range(count)]
    cells += [{"group": -1} for _ in range(squares[-1])]

    reference_squares = 0
    if has_reference and groups and groups[0]["reference_proportion"] is not None:
        observed_squares = 100 - squares[-1]
        reference_squares = round(groups[0]["reference_proportion"] * observed_squares)
    for position, cell in enumerate(cells):
        cell["reference"] = position < reference_squares

    return {
        "column": column,
        "status": attribute["status"],
        "observedCount": attribute["observed_count"],
        "missingCount": attribute["missing_count"],
        "hasReference": has_reference,
        "referenceLabel": recorded_label(column, groups[0]["label"]) if reference_squares else None,
        "referenceSquares": reference_squares,
        "groups": [
            {
                "label": recorded_label(column, group["label"]),
                "count": group["count"],
                "observed": None if group["proportion"] is None else round(group["proportion"] * 100, 1),
                "reference": (
                    None if group["reference_proportion"] is None
                    else round(group["reference_proportion"] * 100, 1)
                ),
                "gap": group["difference_pp"],
                "squares": squares[index],
            }
            for index, group in enumerate(groups)
        ],
        "missingSquares": squares[-1],
        "cells": cells,
    }


def format_gap(difference_pp: float | None) -> str | None:
    """Percentage-point gap with a true minus sign, for example ``−23 pp``."""

    if difference_pp is None:
        return None
    value = round(difference_pp, 1)
    text = f"{abs(value):.1f}".removesuffix(".0")
    if value > 0:
        return f"+{text} pp"
    if value < 0:
        return f"−{text} pp"
    return "0 pp"


def build_quality_tiles(frame: pd.DataFrame, report: Mapping) -> list[dict]:
    quality = report["quality"]
    return [
        {"label": "Missing cells", "value": quality["missing_cells"], "review": quality["missing_cells"] > 0},
        {"label": "Rows with a gap", "value": int(frame.isna().any(axis=1).sum()), "review": quality["missing_cells"] > 0},
        {"label": "Rows in exact-duplicate sets", "value": quality["duplicate_rows"], "review": quality["duplicate_rows"] > 0},
        {"label": "Columns checked", "value": report["dataset"]["column_count"], "review": False},
    ]


def build_coverage_payload(screening: Mapping) -> dict:
    coverage = screening["coverage"]
    row_count = coverage["row_count"]
    percent = round(coverage["rows_scanned"] / row_count * 100, 1) if row_count else 0.0
    return {
        "status": screening["status"],
        "percent": percent,
        "rowsScanned": coverage["rows_scanned"],
        "rowCount": row_count,
        "columnCount": coverage["column_count"],
        "checkCount": len(coverage["checks"]),
        "matches": len(screening["findings"]),
        "complete": bool(coverage["complete"]),
    }


def build_change_payload(
    source: pd.DataFrame,
    *,
    source_fingerprint: str,
    preview_result: Mapping | None,
    preview_frame: pd.DataFrame | None,
    column_roles: Mapping[str, str],
    accepted: bool,
) -> dict:
    ready = bool(
        preview_result and preview_result.get("status") == "preview_ready" and preview_frame is not None
    )
    kept = set(preview_frame.index) if ready else set(source.index)
    indices = even_sample_indices(len(source))
    removed = [source.index[index] not in kept for index in indices]
    copy_rows = len(preview_frame) if ready else len(source)
    cells_filled = 0
    if ready:
        cells_filled = sum(
            int(action.get("evidence", {}).get("cells_changed", 0))
            for action in preview_result.get("actions", [])
            if action.get("action") == "fill_missing" and action.get("status") == "applied"
        )
    protected_roles = sorted({role for role in column_roles.values() if role != "feature"})
    return {
        "sampled": len(indices) < len(source),
        "sampleCount": len(indices),
        "removed": [index + 1 for index, flag in zip(indices, removed) if flag],
        "rowNumbers": [index + 1 for index in indices],
        "sourceRows": len(source),
        "removedRows": len(source) - copy_rows,
        "copyRows": copy_rows,
        "cellsFilled": cells_filled,
        "sourceFingerprint": source_fingerprint,
        "outputFingerprint": preview_result.get("output_fingerprint") if ready else None,
        "previewReady": ready,
        "accepted": bool(accepted and ready),
        "protectedRoles": protected_roles,
    }


def _component(kind: str, payload: Mapping, *, height: int) -> None:
    safe_json = json.dumps({"kind": kind, **payload}, ensure_ascii=False).replace("</", "<\\/")
    components.html(_TEMPLATE.replace("__MEDGUARD_PAYLOAD__", safe_json), height=height, scrolling=False)


def render_status_strip(report: Mapping) -> None:
    _component("status", {"tiles": build_status_tiles(report)}, height=168)


def render_dataset_mosaic(
    frame: pd.DataFrame,
    report: Mapping,
    *,
    demographic_column: str | None,
    focus_column: str | None = None,
) -> None:
    payload = build_mosaic_payload(
        frame, report, demographic_column=demographic_column, focus_column=focus_column
    )
    _component("mosaic", payload, height=520)


def render_cohort_evidence(attribute: Mapping) -> None:
    payload = build_cohort_payload(attribute)
    for group in payload["groups"]:
        group["gapText"] = format_gap(group["gap"])
    _component("cohort", payload, height=360)


def render_quality_tiles(frame: pd.DataFrame, report: Mapping) -> None:
    _component("tiles", {"tiles": build_quality_tiles(frame, report)}, height=118)


def render_identifier_coverage(screening: Mapping) -> None:
    _component("identifier", build_coverage_payload(screening), height=300)


def render_change_map(source: pd.DataFrame, **kwargs) -> None:
    _component("changes", build_change_payload(source, **kwargs), height=460)


def cohort_distribution_donut(attribute: Mapping) -> go.Figure:
    groups = [group for group in attribute["groups"] if group["count"]]
    labels = [recorded_label(attribute["column"], group["label"]) for group in groups]
    values = [group["count"] for group in groups]
    if attribute["missing_count"]:
        labels.append("missing")
        values.append(attribute["missing_count"])
    colors = [GROUP_COLORS[index % len(GROUP_COLORS)] for index in range(len(groups))]
    if attribute["missing_count"]:
        colors.append(DAYLIGHT["dim"])
    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.66,
            sort=False,
            direction="clockwise",
            textinfo="none",
            marker={"colors": colors, "line": {"color": DAYLIGHT["card"], "width": 3}},
            hovertemplate="%{label}<br>%{value:,} rows · %{percent}<extra></extra>",
        )
    )
    figure.add_annotation(
        text=f"<b>{attribute['observed_count']:,}</b><br><span style='font-size:11px'>recorded values</span>",
        showarrow=False,
        font={"color": DAYLIGHT["ink"], "size": 20},
    )
    figure.update_layout(template="medguard", height=270, legend={"orientation": "h", "y": -0.05})
    return figure


def completeness_donut(*, total_cells: int, missing_cells: int) -> go.Figure:
    observed = max(total_cells - missing_cells, 0)
    share = observed / max(total_cells, 1)
    figure = go.Figure(
        go.Pie(
            labels=["Observed cells", "Missing cells"],
            values=[observed, missing_cells],
            hole=0.66,
            sort=False,
            direction="clockwise",
            textinfo="none",
            marker={
                "colors": [DAYLIGHT["scan_dim"], DAYLIGHT["review"]],
                "line": {"color": DAYLIGHT["card"], "width": 3},
            },
            hovertemplate="%{label}<br>%{value:,} cells · %{percent}<extra></extra>",
        )
    )
    figure.add_annotation(
        text=f"<b>{share:.1%}</b><br><span style='font-size:11px'>cells observed</span>",
        showarrow=False,
        font={"color": DAYLIGHT["ink"], "size": 20},
    )
    figure.update_layout(template="medguard", height=270, legend={"orientation": "h", "y": -0.05})
    return figure


def missingness_lollipop(
    missing_by_column: Mapping[str, int],
    row_count: int,
    column_roles: Mapping[str, str],
    focus_column: str | None = None,
) -> go.Figure:
    """Sorted missing share per column; protected roles are tagged, never hidden."""

    rows = sorted(missing_by_column.items(), key=lambda item: (item[1], item[0]))
    labels = [
        f"{column}  · protected" if column_roles.get(column, "feature") != "feature" else column
        for column, _ in rows
    ]
    shares = [count / max(row_count, 1) * 100 for _, count in rows]
    focused = [focus_column is None or column == focus_column for column, _ in rows]
    colors = [DAYLIGHT["review"] if flag else DAYLIGHT["review_cell"] for flag in focused]
    figure = go.Figure()
    for label, share in zip(labels, shares):
        figure.add_trace(
            go.Scatter(
                x=[0, share], y=[label, label], mode="lines",
                line={"color": DAYLIGHT["review_cell"], "width": 3},
                hoverinfo="skip", showlegend=False,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=shares,
            y=labels,
            mode="markers+text",
            marker={"size": 14, "color": colors, "line": {"width": 0}},
            text=[f"{share:.1f}% · {count:,} cells" for share, (_, count) in zip(shares, rows)],
            textposition="middle right",
            textfont={"color": DAYLIGHT["ink_2"]},
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:.1f}% missing<extra></extra>",
            showlegend=False,
        )
    )
    figure.update_layout(
        template="medguard",
        height=max(180, len(labels) * 46 + 70),
        margin={"l": 12, "r": 120, "t": 12, "b": 40},
        xaxis={
            "title": "Missing share of rows (%)",
            "range": [0, max(shares + [5]) * 1.15],
            "showgrid": False,
            "ticksuffix": "%",
        },
        yaxis={"title": None, "showgrid": True, "automargin": True},
    )
    return figure
