# Knowledge-source inventory

Reviewed 2026-10-24 by Swathi (W04). The retrieval loader (`src/utils/medical_rag.py`) reads only `*.txt` files under `knowledge_base/`. This inventory is the reference for every claim in those files. Each claim carries a `[S#]` tag that points to a row below.

Being included here means a claim matches its cited source, nothing more. It does not make the claim clinical advice. It does not mean retrieval works: see [Retrieval and embeddings status](#retrieval-and-embeddings-status).

## Sources

"Checked" says how the claim was verified on the review date:
- **text read**: the cited wording was read in the source itself.
- **abstract read**: only the abstract or summary was read.
- **metadata only**: the bibliographic record was confirmed but the full text was not read.

| ID | Source | Publisher, date | URL | Checked | Claims it supports |
|---|---|---|---|---|---|
| S1 | ATP III Guidelines At-A-Glance Quick Desk Reference | NCEP / NHLBI, June 2001 | https://www.nhlbi.nih.gov/files/docs/guidelines/atglance.pdf | text read | Adult total cholesterol: <200 desirable, 200-239 borderline high, >=240 high (mg/dL). LDL >=190 mg/dL classed "very high". |
| S2 | Disparities fact sheet | Indian Health Service, October 2019 | https://www.ihs.gov/newsroom/factsheets/disparities/ | text read | AI/AN life expectancy 5.5 years less than U.S. all races (73.0 vs 78.5). Age-adjusted mortality ratios, AI/AN 2009-2011 vs U.S. all races 2010: heart disease 1.1, diabetes 3.2, stroke 1.1. |
| S3 | Mehta LS et al. Acute Myocardial Infarction in Women: A Scientific Statement From the American Heart Association. Circulation 2016;133(9):916-947. doi:10.1161/CIR.0000000000000351 | American Heart Association, published online 2016-01-25 | https://doi.org/10.1161/CIR.0000000000000351 | abstract read | Sex-specific differences exist in the presentation, pathophysiological mechanisms, and outcomes of acute myocardial infarction. |
| S4 | Good Machine Learning Practice for Medical Device Development: Guiding Principles | FDA, Health Canada, MHRA, October 2021 | https://www.fda.gov/media/153486/download | text read | Principle 3: participants and data sets should represent the intended patient population (e.g. age, sex, race, ethnicity). Principle 4: training and test sets are independent. Principle 8: testing considers important subgroups. Principle 9: users get model performance for appropriate subgroups and known limitations. No numeric subgroup threshold is stated. |
| S5 | Artificial Intelligence-Enabled Device Software Functions: Lifecycle Management and Marketing Submission Recommendations (docket FDA-2024-D-4488) | FDA, January 2025, **draft** guidance | https://www.fda.gov/regulatory-information/search-fda-guidance-documents/artificial-intelligence-enabled-device-software-functions-lifecycle-management-and-marketing | metadata only | Exists; labelled draft, "not for implementation", non-binding. Its detailed recommendations were not reviewed. |
| S6 | 45 CFR 164.514(b), implementation specifications for de-identification | U.S. Code of Federal Regulations (current text) via Cornell LII, accessed 2026-10-24 | https://www.law.cornell.edu/cfr/text/45/164.514 | text read | Two methods: expert determination (b)(1) and Safe Harbor (b)(2). Safe Harbor removes all date elements except year that relate directly to an individual, and all ages over 89, which may be aggregated into a single "90 or older" category. |
| S7 | Rubin DB. Inference and missing data. Biometrika 1976;63(3):581-592. doi:10.1093/biomet/63.3.581 | Biometrika, 1976 | https://doi.org/10.1093/biomet/63.3.581 | metadata only | Foundational paper on when the missing-data mechanism can be ignored. Cited only for provenance of the terminology. |
| S8 | Sterne JAC et al. Multiple imputation for missing data in epidemiological and clinical research: potential and pitfalls. BMJ 2009;338:b2393. doi:10.1136/bmj.b2393 | BMJ, published online 2009-06-29 | https://doi.org/10.1136/bmj.b2393 | text read | "Missing at random" is an assumption that justifies the analysis, not a property of the data. Analyses based on complete cases may be biased. |

## Claims removed from the previous knowledge base

These claims appeared in the earlier `.txt` files. They were removed because the source contradicted them, the source given was vague, or the claim could not be traced.

| Former file | Removed claim | Reason |
|---|---|---|
| regulatory/fda_ai_guidance.txt | Source "FDA 2021 Guidance Document"; "If performance differs >5% across groups, additional validation required" | No such FDA requirement found. S4 (Oct 2021) states no numeric threshold. The 2021 AI/ML Action Plan is not a guidance with these requirements. |
| regulatory/fda_ai_guidance.txt | Fairness metric calculations required; bias "can lead to 510(k) rejection"; post-market fairness surveillance required | Not supported by the reviewed documents. S5 detail not reviewed. |
| medical/indigenous_health_disparities.txt | Heart disease death rate 2x; stroke mortality 1.4x | Contradicted by S2: ratios 1.1 and 1.1. |
| medical/indigenous_health_disparities.txt | "Diabetes prevalence: 3x national average" | S2's 3.2 is a mortality ratio, not prevalence. A current CDC prevalence figure was not verified in this review. |
| medical/indigenous_health_disparities.txt | Hypertension 1.5x; contributing-factor list; "models ... will be completely unreliable"; partnership and tribal IRB recommendations | No source given or traced. "Completely unreliable" is an overclaim. |
| medical/cardiac_gender_differences.txt | Symptom percentages (e.g. chest pain 89% of men, fatigue 58% of women) | Attributed only to "JACC, CDC"; not traceable. |
| medical/cardiac_gender_differences.txt | "Women are 50% more likely to receive initial misdiagnosis" | Traced to a researcher's spoken remark reported by the University of Leeds about Wu J et al., Eur Heart J Acute Cardiovasc Care 2018;7(2):139-148 (doi:10.1177/2048872616661693). Not confirmed in the paper's text during this review. |
| medical/cardiac_gender_differences.txt | Higher mortality for women under 50 due to historical bias | Not traced to a source. |
| medical/cholesterol_guidelines.txt | "Very high: 400+ mg/dL" (total cholesterol); "twice the risk" at >=240 | Not an S1 category; the risk ratio was not traced. |
| medical/cholesterol_guidelines.txt | ">400 mg/dL ... most predictive cases"; "above 190 mg/dL typically warrant intervention" | Modelling claim unsupported. The 190 figure is an LDL threshold, not total cholesterol, and the 2018 guideline text was not reviewed. |
| statistical/imputation_methods.txt | Percentage cut-offs for choosing mean, KNN, MICE, or deletion (<5%, 5-20%, >20%, <3% and >5000 rows; skewness 0.5); source "Statistical Analysis Handbook" | Rules of thumb with no traceable source. |

## Retrieval and embeddings status

- Retrieval has **not** been verified end to end. The project's local Ollama service rejected embedding calls ("This server does not support embeddings", recorded in `docs/LOCAL_SETUP.md`), so `MedicalKnowledgeBase` cannot index these files on that service.
- Fixing retrieval means an embedding-capable service or model, followed by a retrieval test. That is backlog item 15 and is not part of W04.
- Retrieval quality does not validate sources. A retrieved chunk is only as reliable as the inventory row behind it.
- The deterministic audit and its tests do not use embeddings or retrieval. CI runs without Ollama, model downloads, or network access to models.
- Turning on source-grounded explanations in the UI is an integration decision (S04 owner). This inventory is what that decision should rely on.
