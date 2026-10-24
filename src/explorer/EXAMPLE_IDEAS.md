# Example research ideas for the first page

Paste one into the Research idea form, then pick the matching bundled dataset. These are sample inputs only;
every result is still computed from the dataset.

## 1. Heart Disease Indigenous — missing focus group

| Field | Value |
|---|---|
| Project title | Heart disease risk for under-served groups |
| Research question | Can we predict heart disease reliably for Indigenous patients and women? |
| Outcome of interest | heart disease |
| Intended population | US adults in primary care |
| Groups you are concerned about | Indigenous patients, women, Black patients |
| Dataset | Heart Disease Indigenous |

Expect: a warning that "indigenous" is not in `race_ethnicity`; some combined groups (e.g. Hispanic x Female) below 10 cases.

## 2. Diabetes Gender Bias — women as the focus group

| Field | Value |
|---|---|
| Project title | Diabetes screening model for women |
| Research question | Will a diabetes model trained on this data work for women as well as men? |
| Outcome of interest | diabetes |
| Intended population | Adults aged 18-80 attending routine check-ups |
| Groups you are concerned about | women |
| Dataset | Diabetes Gender Bias |

Expect: Female has 324 rows (111 with diabetes); weak single-feature signal; `patient_id` flagged as an identifier.

## 3. Heart Disease Quality — data-quality problems

| Field | Value |
|---|---|
| Project title | Data quality check before heart disease modelling |
| Research question | Is this heart disease dataset clean enough to train a risk model for men and women? |
| Outcome of interest | heart disease |
| Intended population | Adults referred for cardiac testing |
| Groups you are concerned about | women, older adults |
| Dataset | Heart Disease Quality |

Expect: missing values (e.g. cholesterol) in the Missingness view; a note that age is continuous, so it is not used as a group.

## 4. Diabetes Combined — several groups at once

| Field | Value |
|---|---|
| Project title | Fair diabetes prediction across race and sex |
| Research question | Does this dataset have enough diabetes cases for Black, Hispanic and Asian patients and for women? |
| Outcome of interest | diabetes |
| Intended population | US adults in community health centres |
| Groups you are concerned about | Black patients, Hispanic patients, Asian patients, women |
| Dataset | Diabetes Combined |

Expect: the Intersections widget (race x sex) and per-group cell counts.

## 5. Test Synthetic Twin — vague idea

| Field | Value |
|---|---|
| Project title | Exploratory look |
| Research question | What does this dataset look like before modelling? |
| Outcome / population / groups | leave blank |
| Dataset | Test Synthetic Twin |

Expect: the planner may not pick an outcome, so you choose one on the plan screen.
