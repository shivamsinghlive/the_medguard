"""MedGuard's evidence-first dataset audit workspace."""

from __future__ import annotations

from html import escape
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from services.audit_runner import finding_summary, report_csv, report_json, run_audit
from services.contracts import RepresentationInputError
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
    .stApp { background: #f4f8f6; }
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
    .stButton > button:focus, .stDownloadButton > button:focus {
      outline: 3px solid #62c5ca; outline-offset: 2px;
    }
    @media (max-width: 700px) {
      .block-container { padding: .8rem .8rem 3rem; }
      .mg-hero { padding: 1.6rem 1.25rem; border-radius: 18px; }
      .mg-hero h1 { font-size: 2.2rem; }
      .mg-section { display: block; }
      .mg-section-copy { text-align: left; margin-top: .35rem; }
      .mg-status-row { grid-template-columns: 1fr; }
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


with st.sidebar:
    st.markdown(
        '<div class="mg-brand"><div class="mg-shield">MG</div><div>'
        '<div class="mg-brand-name">MedGuard</div><div class="mg-brand-sub">Evidence workspace</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("STEP 1 OF 3 · CHOOSE A SOURCE")
    source = st.radio(
        "Data source",
        ["Guided demo", "Upload CSV"],
        help="The guided demo opens immediately and uses synthetic records.",
    )
    st.divider()
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
    '<span class="mg-chip">Honest unknowns</span></div></div>',
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
role_col1, role_col2, role_col3 = st.columns(3)
with role_col1:
    demographic_columns = st.multiselect(
        "Demographic columns",
        columns,
        default=suggested_demographics[:1],
        help="Select explicitly. Numeric codes are retained and are never mapped automatically.",
    )
with role_col2:
    outcome_column = st.selectbox(
        "Outcome column (optional)",
        ["Not selected"] + columns,
        index=(columns.index(suggested_outcomes[0]) + 1) if suggested_outcomes else 0,
    )
with role_col3:
    identifier_columns = st.multiselect(
        "Identifier columns",
        columns,
        default=suggested_ids,
        help="Identifiers are excluded from future proposed transformations.",
    )

if outcome_column != "Not selected" or identifier_columns:
    st.caption(
        "Outcome and identifier selections are reserved for future safe-change controls; "
        "they do not change this audit. Controls remain disabled until W03 is integrated."
    )

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


st.markdown(
    '<div class="mg-export"><div class="mg-section-kicker">Portable evidence</div>'
    '<div class="mg-title">Export the audit record</div>'
    '<div class="mg-copy">JSON preserves the complete machine-readable result. CSV provides '
    'a compact table for review and handoff.</div></div>',
    unsafe_allow_html=True,
)
export_col1, export_col2 = st.columns(2)
export_col1.download_button(
    "Download JSON report",
    data=report_json(report),
    file_name="medguard-audit.json",
    mime="application/json",
    use_container_width=True,
)
export_col2.download_button(
    "Download CSV evidence",
    data=report_csv(report),
    file_name="medguard-audit.csv",
    mime="text/csv",
    use_container_width=True,
)

st.markdown(
    '<div class="mg-section"><div><div class="mg-section-kicker">Controlled next step</div>'
    '<div class="mg-section-title">Changes to the dataset</div></div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="mg-warning"><strong>Automatic mitigation is disabled.</strong> The legacy '
    'SMOTE and oversampling controls could alter outcomes or create inconsistent records. '
    'Changes will be enabled only after a source-preserving preview service is tested.</div>',
    unsafe_allow_html=True,
)
st.button("Preview supported changes", disabled=True, help="Available after W03 integration")

st.caption(
    "MedGuard is a dataset-readiness prototype. It does not provide clinical advice, certify "
    "de-identification, measure model performance, or establish that a model is fair or safe."
)
