"""UI-only visual helpers mapped to MedGuard's existing report contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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
    "teal": "#13B5A6",
    "teal_soft": "#DDF6F3",
    "review": "#FF8A3D",
    "review_soft": "#FFEBDD",
    "neutral": "#1A2340",
    "neutral_soft": "#E7EAF3",
    "dim": "#DDE2EE",
}
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
_TEMPLATE = Path(__file__).with_name("component.html").read_text(encoding="utf-8")


pio.templates["medguard"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[DAYLIGHT["cobalt"], DAYLIGHT["teal"], DAYLIGHT["review"], "#8FA4FF"],
        font={"family": "Instrument Sans, system-ui, sans-serif", "color": DAYLIGHT["ink_2"]},
        margin={"l": 24, "r": 24, "t": 24, "b": 24},
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showline": False,
            "ticks": "",
        },
        yaxis={
            "gridcolor": DAYLIGHT["line"],
            "gridwidth": 1,
            "zeroline": False,
            "showline": False,
            "ticks": "",
        },
        hoverlabel={"bgcolor": DAYLIGHT["ink"], "font_color": "#FFFFFF", "bordercolor": DAYLIGHT["ink"]},
    )
)


def _recorded_label(value: object) -> str:
    """Match the representation service's display behavior without inferring meaning."""

    if isinstance(value, (bool, np.bool_)):
        return str(bool(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def _even_indices(row_count: int, limit: int = 1_200) -> list[int]:
    if row_count <= limit:
        return list(range(row_count))
    return np.linspace(0, row_count - 1, limit, dtype=int).tolist()


def build_mosaic_payload(
    frame: pd.DataFrame,
    *,
    demographic_column: str | None,
    selected_missing_column: str | None = None,
) -> dict:
    """Build browser-safe per-row flags; no raw records or cell values are included."""

    indices = _even_indices(len(frame))
    sampled = frame.iloc[indices]
    labels: list[str] = []
    label_indexes: dict[str, int] = {}
    if demographic_column and demographic_column in frame.columns:
        observed_labels = sorted(
            {_recorded_label(value) for value in frame[demographic_column].dropna()},
            key=str,
        )
        labels = observed_labels
        label_indexes = {label: index for index, label in enumerate(labels)}

    duplicate_flags = frame.duplicated(keep=False).iloc[indices].tolist()
    missing_counts = sampled.isna().sum(axis=1).astype(int).tolist()
    selected_missing = (
        sampled[selected_missing_column].isna().tolist()
        if selected_missing_column and selected_missing_column in sampled.columns
        else [False] * len(sampled)
    )
    group_indexes: list[int] = []
    if demographic_column and demographic_column in sampled.columns:
        for value in sampled[demographic_column]:
            group_indexes.append(-1 if pd.isna(value) else label_indexes[_recorded_label(value)])
    else:
        group_indexes = [-1] * len(sampled)

    return {
        "rowCount": int(len(frame)),
        "sampled": len(indices) < len(frame),
        "sampleCount": len(indices),
        "labels": labels,
        "rows": [
            {
                "row": int(source_index) + 1,
                "group": int(group_index),
                "missing": int(missing_count),
                "duplicate": bool(duplicate),
                "selectedMissing": bool(filtered_missing),
            }
            for source_index, group_index, missing_count, duplicate, filtered_missing in zip(
                indices, group_indexes, missing_counts, duplicate_flags, selected_missing
            )
        ],
    }


def _component(kind: str, payload: Mapping, *, height: int) -> None:
    safe_json = json.dumps({"kind": kind, **payload}, ensure_ascii=False).replace("</", "<\\/")
    components.html(_TEMPLATE.replace("__MEDGUARD_PAYLOAD__", safe_json), height=height, scrolling=False)


def render_dataset_mosaic(
    frame: pd.DataFrame,
    report: Mapping,
    *,
    demographic_column: str | None,
    selected_missing_column: str | None = None,
) -> None:
    payload = build_mosaic_payload(
        frame,
        demographic_column=demographic_column,
        selected_missing_column=selected_missing_column,
    )
    payload.update(
        {
            "quality": report["quality"],
            "screening": {
                "status": report["identifier_screening"]["status"],
                "matches": len(report["identifier_screening"]["findings"]),
            },
        }
    )
    _component("mosaic", payload, height=625)


def render_status_strip(report: Mapping) -> None:
    quality = report["quality"]
    _component(
        "status",
        {
            "tiles": [
                {"label": "Structure", "value": f"{report['dataset']['row_count']:,} rows", "status": "descriptive_only"},
                {"label": "Identifiers", "value": f"{len(report['identifier_screening']['findings']):,} matched", "status": report["identifier_screening"]["status"]},
                {"label": "Quality", "value": f"{quality['missing_cells']:,} missing cells", "status": "review_needed" if quality["missing_cells"] or quality["duplicate_rows"] else "descriptive_only"},
                {"label": "Representation", "value": f"{len(report['representation']['findings']):,} flags", "status": report["representation"]["status"]},
            ]
        },
        height=190,
    )


def render_identifier_coverage(screening: Mapping) -> None:
    coverage = screening["coverage"]
    _component(
        "identifier",
        {
            "status": screening["status"],
            "rowsScanned": coverage["rows_scanned"],
            "rowCount": coverage["row_count"],
            "columnCount": coverage["column_count"],
            "matches": len(screening["findings"]),
            "complete": bool(coverage["complete"]),
        },
        height=420,
    )


def render_waffle(attribute: Mapping) -> None:
    _component(
        "waffle",
        {
            "column": attribute["column"],
            "observedCount": attribute["observed_count"],
            "missingCount": attribute["missing_count"],
            "groups": attribute["groups"],
        },
        height=285,
    )


def render_change_map(
    source: pd.DataFrame,
    *,
    source_fingerprint: str,
    preview_result: Mapping | None,
    preview_frame: pd.DataFrame | None,
    protected_roles: Mapping[str, str],
    accepted: bool,
) -> None:
    output_indexes = set(preview_frame.index.tolist()) if preview_frame is not None else set(source.index)
    indices = _even_indices(len(source))
    removed = [source.index[index] not in output_indexes for index in indices]
    cells_filled = 0
    if preview_result:
        cells_filled = sum(
            int(action.get("evidence", {}).get("cells_changed", 0))
            for action in preview_result.get("actions", [])
            if action.get("action") == "fill_missing"
        )
    _component(
        "changes",
        {
            "rows": [{"row": index + 1, "removed": bool(flag)} for index, flag in zip(indices, removed)],
            "sourceRows": len(source),
            "copyRows": len(preview_frame) if preview_frame is not None else len(source),
            "removedRows": len(source) - (len(preview_frame) if preview_frame is not None else len(source)),
            "cellsFilled": cells_filled,
            "sourceFingerprint": (
                preview_result.get("source_fingerprint") if preview_result else source_fingerprint
            ),
            "outputFingerprint": preview_result.get("output_fingerprint") if preview_result else None,
            "previewReady": bool(preview_result and preview_result.get("status") == "preview_ready"),
            "accepted": bool(accepted),
            "protected": [f"{column} · {role}" for column, role in protected_roles.items()],
        },
        height=650,
    )


def cohort_distribution_donut(attribute: Mapping) -> go.Figure:
    groups = attribute["groups"]
    labels = [group["label"] for group in groups]
    values = [group["count"] for group in groups]
    figure = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.64,
            sort=False,
            textinfo="none",
            marker={"colors": [DAYLIGHT["cobalt"], DAYLIGHT["teal"], DAYLIGHT["review"], "#8FA4FF"], "line": {"color": DAYLIGHT["card"], "width": 3}},
            hovertemplate="%{label}<br>%{value:,} rows · %{percent}<extra></extra>",
        )
    )
    largest = max(groups, key=lambda group: group["count"]) if groups else None
    if largest:
        figure.add_annotation(text=f"<b>{largest['proportion']:.0%}</b><br><span style='font-size:11px'>largest group</span>", showarrow=False, font={"color": DAYLIGHT["ink"], "size": 21})
    figure.update_layout(template="medguard", height=270, legend={"orientation": "h", "y": -0.08})
    return figure


