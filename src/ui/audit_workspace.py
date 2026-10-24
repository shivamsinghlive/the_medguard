"""MedGuard's evidence-first audit workspace.

The guided demo uses a clearly labeled contract fixture until the W01
representation service is integrated. Uploaded datasets are previewed but are
not assigned representation findings by this UI layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


SRC_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from ui.demo_fixtures import diabetes_gender_demo


DEMO_PATH = PROJECT_DIR / "data/synthetic/dataset2_diabetes_gender_bias.csv"
PRIORITY_LABELS = {"high": "Review first", "medium": "Review next", "low": "Context"}


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
      --mg-ink: #102a43;
      --mg-muted: #52667a;
      --mg-teal: #087f8c;
      --mg-teal-soft: #e6f6f7;
      --mg-amber: #a15c00;
      --mg-amber-soft: #fff4df;
      --mg-border: #d9e2ec;
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


def read_demo() -> pd.DataFrame:
    return pd.read_csv(DEMO_PATH)


def priority_card(finding: dict) -> None:
    label = PRIORITY_LABELS.get(finding["priority"], "Review")
    st.markdown(
        f"""
        <div class="mg-card">
          <div class="mg-priority">{label}</div>
          <div class="mg-title">{finding['title']}</div>
          <div class="mg-copy">{finding['summary']}</div>
          <div class="mg-copy"><strong>Next:</strong> {finding['suggested_action']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    data = read_demo()
    result = diabetes_gender_demo()
    source_label = "Synthetic diabetes cohort"
    st.markdown(
        '<div class="mg-note"><strong>Guided interface demo.</strong> The records are bundled '
        'synthetic data. Representation results below are a fixed v1 contract fixture while '
        'Swathi\'s analysis service is developed; they are not recalculated by this UI.</div>',
        unsafe_allow_html=True,
    )
else:
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded is None:
        st.info("Choose a CSV to preview its columns and assign roles. No analysis runs before upload.")
        st.stop()
    try:
        data = pd.read_csv(uploaded)
    except Exception:
        st.error("This file could not be read as CSV. Check its format and encoding.")
        st.stop()
    result = None
    source_label = uploaded.name
    st.markdown(
        '<div class="mg-warning"><strong>Preview only.</strong> The file is loaded locally for '
        'role selection. Representation findings will remain unavailable until the tested W01 '
        'analysis service is integrated.</div>',
        unsafe_allow_html=True,
    )


st.markdown("## Review scope")
role_col1, role_col2, role_col3 = st.columns(3)
columns = list(data.columns)
suggested_demographics = [c for c in columns if c.lower() in {"sex", "gender", "race_ethnicity"}]
suggested_outcomes = [c for c in columns if c.lower() in {"outcome", "target", "diabetes", "heart_disease"}]
suggested_ids = [c for c in columns if c.lower().endswith("_id")]
with role_col1:
    demographic_columns = st.multiselect(
        "Demographic columns",
        columns,
        default=suggested_demographics[:1],
        help="Select explicitly. Numeric codes are not mapped automatically.",
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
        help="Identifiers are excluded from proposed transformations.",
    )

if source == "Guided demo" and demographic_columns != ["sex"]:
    st.warning(
        "This fixture covers only the `sex` column. Your role selection is saved for the "
        "future analysis-service integration, but the displayed fixture remains unchanged."
    )


st.divider()
st.markdown(f"### {source_label}")
metric_cols = st.columns(4)
metric_cols[0].metric("Records", f"{len(data):,}")
metric_cols[1].metric("Columns", f"{len(data.columns):,}")
if result:
    metric_cols[2].metric("Priority findings", len(result["findings"]))
    metric_cols[3].metric("Performance", "Not measured")
else:
    metric_cols[2].metric("Findings", "Pending")
    metric_cols[3].metric("Performance", "Not measured")


overview_tab, cohorts_tab, data_tab = st.tabs(["Overview", "Cohort evidence", "Data preview"])

with overview_tab:
    if result:
        st.markdown("### What needs attention")
        for finding in result["findings"]:
            priority_card(finding)
        st.markdown("### What this review does not establish")
        for limitation in result["limitations"]:
            st.write(f"- {limitation}")
    else:
        st.markdown("### Analysis pending")
        st.write(
            "The upload and role-selection experience is ready. This UI does not invent findings "
            "while the deterministic representation and screening services are still pending."
        )

with cohorts_tab:
    if result:
        attribute = result["attributes"][0]
        cohort_rows = []
        for group in attribute["groups"]:
            cohort_rows.append(
                {
                    "Group": group["label"],
                    "Records": group["count"],
                    "Observed share": f"{group['proportion']:.1%}",
                    "Demo reference": f"{group['reference_proportion']:.1%}",
                    "Difference": f"{group['difference_pp']:+.1f} pp",
                }
            )
        st.dataframe(pd.DataFrame(cohort_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Denominator: 1,200 nonmissing values. The demo reference is an explicit interface "
            "assumption and is not a universal fairness threshold."
        )
        with st.expander("Evidence details"):
            st.json(
                {
                    "schema_version": result["schema_version"],
                    "scope": result["scope"],
                    "status": result["status"],
                    "attribute": attribute,
                }
            )
    else:
        st.info("Cohort evidence will appear after the W01 service is integrated and tested.")

with data_tab:
    st.dataframe(data.head(20), use_container_width=True, hide_index=True)
    st.caption("Showing the first 20 rows. The source dataset remains unchanged.")


st.divider()
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
