"""Pure evidence payloads shared by the Streamlit workspace and MedGuard Explorer.

No Streamlit, Plotly, or browser code lives here, so the Explorer API can reuse
the same builders. Payloads carry aggregate evidence only: counts, shares,
contract statuses, per-row flags, and the demographic group labels that the
cohort views already display. Cell values and other column names stay in Python,
and nothing here changes the audited frame.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


STATUS_LABELS = {
    "review_needed": "review needed",
    "descriptive_only": "descriptive only",
    "insufficient_evidence": "insufficient evidence",
    "no_patterns_found": "no patterns found",
}
MOSAIC_LIMIT = 1_200
# Readiness funnel stages, in the order a row can leave them.
FUNNEL_STAGES = (
    ("all", "All rows"),
    ("unique", "No exact duplicate before it"),
    ("complete", "No missing cells"),
    ("labelled", "Group label recorded"),
)


def _row_ids(frame: pd.DataFrame) -> list[int]:
    """Stable row numbers from the validated frame's index, falling back to position."""

    try:
        return [int(label) for label in frame.index]
    except (TypeError, ValueError):
        return list(range(len(frame)))


def readiness_drop_stage(frame: pd.DataFrame, demographic_column: str | None) -> pd.Series:
    """Stage at which each row first leaves the funnel; 0 means it passes every check.

    1 = later copy of an exact duplicate, 2 = has a missing cell,
    3 = no recorded group label in the selected demographic column.
    """

    stage = pd.Series(0, index=frame.index, dtype=int)
    later_copy = frame.duplicated(keep="first")
    stage[later_copy] = 1
    has_gap = frame.isna().any(axis=1) & (stage == 0)
    stage[has_gap] = 2
    if demographic_column and demographic_column in frame.columns:
        unlabelled = frame[demographic_column].isna() & (stage == 0)
        stage[unlabelled] = 3
    return stage


def build_readiness_funnel(frame: pd.DataFrame, demographic_column: str | None) -> list[dict]:
    """Rows passing each measured check in sequence. Descriptive; nothing is removed."""

    stage = readiness_drop_stage(frame, demographic_column)
    total = int(len(frame))
    stages = FUNNEL_STAGES if demographic_column and demographic_column in frame.columns else FUNNEL_STAGES[:3]
    funnel = []
    for index, (key, label) in enumerate(stages):
        remaining = total if index == 0 else int(((stage == 0) | (stage > index)).sum())
        funnel.append({
            "key": key,
            "label": label,
            "rows": remaining,
            "dropped": 0 if index == 0 else int((stage == index).sum()),
            "share": round(remaining / total * 100, 1) if total else 0.0,
        })
    return funnel


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
    drops = readiness_drop_stage(frame, demographic_column).iloc[indices].tolist()
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
        "funnel": build_readiness_funnel(frame, demographic_column),
        "rows": [
            {
                "id": row_id,
                "row": row_id + 1,
                "group": int(group),
                "missing": int(count),
                "duplicate": bool(duplicate),
                "focus": bool(flag),
                "drop": int(stage),
            }
            for row_id, group, count, duplicate, flag, stage in zip(
                _row_ids(sampled), groups, missing, duplicates, focus, drops
            )
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