def completeness_donut(*, total_cells: int, missing_cells: int) -> go.Figure:
    observed = max(total_cells - missing_cells, 0)
    proportion = observed / max(total_cells, 1)
    figure = go.Figure(
        go.Pie(
            labels=["Observed", "Missing"],
            values=[observed, missing_cells],
            hole=0.64,
            sort=False,
            textinfo="none",
            marker={"colors": [DAYLIGHT["cobalt"], DAYLIGHT["review_soft"]], "line": {"color": DAYLIGHT["card"], "width": 3}},
            hovertemplate="%{label}<br>%{value:,} cells · %{percent}<extra></extra>",
        )
    )
    figure.add_annotation(text=f"<b>{proportion:.0%}</b><br><span style='font-size:11px'>observed</span>", showarrow=False, font={"color": DAYLIGHT["ink"], "size": 21})
    figure.update_layout(template="medguard", height=270, legend={"orientation": "h", "y": -0.08})
    return figure


def cohort_dumbbell(attribute: Mapping) -> go.Figure:
    groups = attribute["groups"]
    figure = go.Figure()
    for index, group in enumerate(groups):
        observed = (group["proportion"] or 0) * 100
        reference = group["reference_proportion"]
        if reference is not None:
            reference *= 100
            figure.add_trace(
                go.Scatter(
                    x=[reference, observed], y=[group["label"], group["label"]],
                    mode="lines", line={"color": DAYLIGHT["line"], "width": 6},
                    hoverinfo="skip", showlegend=False,
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=[reference], y=[group["label"]], mode="markers",
                    marker={"size": 17, "color": DAYLIGHT["card"], "line": {"color": DAYLIGHT["neutral"], "width": 3}},
                    name="Reference" if index == 0 else None, showlegend=index == 0,
                    hovertemplate=f"{group['label']}<br>Reference: {reference:.1f}%<extra></extra>",
                )
            )
        figure.add_trace(
            go.Scatter(
                x=[observed], y=[group["label"]], mode="markers+text",
                marker={"size": 17, "color": DAYLIGHT["cobalt"] if index % 2 == 0 else DAYLIGHT["teal"]},
                text=[f"{observed:.1f}%" + (f" · {group['difference_pp']:+.0f} pp" if group["difference_pp"] is not None else "")],
                textposition="middle right", cliponaxis=False,
                name="Observed" if index == 0 else None, showlegend=index == 0,
                hovertemplate=f"{group['label']}<br>Observed: {observed:.1f}%<extra></extra>",
            )
        )
    figure.update_layout(
        template="medguard", height=max(250, len(groups) * 62 + 110),
        xaxis={"range": [0, 112], "title": "Share of non-missing values (%)", "showgrid": False},
        yaxis={"title": None, "showgrid": True},
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def missingness_bars(missing_by_column: Mapping[str, int], row_count: int) -> go.Figure:
    rows = sorted(missing_by_column.items(), key=lambda item: item[1])
    labels = [item[0] for item in rows]
    values = [(item[1] / max(row_count, 1)) * 100 for item in rows]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker={"color": DAYLIGHT["review"], "line": {"width": 0}},
            text=[f"{value:.1f}%" for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:.1f}% missing<extra></extra>",
        )
    )
    figure.update_layout(
        template="medguard", height=max(210, len(labels) * 38 + 80),
        xaxis={"title": "Missing values (%)", "showgrid": False, "range": [0, max(values + [5]) * 1.2]},
        yaxis={"title": None, "showgrid": False},
    )
    return figure
