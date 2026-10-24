"""Streamlit renderers and Plotly charts for the MedGuard workspace.

Every payload sent to the browser carries aggregate evidence only: counts,
shares, contract statuses, per-row flags, and the demographic group labels the
cohort section already displays. Cell values, other column names, and file
names stay in Python. Nothing here changes the audited frame.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit.components.v1 as components

from .payloads import (  # noqa: F401  re-exported for the Streamlit workspace and tests
    FUNNEL_STAGES,
    MOSAIC_LIMIT,
    STATUS_LABELS,
    allocate_squares,
    build_change_payload,
    build_cohort_payload,
    build_coverage_payload,
    build_mosaic_payload,
    build_quality_tiles,
    build_readiness_funnel,
    build_status_tiles,
    even_sample_indices,
    format_gap,
    quality_status,
    readiness_drop_stage,
    recorded_label,
    structure_status,
)


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
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
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
