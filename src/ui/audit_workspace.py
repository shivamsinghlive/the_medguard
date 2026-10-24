"""MedGuard's evidence-first dataset audit workspace."""

from __future__ import annotations

from html import escape
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from services.audit_runner import (
    finding_summary, report_csv, report_json, reviewed_copy_csv, run_audit,
)
from agents.audit_explainer import (
    ALLOWED_CONTEXTS, DEFAULT_MODEL, explanation_cache_key, generate_explanation,
)
from services.change_preview import preview_changes
from services.contracts import ChangePreviewError, RepresentationInputError
from services.input_validation import validate_input


DEMO_PATH = PROJECT_DIR / "data/synthetic/dataset2_diabetes_gender_bias.csv"
PRIORITY_LABELS = {"high": "Review first", "medium": "Review next", "low": "Context"}
STATUS_LABELS = {
    "review_needed": "Review needed",
    "descriptive_only": "Descriptive only",
    "insufficient_evidence": "Insufficient evidence",
}
SCREENING_STATUS_LABELS = {
    "review_needed": "Potential identifiers need review",
    "no_patterns_found": "No listed patterns found",
    "insufficient_evidence": "Insufficient evidence",
}
CHANGE_ACTIONS = {
    "Remove exact duplicate rows": "drop_duplicate_rows",
    "Remove rows missing selected feature values": "drop_rows_with_missing",
    "Fill missing feature values": "fill_missing",
    "Trim leading and trailing whitespace": "strip_whitespace",
    "Remove a feature column": "drop_column",
}
REVIEWED_SOURCES = (
    {
        "id": "S4",
        "label": "Cohort context",
        "title": "Good Machine Learning Practice",
        "publisher": "FDA, Health Canada and MHRA · 2021",
        "summary": (
            "Intended-population representation and subgroup testing matter; the principles "
            "do not define a universal numeric disparity threshold."
        ),
        "url": "https://www.fda.gov/media/153486/download",
    },
    {
        "id": "S6",
        "label": "Privacy context",
        "title": "45 CFR 164.514(b)",
        "publisher": "HIPAA Privacy Rule · current text",
        "summary": (
            "The regulation describes Expert Determination and Safe Harbor. Pattern screening "
            "alone establishes neither method."
        ),
        "url": "https://www.law.cornell.edu/cfr/text/45/164.514",
    },
    {
        "id": "S8",
        "label": "Missing-data context",
        "title": "Multiple imputation: potential and pitfalls",
        "publisher": "BMJ · 2009",
        "summary": (
            "Missing at random is an analytical assumption, not something this audit can prove "
            "from the observed table."
        ),
        "url": "https://doi.org/10.1136/bmj.b2393",
    },
)


