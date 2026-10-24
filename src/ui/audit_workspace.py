"""MedGuard's evidence-first dataset audit workspace."""

from __future__ import annotations

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
    page_title="MedGuard Audit Workspace",
    page_icon="MG",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
      --mg-ink: #102a43; --mg-muted: #52667a; --mg-teal: #087f8c;
      --mg-teal-soft: #e6f6f7; --mg-amber: #a15c00;
      --mg-amber-soft: #fff4df; --mg-border: #d9e2ec;
    }
    .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3 { color: var(--mg-ink); letter-spacing: -0.02em; }
    p, li { color: var(--mg-muted); }
    .mg-eyebrow { color: var(--mg-teal); font-size: .78rem; font-weight: 700;
      letter-spacing: .09em; text-transform: uppercase; margin-bottom: .45rem; }
    .mg-lede { color: var(--mg-muted); font-size: 1.05rem; max-width: 760px;
      line-height: 1.65; margin-bottom: 1.4rem; }
    .mg-chip { display: inline-block; border: 1px solid #abdadd; border-radius: 999px;
      background: var(--mg-teal-soft); color: #075b63; padding: .28rem .65rem;
      margin: 0 .4rem .4rem 0; font-size: .78rem; font-weight: 650; }
    .mg-card { border: 1px solid var(--mg-border); border-radius: 14px; background: white;
      padding: 1rem 1.05rem; margin: .55rem 0; box-shadow: 0 4px 18px rgba(16,42,67,.05); }
    .mg-priority { color: var(--mg-amber); font-size: .72rem; font-weight: 750;
      letter-spacing: .07em; text-transform: uppercase; }
    .mg-title { color: var(--mg-ink); font-size: 1rem; font-weight: 720; margin: .25rem 0; }
    .mg-copy { color: var(--mg-muted); font-size: .9rem; line-height: 1.5; }
    .mg-note { border-left: 4px solid var(--mg-teal); border-radius: 8px;
      background: var(--mg-teal-soft); padding: .85rem 1rem; color: #164e55; }
    .mg-warning { border-left: 4px solid #c77700; border-radius: 8px;
      background: var(--mg-amber-soft); padding: .85rem 1rem; color: #714000; }
    [data-testid="stMetric"] { border: 1px solid var(--mg-border); border-radius: 12px;
      background: white; padding: .8rem 1rem; }
    [data-testid="stMetricValue"] { color: var(--mg-ink); font-size: 1.55rem; }
    [data-testid="stSidebar"] { background: #f6f9fb; border-right: 1px solid var(--mg-border); }
    .stButton > button:focus, .stDownloadButton > button:focus {
      outline: 3px solid #62c5ca; outline-offset: 2px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def priority_card(finding: dict) -> None:
    label = PRIORITY_LABELS.get(finding["priority"], "Review")
    st.markdown(
        f"""
        <div class="mg-card">
          <div class="mg-priority">{label}</div>
          <div class="mg-title">{finding['title']}</div>
          <div class="mg-copy">{finding_summary(finding)}</div>
          <div class="mg-copy"><strong>Next:</strong> {finding['suggested_action']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reference_for_demo(enabled: bool, columns: list[str]) -> dict | None:
    if enabled and "sex" in columns:
        return {"sex": {"Male": 0.5, "Female": 0.5}}
    return None


with st.sidebar:
    st.markdown("### Audit setup")
    source = st.radio(
        "Data source",
        ["Guided demo", "Upload CSV"],
        help="The guided demo opens immediately and uses synthetic records.",
    )
    st.divider()
    st.caption("Analysis scope")
    st.write("Dataset readiness and cohort representation before model training.")
    st.caption("Current boundary")
    st.write("No model performance, clinical harm, privacy certification, or automatic mitigation.")


st.markdown('<div class="mg-eyebrow">Healthcare dataset review</div>', unsafe_allow_html=True)
st.title("Know what your dataset can support")
st.markdown(
    '<div class="mg-lede">Inspect measured evidence, cohort coverage, and unknowns before '
    'building a model. MedGuard keeps observations separate from assumptions and suggestions.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<span class="mg-chip">Original records preserved</span>'
    '<span class="mg-chip">AI optional</span>'
    '<span class="mg-chip">Unknowns shown explicitly</span>',
    unsafe_allow_html=True,
)


if source == "Guided demo":
    validation, data = validate_input(DEMO_PATH.read_bytes())
    source_label = "Synthetic diabetes cohort"
    source_type = "bundled_synthetic_demo"
    st.markdown(
        '<div class="mg-note"><strong>Live guided demo.</strong> The records are bundled '
        'synthetic data. Counts, proportions, missingness, and findings below are calculated '
        'by the merged deterministic representation service.</div>',
        unsafe_allow_html=True,
    )
else:
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded is None:
        st.info("Choose a CSV to assign column roles and run deterministic representation analysis.")
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
    f"Input accepted: {validation['byte_count']:,} bytes, {validation['row_count']:,} rows, "
    f"{validation['column_count']:,} columns. Limits: 25 MB, 200,000 rows, 500 columns."
)


st.markdown("## Review scope")
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
    st.selectbox(
        "Outcome column (optional)",
        ["Not selected"] + columns,
        index=(columns.index(suggested_outcomes[0]) + 1) if suggested_outcomes else 0,
    )
with role_col3:
    st.multiselect(
        "Identifier columns",
        columns,
        default=suggested_ids,
        help="Identifiers are excluded from future proposed transformations.",
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

st.divider()
st.markdown(f"### {source_label}")
metric_cols = st.columns(4)
metric_cols[0].metric("Records", f"{report['dataset']['row_count']:,}")
metric_cols[1].metric("Attributes assessed", len(representation["attributes"]))
metric_cols[2].metric("Representation flags", len(representation["findings"]))
metric_cols[3].metric("Identifier signals", len(screening["findings"]))
st.caption(
    f"Representation status: {STATUS_LABELS[representation['status']]}. "
    "This is an evidence state, not a fairness verdict."
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
        st.markdown("### No rule-based review flags")
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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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


st.divider()
st.markdown("## Export audit evidence")
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

st.markdown("## Changes to the dataset")
st.markdown(
    '<div class="mg-warning"><strong>Automatic mitigation is disabled.</strong> The legacy '
    'SMOTE and oversampling controls could alter outcomes or create inconsistent records. '
    'Changes will be enabled only after a source-preserving preview service is tested.</div>',
    unsafe_allow_html=True,
)
st.button("Preview supported changes", disabled=True, help="Available after W03 integration")

st.caption(
    "MedGuard is a dataset-review prototype. It does not provide clinical advice, certify "
    "de-identification, or establish that a model is fair or safe."
)
