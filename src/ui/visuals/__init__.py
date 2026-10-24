"""Interactive, evidence-only visuals for the MedGuard workspace.

Payload builders load eagerly and have no Streamlit dependency, so the Explorer
API can import them. Streamlit renderers and Plotly charts load on first use.
"""

from importlib import import_module

from .payloads import (
    allocate_squares,
    build_change_payload,
    build_cohort_payload,
    build_coverage_payload,
    build_mosaic_payload,
    build_quality_tiles,
    build_readiness_funnel,
    build_status_tiles,
    format_gap,
    recorded_label,
)

_RENDERERS = {
    "PLOTLY_CONFIG",
    "cohort_distribution_donut",
    "completeness_donut",
    "missingness_lollipop",
    "render_change_map",
    "render_cohort_evidence",
    "render_dataset_mosaic",
    "render_identifier_coverage",
    "render_quality_tiles",
    "render_status_strip",
}


def __getattr__(name):
    if name in _RENDERERS:
        return getattr(import_module(".components", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "allocate_squares",
    "build_change_payload",
    "build_cohort_payload",
    "build_coverage_payload",
    "build_mosaic_payload",
    "build_quality_tiles",
    "build_readiness_funnel",
    "build_status_tiles",
    "format_gap",
    "recorded_label",
    *sorted(_RENDERERS),
]
