"""UI-only fixtures for the audit workspace.

These fixtures exercise the representation result contract while Swathi's W01
service is developed. They must never be presented as results calculated from
an uploaded file.
"""

from copy import deepcopy


DIABETES_GENDER_DEMO = {
    "schema_version": "1.0",
    "scope": "dataset_representation",
    "status": "review_needed",
    "row_count": 1200,
    "attributes": [
        {
            "column": "sex",
            "status": "review_needed",
            "observed_count": 1200,
            "missing_count": 0,
            "groups": [
                {
                    "label": "Male",
                    "count": 876,
                    "proportion": 0.73,
                    "reference_proportion": 0.50,
                    "difference_pp": 23.0,
                },
                {
                    "label": "Female",
                    "count": 324,
                    "proportion": 0.27,
                    "reference_proportion": 0.50,
                    "difference_pp": -23.0,
                },
            ],
        }
    ],
    "findings": [
        {
            "id": "sex:reference_gap",
            "code": "reference_gap",
            "column": "sex",
            "priority": "high",
            "title": "Female cohort differs from the selected reference",
            "summary": "324 of 1,200 records are labeled Female (27.0%).",
            "evidence": {
                "observed_count": 324,
                "observed_proportion": 0.27,
                "reference_proportion": 0.50,
                "difference_pp": -23.0,
            },
            "suggested_action": (
                "Confirm the intended-use population and review cohort coverage "
                "before model development."
            ),
        },
        {
            "id": "sex:performance_unknown",
            "code": "performance_not_measured",
            "column": "sex",
            "priority": "medium",
            "title": "Subgroup model performance is not measured",
            "summary": (
                "This dataset review has no held-out predictions, so performance "
                "differences and patient impact remain unknown."
            ),
            "evidence": {
                "performance_gap_percentage": None,
                "patients_affected_per_100": None,
            },
            "suggested_action": (
                "Add labels, held-out predictions, and an evaluation protocol "
                "before making performance claims."
            ),
        },
        {
            "id": "sex:reference_scope",
            "code": "reference_requires_review",
            "column": "sex",
            "priority": "medium",
            "title": "The reference population is an explicit assumption",
            "summary": (
                "The 50/50 reference is supplied for this interface demo. It is "
                "not a universal clinical or regulatory target."
            ),
            "evidence": {"reference_source": "guided_demo_assumption"},
            "suggested_action": (
                "Replace the demonstration reference with one justified for the "
                "project's intended population."
            ),
        },
    ],
    "quality_snapshot": {
        "duplicate_rows": 0,
        "missing_cells": 0,
        "columns": 14,
    },
    "limitations": [
        "This is a fixed interface fixture, not a newly calculated result.",
        "Representation does not measure model fairness or clinical harm.",
        "The 50/50 reference is supplied for demonstration and is not a default.",
        "Potential identifier screening does not certify de-identification.",
    ],
}


def diabetes_gender_demo() -> dict:
    """Return an isolated copy so UI state cannot mutate the shared fixture."""

    return deepcopy(DIABETES_GENDER_DEMO)