st.set_page_config(
    page_title="MedGuard | Dataset Readiness",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    :root {
      --mg-night: #0b1f2a; --mg-ink: #17323d; --mg-muted: #58707a;
      --mg-teal: #087f78; --mg-teal-bright: #43c6b5; --mg-teal-soft: #e7f6f3;
      --mg-coral: #d66b4b; --mg-coral-soft: #fff0ea; --mg-amber: #91610b;
      --mg-amber-soft: #fff7df; --mg-surface: #fbfdfc; --mg-border: #d9e6e2;
    }
    html { scroll-behavior: smooth; }
    .stApp { background:
      radial-gradient(circle at 88% 5%, rgba(67,198,181,.08), transparent 23rem), #f4f8f6; }
    .block-container { max-width: 1240px; padding-top: 1.35rem; padding-bottom: 5rem; }
    h1, h2, h3 { color: var(--mg-ink); letter-spacing: -0.035em; }
    p, li, label { color: var(--mg-muted); }
    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }
    .mg-hero { position: relative; overflow: hidden; padding: 2.25rem 2.35rem;
      border-radius: 24px; color: white; margin-bottom: 1rem;
      background: radial-gradient(circle at 88% 12%, rgba(67,198,181,.30), transparent 27%),
        linear-gradient(128deg, #0b1f2a 0%, #123944 64%, #0b5c5b 100%);
      box-shadow: 0 20px 50px rgba(11,31,42,.16); }
    .mg-hero::after { content: ""; position: absolute; width: 260px; height: 260px;
      right: -95px; bottom: -145px; border: 1px solid rgba(255,255,255,.18);
      border-radius: 50%; box-shadow: 0 0 0 38px rgba(255,255,255,.04),
        0 0 0 78px rgba(255,255,255,.025); }
    .mg-eyebrow { color: #8ee4d8; font-size: .72rem; font-weight: 800;
      letter-spacing: .14em; text-transform: uppercase; margin-bottom: .75rem; }
    .mg-hero h1 { max-width: 780px; color: white; font-size: clamp(2.15rem, 5vw, 3.7rem);
      line-height: 1.01; letter-spacing: -.055em; margin: 0 0 1rem; }
    .mg-lede { color: #d2e5e2; font-size: 1.05rem; max-width: 720px;
      line-height: 1.65; margin: 0 0 1.35rem; }
    .mg-hero-meta { display: flex; flex-wrap: wrap; gap: .55rem; }
    .mg-chip { display: inline-block; border: 1px solid #abdadd; border-radius: 999px;
      background: rgba(255,255,255,.08); color: #e9fffb; padding: .36rem .72rem;
      font-size: .75rem; font-weight: 700; }
    .mg-hero-flow { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: .55rem;
      margin-top: 1.35rem; max-width: 880px; }
    .mg-flow-step { border-top: 1px solid rgba(255,255,255,.32); padding-top: .65rem;
      color: #dff4f1; font-size: .72rem; line-height: 1.35; }
    .mg-flow-step strong { color: white; display: block; font-size: .78rem; margin-bottom: .1rem; }
    .mg-section { display: flex; align-items: end; justify-content: space-between; gap: 1rem;
      margin: 2.25rem 0 .75rem; }
    .mg-section-kicker { color: var(--mg-teal); font-size: .7rem; font-weight: 800;
      letter-spacing: .12em; text-transform: uppercase; }
    .mg-section-title { color: var(--mg-ink); font-size: 1.55rem; font-weight: 760;
      letter-spacing: -.035em; margin-top: .15rem; }
    .mg-section-copy { color: var(--mg-muted); font-size: .86rem; max-width: 480px; text-align: right; }
    .mg-card { border: 1px solid var(--mg-border); border-radius: 16px; background: white;
      padding: 1rem 1.1rem; margin: .65rem 0; box-shadow: 0 8px 24px rgba(20,54,62,.055); }
    .mg-card.high { border-left: 4px solid var(--mg-coral); }
    .mg-card.medium { border-left: 4px solid #d59b2d; }
    .mg-card.low { border-left: 4px solid var(--mg-teal); }
    .mg-priority { color: var(--mg-coral); font-size: .68rem; font-weight: 800;
      letter-spacing: .07em; text-transform: uppercase; }
    .mg-title { color: var(--mg-ink); font-size: 1.02rem; font-weight: 760; margin: .25rem 0; }
    .mg-copy { color: var(--mg-muted); font-size: .88rem; line-height: 1.55; }
    .mg-note, .mg-warning, .mg-empty { border-radius: 14px; padding: 1rem 1.1rem; }
    .mg-note { border: 1px solid #b9ded7; background: var(--mg-teal-soft); color: #15584f; }
    .mg-warning { border: 1px solid #eed6a5; background: var(--mg-amber-soft); color: #704b08; }
    .mg-empty { border: 1px dashed #9ebdb6; background: rgba(255,255,255,.65);
      color: var(--mg-muted); text-align: center; padding: 2rem; }
    .mg-review-queue { display: grid; grid-template-columns: auto 1fr auto; align-items: center;
      gap: 1rem; border: 1px solid #b8d9d2; border-radius: 18px; background: white;
      padding: 1.05rem 1.15rem; margin: 1rem 0 1.3rem; box-shadow: 0 10px 30px rgba(20,54,62,.06); }
    .mg-review-count { display: grid; place-items: center; min-width: 3rem; height: 3rem;
      border-radius: 14px; background: var(--mg-teal-soft); color: #075f59;
      font-size: 1.35rem; font-weight: 850; }
    .mg-review-copy strong { display: block; color: var(--mg-ink); font-size: 1rem; }
    .mg-review-copy span { color: var(--mg-muted); font-size: .82rem; line-height: 1.45; }
    .mg-review-link { display: inline-block; border-radius: 999px; background: #0b736c;
      color: white !important; text-decoration: none; padding: .55rem .85rem; font-size: .76rem;
      font-weight: 800; white-space: nowrap; }
    .mg-status-row { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: .75rem;
      margin: .75rem 0 1rem; }
    .mg-status { border: 1px solid var(--mg-border); background: white; border-radius: 14px;
      padding: .9rem 1rem; }
    .mg-status-label { color: var(--mg-muted); font-size: .7rem; font-weight: 800;
      letter-spacing: .08em; text-transform: uppercase; }
    .mg-status-value { color: var(--mg-ink); font-weight: 760; margin-top: .2rem; }
    .mg-status-value::before { content: ""; display: inline-block; width: .55rem; height: .55rem;
      border-radius: 50%; background: var(--mg-teal-bright); margin-right: .45rem; }
    .mg-export { border-radius: 18px; padding: 1.15rem 1.25rem; margin-top: 1.4rem;
      background: linear-gradient(115deg, #e5f5f1, #f7fbf9); border: 1px solid #c8e2db; }
    .mg-preview { border: 1px solid #b9ded7; border-radius: 18px; background: white;
      padding: 1rem 1.1rem; margin: .75rem 0; box-shadow: 0 8px 24px rgba(20,54,62,.05); }
    .mg-preview-ready { color: #08766d; font-size: .72rem; font-weight: 850;
      letter-spacing: .1em; text-transform: uppercase; }
    .mg-explanation { border: 1px solid #c8d8e8; border-radius: 18px; background: #f6f9fd;
      padding: 1.05rem 1.15rem; margin: .75rem 0; }
    .mg-source-card { height: 100%; border: 1px solid var(--mg-border); border-radius: 16px;
      background: white; padding: 1rem 1.05rem; box-shadow: 0 8px 24px rgba(20,54,62,.045); }
    .mg-source-label { color: var(--mg-teal); font-size: .66rem; font-weight: 850;
      letter-spacing: .1em; text-transform: uppercase; }
    .mg-source-title { color: var(--mg-ink); font-size: .96rem; font-weight: 780;
      margin: .35rem 0 .12rem; }
    .mg-source-publisher { color: var(--mg-muted); font-size: .72rem; margin-bottom: .65rem; }
    .mg-source-summary { color: var(--mg-muted); font-size: .8rem; line-height: 1.5; min-height: 4.8rem; }
    .mg-source-link { color: #086c64 !important; font-size: .76rem; font-weight: 800;
      text-decoration-thickness: 1px; text-underline-offset: 3px; }
    .mg-brand { display: flex; align-items: center; gap: .65rem; margin: .3rem 0 1.5rem; }
    .mg-shield { display: grid; place-items: center; width: 2rem; height: 2rem;
      border-radius: 9px 9px 12px 12px; background: var(--mg-night); color: #76ddd0;
      font-weight: 900; font-size: .78rem; }
    .mg-brand-name { color: var(--mg-night); font-size: 1.05rem; font-weight: 850; }
    .mg-brand-sub { color: var(--mg-muted); font-size: .68rem; letter-spacing: .08em;
      text-transform: uppercase; }
    .mg-step { display: grid; grid-template-columns: 1.7rem 1fr; gap: .55rem; margin: .85rem 0; }
    .mg-step-num { display: grid; place-items: center; width: 1.55rem; height: 1.55rem;
      border-radius: 50%; background: #dceae6; color: #315e58; font-size: .68rem; font-weight: 800; }
    .mg-step strong { display: block; color: var(--mg-ink); font-size: .82rem; }
    .mg-step span { color: var(--mg-muted); font-size: .72rem; line-height: 1.35; }
    .mg-nav { display: grid; gap: .28rem; margin: .35rem 0 1rem; }
    .mg-nav a { color: #315e58 !important; text-decoration: none; border-radius: 8px;
      padding: .42rem .55rem; font-size: .76rem; font-weight: 700; }
    .mg-nav a:hover { background: #dceae6; }
    [data-testid="stMetric"] { border: 1px solid var(--mg-border); border-radius: 12px;
      background: white; padding: .9rem 1rem; box-shadow: 0 7px 22px rgba(20,54,62,.04); }
    [data-testid="stMetricLabel"] { color: var(--mg-muted); }
    [data-testid="stMetricValue"] { color: var(--mg-ink); font-size: 1.5rem; font-weight: 760; }
    [data-testid="stSidebar"] { background: #eef5f2; border-right: 1px solid #d6e4df; }
    [data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }
    [data-testid="stFileUploader"] { background: white; border-radius: 14px; padding: .35rem .65rem; }
    [data-baseweb="select"] > div { background: white; border-color: #c7d9d4; color: var(--mg-ink); }
    [data-baseweb="select"] input, [data-baseweb="select"] svg { color: var(--mg-ink); fill: var(--mg-ink); }
    [data-baseweb="tag"] { background-color: #0b8178; }
    [data-baseweb="tag"] span { color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; background: #e8f0ed; padding: .3rem;
      border-radius: 12px; overflow-x: auto; }
    .stTabs [data-baseweb="tab"] { border-radius: 9px; padding: .45rem .8rem; }
    .stTabs [aria-selected="true"] { background: white; box-shadow: 0 2px 8px rgba(20,54,62,.08); }
    .stDownloadButton > button, .stButton > button { border-radius: 10px; font-weight: 700; }
    .stDownloadButton > button { border-color: #15877d; color: #086c64; background: white; }
    .stButton > button:focus-visible, .stDownloadButton > button:focus-visible,
    [data-baseweb="tab"]:focus-visible, [data-baseweb="select"]:focus-within,
    input:focus-visible, [role="radio"]:focus-visible, [role="checkbox"]:focus-visible {
      outline: 3px solid #62c5ca; outline-offset: 2px;
    }
    @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
    @media (max-width: 700px) {
      .block-container { padding: .8rem .8rem 3rem; }
      .mg-hero { padding: 1.6rem 1.25rem; border-radius: 18px; }
      .mg-hero h1 { font-size: 2.2rem; }
      .mg-section { display: block; }
      .mg-section-copy { text-align: left; margin-top: .35rem; }
      .mg-status-row { grid-template-columns: 1fr; }
      .mg-hero-flow { grid-template-columns: repeat(2,minmax(0,1fr)); }
      .mg-review-queue { grid-template-columns: auto 1fr; }
      .mg-review-link { grid-column: 1 / -1; text-align: center; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def priority_card(finding: dict) -> None:
    priority = finding.get("priority", "low")
    label = PRIORITY_LABELS.get(priority, "Review")
    title = escape(str(finding.get("title", "Review this evidence")))
    summary = escape(finding_summary(finding))
    action = escape(str(finding.get("suggested_action", "Review the measured evidence.")))
    st.markdown(
        f"""
        <div class="mg-card {escape(priority)}">
          <div class="mg-priority">{escape(label)}</div>
          <div class="mg-title">{title}</div>
          <div class="mg-copy">{summary}</div>
          <div class="mg-copy"><strong>Next:</strong> {action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reference_for_demo(enabled: bool, columns: list[str]) -> dict | None:
    if enabled and "sex" in columns:
        return {"sex": {"Male": 0.5, "Female": 0.5}}
    return None


def clear_change_state() -> None:
    """Reset the current change request and any accepted preview."""

    for key in (
        "change_preview_context", "change_preview_result", "change_preview_frame",
        "accepted_change_context",
    ):
        st.session_state.pop(key, None)
    st.session_state["selected_change_actions"] = []


with st.sidebar:
    st.markdown(
        '<div class="mg-brand"><div class="mg-shield">MG</div><div>'
        '<div class="mg-brand-name">MedGuard</div><div class="mg-brand-sub">Evidence workspace</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("START HERE · CHOOSE A SOURCE")
    source = st.radio(
        "Data source",
        ["Guided demo", "Upload CSV"],
        help="The guided demo opens immediately and uses synthetic records.",
    )
    st.divider()
    st.caption("JUMP TO")
    st.markdown(
        '<nav class="mg-nav" aria-label="Workspace sections">'
        '<a href="#review-scope">1 · Assign roles</a>'
        '<a href="#review-evidence">2 · Review evidence</a>'
        '<a href="#reviewed-context">3 · Check source context</a>'
        '<a href="#preview-changes">4 · Preview changes</a>'
        '<a href="#optional-explanation">5 · Optional explanation</a>'
        '<a href="#export-evidence">6 · Export evidence</a>'
        '</nav>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("WORKFLOW")
    st.markdown(
        '<div class="mg-step"><div class="mg-step-num">1</div><div><strong>Load</strong>'
        '<span>Validate structure and screen potential identifiers.</span></div></div>'
        '<div class="mg-step"><div class="mg-step-num">2</div><div><strong>Inspect</strong>'
        '<span>Review representation, missingness, and evidence.</span></div></div>'
        '<div class="mg-step"><div class="mg-step-num">3</div><div><strong>Export</strong>'
        '<span>Save a machine-readable audit record.</span></div></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("SCOPE")
    st.write("Dataset readiness before model training. No clinical or fairness certification.")


st.markdown(
    '<div class="mg-hero"><div class="mg-eyebrow">Healthcare dataset readiness · DS+X 2026</div>'
    '<h1>See the evidence before you train.</h1>'
    '<div class="mg-lede">MedGuard turns a healthcare CSV into a reviewable record of cohort '
    'coverage, data quality, and potential identifier signals—without changing a single row.</div>'
    '<div class="mg-hero-meta"><span class="mg-chip">Deterministic checks</span>'
    '<span class="mg-chip">Source preserved</span><span class="mg-chip">Offline-ready demo</span>'
    '<span class="mg-chip">Honest unknowns</span></div>'
    '<div class="mg-hero-flow">'
    '<div class="mg-flow-step"><strong>01 · Validate</strong>Reject unsafe structure early</div>'
    '<div class="mg-flow-step"><strong>02 · Inspect</strong>Measure evidence and unknowns</div>'
    '<div class="mg-flow-step"><strong>03 · Preview</strong>Review changes on a copy</div>'
    '<div class="mg-flow-step"><strong>04 · Export</strong>Carry evidence forward</div>'
    '</div></div>',
    unsafe_allow_html=True,
)


if source == "Guided demo":
    validation, data = validate_input(DEMO_PATH.read_bytes())
    source_label = "Synthetic diabetes cohort"
    source_type = "bundled_synthetic_demo"
    st.markdown(
        '<div class="mg-note"><strong>Guided demo is ready.</strong> This bundled synthetic '
        'cohort lets you explore every review step without uploading patient data.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="mg-section"><div><div class="mg-section-kicker">Private local review</div>'
        '<div class="mg-section-title">Upload a CSV</div></div>'
        '<div class="mg-section-copy">The first release accepts UTF-8 CSV files up to 25 MB, '
        '200,000 rows, and 500 columns.</div></div>',
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded is None:
        st.markdown(
            '<div class="mg-empty"><strong>Drop in a healthcare dataset to begin</strong><br>'
            'MedGuard will validate its structure before any analysis runs.</div>',
            unsafe_allow_html=True,
        )
        st.stop()
    validation, data = validate_input(uploaded.getvalue())
    if validation["status"] == "rejected":
        st.error("This CSV was rejected before analysis.")
        for issue in validation["errors"]:
            st.write(f"- {issue['message']}")
        st.stop()
    source_label = uploaded.name
    source_type = "uploaded_csv"

if data is None:
    st.error("No validated table is available for analysis.")
    st.stop()
if validation["warnings"]:
    for warning in validation["warnings"]:
        st.warning(warning["message"])
st.caption(
    f"✓ Input accepted · {validation['byte_count']:,} bytes · {validation['row_count']:,} rows · "
    f"{validation['column_count']:,} columns"
)


st.markdown('<div id="review-scope"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Step 2 · Assign roles</div>'
    '<div class="mg-section-title">Define the review scope</div></div>'
    '<div class="mg-section-copy">You choose what demographic evidence to measure. MedGuard '
    'does not guess the meaning of coded values.</div></div>',
    unsafe_allow_html=True,
)
columns = list(data.columns)
suggested_demographics = [c for c in columns if c.lower() in {"sex", "gender", "race_ethnicity"}]
suggested_outcomes = [c for c in columns if c.lower() in {"outcome", "target", "diabetes", "heart_disease"}]
suggested_ids = [c for c in columns if c.lower().endswith("_id")]
suggested_predictions = [c for c in columns if c.lower() in {"prediction", "risk_score", "predicted_label"}]
role_col1, role_col2, role_col3, role_col4 = st.columns(4)
with role_col1:
    demographic_columns = st.multiselect(
        "Demographic columns",
        columns,
        default=suggested_demographics[:1],
        help="Select explicitly. Numeric codes are retained and are never mapped automatically.",
    )
with role_col2:
    outcome_options = [c for c in columns if c not in demographic_columns]
    outcome_column = st.selectbox(
        "Outcome column (optional)",
        ["Not selected"] + outcome_options,
        index=(outcome_options.index(suggested_outcomes[0]) + 1)
        if suggested_outcomes and suggested_outcomes[0] in outcome_options else 0,
    )
with role_col3:
    unavailable_for_ids = set(demographic_columns)
    if outcome_column != "Not selected":
        unavailable_for_ids.add(outcome_column)
    identifier_options = [c for c in columns if c not in unavailable_for_ids]
    identifier_columns = st.multiselect(
        "Identifier columns",
        identifier_options,
        default=[c for c in suggested_ids if c in identifier_options],
        help="Identifiers are excluded from future proposed transformations.",
    )
with role_col4:
    unavailable_for_predictions = unavailable_for_ids | set(identifier_columns)
    prediction_options = [c for c in columns if c not in unavailable_for_predictions]
    prediction_column = st.selectbox(
        "Prediction column (optional)",
        ["Not selected"] + prediction_options,
        index=(prediction_options.index(suggested_predictions[0]) + 1)
        if suggested_predictions and suggested_predictions[0] in prediction_options else 0,
        help="Predictions are protected from cleaning actions by default.",
    )

if outcome_column != "Not selected" or identifier_columns or prediction_column != "Not selected":
    st.caption(
        "Outcome, prediction, identifier, and demographic roles are protected from change "
        "targets. Role selection does not change the measurements in this audit."
    )

column_roles = {column: "feature" for column in columns}
for column in demographic_columns:
    column_roles[column] = "demographic"
if outcome_column != "Not selected":
    column_roles[outcome_column] = "outcome"
for column in identifier_columns:
    column_roles[column] = "identifier"
if prediction_column != "Not selected":
    column_roles[prediction_column] = "prediction"

use_demo_reference = False
if source == "Guided demo" and "sex" in demographic_columns:
    use_demo_reference = st.checkbox(
        "Compare `sex` with an illustrative 50/50 reference",
        value=False,
        help=(
            "This optional reference is supplied only for the guided demo. A percentage-point "
            "difference is descriptive and does not trigger a universal cutoff."
        ),
    )

try:
    report = run_audit(
        data,
        demographic_columns=demographic_columns,
        reference_proportions=reference_for_demo(use_demo_reference, demographic_columns),
        source_type=source_type,
        input_validation=validation,
    )
except RepresentationInputError as error:
    st.error(f"Representation analysis could not run: {error}")
    st.stop()

representation = report["representation"]
quality = report["quality"]
screening = report["identifier_screening"]

st.markdown('<div id="review-evidence"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Step 3 · Review evidence</div>'
    f'<div class="mg-section-title">{escape(source_label)}</div></div>'
    '<div class="mg-section-copy">Measured results stay separate from limitations and future '
    'recommendations.</div></div>',
    unsafe_allow_html=True,
)
metric_cols = st.columns(4)
metric_cols[0].metric("Records", f"{report['dataset']['row_count']:,}")
metric_cols[1].metric("Attributes assessed", len(representation["attributes"]))
metric_cols[2].metric("Representation flags", len(representation["findings"]))
metric_cols[3].metric("Identifier signals", len(screening["findings"]))
st.caption(
    "Counts reflect the validated table. Flags prioritize review; they do not estimate clinical risk."
)
st.markdown(
    '<div class="mg-status-row">'
    f'<div class="mg-status"><div class="mg-status-label">Representation evidence</div>'
    f'<div class="mg-status-value">{escape(STATUS_LABELS[representation["status"]])}</div></div>'
    f'<div class="mg-status"><div class="mg-status-label">Identifier screening</div>'
    f'<div class="mg-status-value">{escape(SCREENING_STATUS_LABELS[screening["status"]])}</div></div>'
    '</div>',
    unsafe_allow_html=True,
)

review_count = len(representation["findings"]) + len(screening["findings"])
if screening["findings"]:
    review_title = f"{review_count} signal{'s' if review_count != 1 else ''} ready for review"
    review_copy = (
        "Start with Identifier screening, then confirm that the selected cohort scope matches "
        "the intended study population."
    )
elif representation["findings"]:
    review_title = f"{review_count} cohort signal{'s' if review_count != 1 else ''} ready for review"
    review_copy = "Open Cohort evidence to inspect counts, denominators, and recorded labels."
else:
    review_title = "No configured review rule triggered"
    review_copy = (
        "The measurements are still descriptive. Inspect the evidence and limitations before "
        "deciding whether this dataset fits the intended use."
    )
st.markdown(
    f'<div class="mg-review-queue" role="status">'
    f'<div class="mg-review-count" aria-label="{review_count} review signals">{review_count}</div>'
    f'<div class="mg-review-copy"><strong>{escape(review_title)}</strong>'
    f'<span>{escape(review_copy)}</span></div>'
    '<a class="mg-review-link" href="#evidence-tabs">Review evidence ↓</a></div>',
    unsafe_allow_html=True,
)

st.markdown('<div id="evidence-tabs"></div>', unsafe_allow_html=True)
overview_tab, cohorts_tab, privacy_tab, quality_tab, data_tab = st.tabs(
    ["Overview", "Cohort evidence", "Identifier screening", "Data quality", "Data preview"]
)

with overview_tab:
    if representation["findings"]:
        st.markdown("### What needs review")
        for finding in representation["findings"]:
            priority_card(finding)
    elif representation["status"] == "insufficient_evidence":
        st.info("Representation evidence is insufficient. Select a populated demographic column.")
    else:
        st.markdown("### No representation rules triggered")
        st.write(
            "Observed proportions are descriptive. MedGuard v1 does not apply a universal "
            "percentage-gap threshold or label the dataset fair."
        )
    st.markdown("### What this review does not establish")
    for limitation in representation["limitations"]:
        st.write(f"- {limitation}")
    st.write("- Identifier screening is heuristic and does not certify de-identification.")

with cohorts_tab:
    if not representation["attributes"]:
        st.info("Select at least one demographic column to view cohort evidence.")
    for attribute in representation["attributes"]:
        st.markdown(f"### {attribute['column']}")
        rows = []
        for group in attribute["groups"]:
            rows.append(
                {
                    "Group": group["label"],
                    "Records": group["count"],
                    "Observed share": (
                        f"{group['proportion']:.1%}" if group["proportion"] is not None else "Unavailable"
                    ),
                    "Reference": (
                        f"{group['reference_proportion']:.1%}"
                        if group["reference_proportion"] is not None
                        else "Not supplied"
                    ),
                    "Difference": (
                        f"{group['difference_pp']:+.1f} pp"
                        if group["difference_pp"] is not None
                        else "Not calculated"
                    ),
                }
            )
        table = pd.DataFrame(rows)
        chart_values = pd.DataFrame(
            {
                "Observed share (%)": [
                    round(group["proportion"] * 100, 1)
                    if group["proportion"] is not None else 0
                    for group in attribute["groups"]
                ]
            },
            index=[group["label"] for group in attribute["groups"]],
        )
        chart_col, table_col = st.columns([0.85, 1.15])
        with chart_col:
            st.bar_chart(chart_values, height=245, color="#17998f")
        with table_col:
            st.dataframe(table, use_container_width=True, hide_index=True)
        st.caption(
            f"Denominator: {attribute['observed_count']:,} nonmissing values. "
            f"Missing values: {attribute['missing_count']:,}."
        )
    with st.expander("Measured representation result"):
        st.json(representation)

with privacy_tab:
    st.markdown("### Potential identifier screening")
    st.markdown(
        '<div class="mg-warning"><strong>This is a screening result, not privacy clearance.</strong> '
        'A result with no listed patterns does not establish HIPAA de-identification.</div>',
        unsafe_allow_html=True,
    )
    st.write(f"**Status:** {SCREENING_STATUS_LABELS[screening['status']]}")
    coverage = screening["coverage"]
    coverage_cols = st.columns(3)
    coverage_cols[0].metric("Rows screened", f"{coverage['rows_scanned']:,}")
    coverage_cols[1].metric("Columns screened", f"{coverage['column_count']:,}")
    coverage_cols[2].metric("Checks applied", f"{len(coverage['checks']):,}")
    st.caption(
        f"Checked column names and values across {coverage['rows_scanned']:,} of "
        f"{coverage['row_count']:,} rows and {coverage['column_count']:,} columns."
    )
    if screening["findings"]:
        for finding in screening["findings"]:
            priority_card(finding)
    else:
        st.info("None of the listed identifier patterns matched in the reported coverage.")
    with st.expander("Scope and limitations"):
        for limitation in screening["limitations"]:
            st.write(f"- {limitation}")
    with st.expander("Measured screening result"):
        st.json(screening)

with quality_tab:
    quality_cols = st.columns(3)
    quality_cols[0].metric("Missing cells", f"{quality['missing_cells']:,}")
    quality_cols[1].metric("Columns with missing data", quality["columns_with_missing_values"])
    quality_cols[2].metric("Rows in duplicate sets", quality["duplicate_rows"])
    if quality["missing_by_column"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {"Column": column, "Missing values": count}
                    for column, count in quality["missing_by_column"].items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No missing cells were observed.")
    st.caption("These are descriptive quality counts; no automatic cleaning has been applied.")

with data_tab:
    st.dataframe(data.head(20), use_container_width=True, hide_index=True)
    st.caption("Showing the first 20 rows. The source dataset remains unchanged.")

st.markdown('<div id="reviewed-context"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Reviewed context · W04</div>'
    '<div class="mg-section-title">Evidence behind the boundaries</div></div>'
    '<div class="mg-section-copy">These reviewed sources explain why MedGuard reports limits. '
    'They are context for human review, not retrieved advice or compliance clearance.</div></div>',
    unsafe_allow_html=True,
)
source_columns = st.columns(len(REVIEWED_SOURCES))
for source_column, source_item in zip(source_columns, REVIEWED_SOURCES):
    with source_column:
        st.markdown(
            '<article class="mg-source-card">'
            f'<div class="mg-source-label">{escape(source_item["label"])} · '
            f'{escape(source_item["id"])}</div>'
            f'<div class="mg-source-title">{escape(source_item["title"])}</div>'
            f'<div class="mg-source-publisher">{escape(source_item["publisher"])}</div>'
            f'<div class="mg-source-summary">{escape(source_item["summary"])}</div>'
            f'<a class="mg-source-link" href="{escape(source_item["url"])}" '
            'target="_blank" rel="noreferrer">Open reviewed source ↗</a>'
            '</article>',
            unsafe_allow_html=True,
        )
st.caption(
    "Source inventory reviewed October 24, 2026. Retrieval and embeddings remain disabled until "
    "they pass an end-to-end test."
)

st.markdown('<div id="preview-changes"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Controlled next step</div>'
    '<div class="mg-section-title">Preview supported changes</div></div>'
    '<div class="mg-section-copy">Every action runs on a separate copy. Protected roles are '
    'excluded from change targets.</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="mg-warning"><strong>Automatic mitigation remains disabled.</strong> '
    'Resampling, SMOTE, and demographic balancing are not available. A preview does not show '
    'that a change improves model accuracy or fairness.</div>',
    unsafe_allow_html=True,
)

protected_columns = {
    column for column, role in column_roles.items() if role != "feature"
}
feature_columns = [column for column in columns if column not in protected_columns]
missing_feature_columns = [column for column in feature_columns if data[column].isna().any()]
text_feature_columns = [
    column for column in feature_columns
    if pd.api.types.is_object_dtype(data[column]) or pd.api.types.is_string_dtype(data[column])
]
fill_feature_columns = [
    column for column in missing_feature_columns if not pd.api.types.is_bool_dtype(data[column])
]

selected_change_labels = st.multiselect(
    "Choose supported changes",
    list(CHANGE_ACTIONS),
    key="selected_change_actions",
    help="Actions run in the order shown below. Any blocked action blocks the whole preview.",
)
requested_actions = []
configuration_complete = True

if "Remove exact duplicate rows" in selected_change_labels:
    requested_actions.append({"action": "drop_duplicate_rows"})

if "Remove rows missing selected feature values" in selected_change_labels:
    if feature_columns:
        missing_row_columns = st.multiselect(
            "Features required for row retention",
            feature_columns,
            default=missing_feature_columns[:1],
            key="change_drop_missing_columns",
        )
        if missing_row_columns:
            requested_actions.append(
                {"action": "drop_rows_with_missing", "columns": missing_row_columns}
            )
        else:
            configuration_complete = False
            st.warning("Select at least one unprotected feature for the missing-row rule.")
    else:
        configuration_complete = False
        st.warning("No unprotected feature columns are available for the missing-row rule.")

if "Fill missing feature values" in selected_change_labels:
    if fill_feature_columns:
        fill_column = st.selectbox(
            "Feature to fill",
            fill_feature_columns,
            key="change_fill_column",
        )
        numeric_fill = pd.api.types.is_numeric_dtype(data[fill_column])
        fill_method_label = st.radio(
            "Fill method",
            ["Median", "Constant"] if numeric_fill else ["Constant"],
            horizontal=True,
            key=f"change_fill_method_{fill_column}",
        )
        fill_action = {
            "action": "fill_missing",
            "column": fill_column,
            "method": fill_method_label.lower(),
        }
        if fill_method_label == "Constant":
            if numeric_fill:
                fill_action["value"] = st.number_input(
                    "Constant value", value=0.0,
                    key=f"change_fill_numeric_value_{fill_column}",
                )
            else:
                fill_action["value"] = st.text_input(
                    "Constant value", value="Not recorded",
                    key=f"change_fill_text_value_{fill_column}",
                )
        requested_actions.append(fill_action)
    else:
        configuration_complete = False
        st.warning("No unprotected columns with missing values can be filled.")

if "Trim leading and trailing whitespace" in selected_change_labels:
    if text_feature_columns:
        whitespace_column = st.selectbox(
            "Text feature to trim",
            text_feature_columns,
            key="change_whitespace_column",
        )
        requested_actions.append({"action": "strip_whitespace", "column": whitespace_column})
    else:
        configuration_complete = False
        st.warning("No unprotected text feature is available for whitespace trimming.")

if "Remove a feature column" in selected_change_labels:
    if feature_columns:
        drop_column = st.selectbox(
            "Feature column to remove",
            feature_columns,
            key="change_drop_column",
        )
        requested_actions.append({"action": "drop_column", "column": drop_column})
    else:
        configuration_complete = False
        st.warning("No unprotected feature column is available to remove.")

change_context = json.dumps(
    {
        "source_fingerprint": report["dataset"]["fingerprint"],
        "column_roles": column_roles,
        "actions": requested_actions,
    },
    sort_keys=True,
)
if st.session_state.get("change_preview_context") not in (None, change_context):
    for stale_key in ("change_preview_result", "change_preview_frame", "accepted_change_context"):
        st.session_state.pop(stale_key, None)
    st.session_state["change_preview_context"] = change_context

preview_col, reset_col = st.columns([3, 1])
preview_clicked = preview_col.button(
    "Generate change preview",
    type="primary",
    disabled=not selected_change_labels or not configuration_complete,
    use_container_width=True,
)
reset_col.button(
    "Reset changes",
    on_click=clear_change_state,
    use_container_width=True,
)

if preview_clicked:
    try:
        preview_result, preview_frame = preview_changes(
            data,
            requested_actions,
            column_roles=column_roles,
        )
    except ChangePreviewError as error:
        st.error(f"The change request could not be previewed: {error}")
    else:
        st.session_state["change_preview_context"] = change_context
        st.session_state["change_preview_result"] = preview_result
        st.session_state["change_preview_frame"] = preview_frame
        st.session_state.pop("accepted_change_context", None)

preview_result = st.session_state.get("change_preview_result")
preview_frame = st.session_state.get("change_preview_frame")
preview_current = st.session_state.get("change_preview_context") == change_context
accepted = st.session_state.get("accepted_change_context") == change_context

if preview_result and preview_current:
    if preview_result["status"] == "blocked":
        st.error("This change set is blocked. No partial output was created.")
    else:
        before = preview_result["before"]
        after = preview_result["after"]
        st.markdown(
            '<div class="mg-preview"><div class="mg-preview-ready">Preview ready</div>'
            '<div class="mg-title">Source preserved · separate output prepared</div>'
            '<div class="mg-copy">Review every action and limitation before accepting this '
            'copy for export.</div></div>',
            unsafe_allow_html=True,
        )
        preview_metrics = st.columns(4)
        preview_metrics[0].metric("Rows before", f"{before['row_count']:,}")
        preview_metrics[1].metric(
            "Rows after",
            f"{after['row_count']:,}",
            delta=after["row_count"] - before["row_count"],
        )
        preview_metrics[2].metric("Columns before", f"{before['column_count']:,}")
        preview_metrics[3].metric(
            "Columns after",
            f"{after['column_count']:,}",
            delta=after["column_count"] - before["column_count"],
        )

    st.markdown("#### Action evidence")
    for action in preview_result["actions"]:
        title = escape(action["action"].replace("_", " ").title())
        status = escape(action["status"].replace("_", " ").title())
        st.markdown(f"**{title} · {status}**")
        if action["reason"]:
            st.write(action["reason"])
        if action["evidence"]:
            st.json(action["evidence"])
        for warning in action["warnings"]:
            st.warning(warning)

    with st.expander("Preview limitations and full evidence"):
        for limitation in preview_result["limitations"]:
            st.write(f"- {limitation}")
        st.json(preview_result)

    if preview_result["status"] == "preview_ready" and preview_frame is not None:
        accept_col, copy_col = st.columns(2)
        if accept_col.button(
            "Accept preview for export",
            disabled=accepted,
            use_container_width=True,
        ):
            st.session_state["accepted_change_context"] = change_context
            accepted = True
        if accepted:
            accept_col.success("Accepted for export. The audited source remains unchanged.")
            copy_col.download_button(
                "Download reviewed copy",
                data=reviewed_copy_csv(preview_frame),
                file_name="medguard-reviewed-copy.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            copy_col.caption("Accept the preview to enable the separate output download.")

export_report = dict(report)
if preview_result and preview_current:
    export_report["change_preview"] = dict(preview_result)
    export_report["change_preview"]["accepted_for_export"] = accepted

st.markdown('<div id="optional-explanation"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Optional · explicit request</div>'
    '<div class="mg-section-title">Explain the aggregate evidence</div></div>'
    '<div class="mg-section-copy">The local model receives aggregate counts and statuses only. '
    'Original records, cell values, labels, column names, and file names stay out of the prompt.'
    '</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="mg-warning"><strong>Reviewed sources are available; retrieval is not.</strong> '
    'W04 verified the source inventory shown above, but embedding and retrieval have not passed '
    'an end-to-end test. The optional explanation uses aggregate audit evidence only and remains '
    'unverified.</div>',
    unsafe_allow_html=True,
)
explanation_col, model_col = st.columns([2, 1])
with explanation_col:
    explanation_context = st.selectbox(
        "Explanation focus",
        ALLOWED_CONTEXTS,
        key="explanation_context",
    )
with model_col:
    explanation_model = st.selectbox(
        "Local model",
        [DEFAULT_MODEL],
        key="explanation_model",
        help="S04 uses local Ollama only; no cloud provider is called.",
    )

current_explanation_key = explanation_cache_key(
    export_report,
    explanation_context,
    explanation_model,
)
if st.session_state.get("explanation_result_key") not in (None, current_explanation_key):
    st.session_state.pop("explanation_result", None)
    st.session_state.pop("explanation_result_key", None)

if st.button("Generate optional explanation", use_container_width=True):
    cache = st.session_state.setdefault("explanation_cache", {})
    with st.spinner("Asking the local model for a bounded explanation…"):
        explanation_result = generate_explanation(
            export_report,
            context=explanation_context,
            model=explanation_model,
            cache=cache,
            timeout_seconds=8,
        )
    st.session_state["explanation_result"] = explanation_result
    st.session_state["explanation_result_key"] = current_explanation_key

explanation_result = st.session_state.get("explanation_result")
explanation_current = st.session_state.get("explanation_result_key") == current_explanation_key
if explanation_result and explanation_current:
    content = explanation_result["content"]
    if explanation_result["status"] == "fallback":
        st.warning(
            "The local AI explanation was unavailable, slow, malformed, or failed safety checks. "
            "Showing a deterministic summary instead."
        )
    else:
        cache_note = " · cache hit" if explanation_result["cache_hit"] else ""
        st.success(f"Local explanation generated{cache_note}. Review it before use.")
    st.markdown(
        f'<div class="mg-explanation"><div class="mg-section-kicker">Unverified explanation</div>'
        f'<div class="mg-title">{escape(content["headline"])}</div></div>',
        unsafe_allow_html=True,
    )
    explanation_tabs = st.tabs(["Observations", "Unknowns", "Questions", "Technical details"])
    with explanation_tabs[0]:
        for item in content["observations"]:
            st.write(f"- {item}")
    with explanation_tabs[1]:
        for item in content["unknowns"]:
            st.write(f"- {item}")
    with explanation_tabs[2]:
        for item in content["next_questions"]:
            st.write(f"- {item}")
    with explanation_tabs[3]:
        st.write(
            f"Status: `{explanation_result['status']}` · Model: `{explanation_result['model']}` · "
            f"Prompt: `{explanation_result['prompt_version']}`"
        )
        if explanation_result["reason"]:
            st.caption(explanation_result["reason"])
        for limitation in explanation_result["limitations"]:
            st.write(f"- {limitation}")
    export_report["optional_explanation"] = explanation_result

st.markdown('<div id="export-evidence"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="mg-export"><div class="mg-section-kicker">Portable evidence</div>'
    '<div class="mg-title">Export the audit record</div>'
    '<div class="mg-copy">JSON preserves the complete machine-readable result. CSV provides '
    'a compact table for review and handoff. A current preview is included with its acceptance '
    'state.</div></div>',
    unsafe_allow_html=True,
)
export_col1, export_col2 = st.columns(2)
export_col1.download_button(
    "Download JSON report",
    data=report_json(export_report),
    file_name="medguard-audit.json",
    mime="application/json",
    use_container_width=True,
)
export_col2.download_button(
    "Download CSV evidence",
    data=report_csv(export_report),
    file_name="medguard-audit.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(
    "MedGuard is a dataset-readiness prototype. It does not provide clinical advice, certify "
    "de-identification, measure model performance, or establish that a model is fair or safe."
)
