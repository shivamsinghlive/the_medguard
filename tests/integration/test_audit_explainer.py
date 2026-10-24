"""S04 optional explanations: prompt minimization, cache identity, and fallbacks."""

import json
from pathlib import Path
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from agents.audit_explainer import (
    ALLOWED_CONTEXTS,
    ExplanationError,
    build_evidence_payload,
    build_prompt,
    explanation_cache_key,
    generate_explanation,
)


def audit_report(fingerprint="fingerprint-one"):
    return {
        "dataset": {
            "fingerprint": fingerprint,
            "source_type": "uploaded_csv",
            "source_name": "SECRET_PATIENT_FILE.csv",
            "row_count": 3,
            "column_count": 4,
        },
        "quality": {
            "missing_cells": 1,
            "columns_with_missing_values": 1,
            "missing_by_column": {"patient_full_name": 1},
            "duplicate_rows": 0,
        },
        "representation": {
            "status": "review_needed",
            "attributes": [{
                "column": "patient_full_name",
                "status": "review_needed",
                "observed_count": 3,
                "missing_count": 0,
                "groups": [
                    {"label": "SECRET_ALICE", "count": 2, "proportion": 2 / 3,
                     "reference_proportion": 0.5, "difference_pp": 16.666},
                    {"label": "SECRET_BOB", "count": 1, "proportion": 1 / 3,
                     "reference_proportion": 0.5, "difference_pp": -16.666},
                ],
            }],
            "findings": [{
                "code": "missing_reference_group",
                "column": "patient_full_name",
                "priority": "high",
                "title": "Expected group is missing",
                "evidence": {"missing_groups": ["SECRET_CAROL"], "observed_count": 3},
            }],
            "limitations": ["SECRET_LIMITATION"],
        },
        "identifier_screening": {
            "status": "review_needed",
            "certifies_deidentification": False,
            "coverage": {"row_count": 3, "rows_scanned": 3, "column_count": 4,
                         "complete": True, "checks": ["email_pattern"]},
            "findings": [{
                "code": "email_pattern",
                "column": "patient_email",
                "priority": "high",
                "title": "Email values found",
                "evidence": {"matching_values": 1, "raw": "secret@example.org"},
            }],
            "limitations": ["SECRET_PRIVACY_TEXT"],
        },
        "model_performance": {"status": "not_measured"},
    }


VALID_CONTENT = {
    "headline": "Review the measured audit evidence",
    "observations": ["Three rows were validated and one review flag was recorded."],
    "unknowns": ["Model performance was not measured."],
    "next_questions": ["Does the selected scope match the intended population?"],
}


def test_prompt_excludes_records_labels_columns_file_names_and_free_text():
    report = audit_report()
    prompt = build_prompt(report, "Audit overview")
    encoded = json.dumps(build_evidence_payload(report))
    for secret in (
        "SECRET_PATIENT_FILE", "patient_full_name", "SECRET_ALICE", "SECRET_BOB",
        "SECRET_CAROL", "patient_email", "secret@example.org", "SECRET_LIMITATION",
        "SECRET_PRIVACY_TEXT",
    ):
        assert secret not in prompt
        assert secret not in encoded
    assert '"row_count": 3' in prompt
    assert '"matching_values": 1' in prompt


def test_generation_is_explicit_structured_and_json_safe():
    calls = []

    def provider(prompt, model, timeout):
        calls.append((prompt, model, timeout))
        return json.dumps(VALID_CONTENT)

    result = generate_explanation(
        audit_report(), context="Audit overview", provider=provider, timeout_seconds=1
    )
    assert result["status"] == "generated"
    assert result["requested"] is True
    assert result["content"] == VALID_CONTENT
    assert len(calls) == 1
    json.dumps(result, allow_nan=False)


def test_successful_result_uses_stable_cache():
    calls = []

    def provider(*args):
        calls.append(args)
        return VALID_CONTENT

    cache = {}
    first = generate_explanation(audit_report(), context="Representation evidence",
                                 provider=provider, cache=cache)
    second = generate_explanation(audit_report(), context="Representation evidence",
                                  provider=provider, cache=cache)
    assert len(calls) == 1
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["content"] == first["content"]


def test_cache_identity_changes_with_input_context_and_model():
    base = audit_report()
    key = explanation_cache_key(base, "Audit overview", "model-a")
    assert key != explanation_cache_key(audit_report("different"), "Audit overview", "model-a")
    assert key != explanation_cache_key(base, "Representation evidence", "model-a")
    assert key != explanation_cache_key(base, "Audit overview", "model-b")


def test_timeout_returns_quick_visible_fallback():
    def slow_provider(*args):
        time.sleep(0.3)
        return VALID_CONTENT

    started = time.monotonic()
    result = generate_explanation(
        audit_report(), context="Audit overview", provider=slow_provider, timeout_seconds=0.02
    )
    assert time.monotonic() - started < 0.15
    assert result["status"] == "fallback"
    assert result["reason"] == "timeout"
    assert result["content"]["unknowns"]


@pytest.mark.parametrize("response", [
    "not json",
    {"headline": "Missing required lists"},
    {
        "headline": "The dataset is fair",
        "observations": ["Everything looks good."],
        "unknowns": ["Nothing is unknown."],
        "next_questions": ["Can we deploy?"],
    },
    {
        "headline": "Recruit 552 people",
        "observations": ["This will improve accuracy."],
        "unknowns": ["Cost is $45,000."],
        "next_questions": ["Can recruitment begin?"],
    },
    {
        "headline": "Review the aggregate evidence",
        "observations": ["Apply SMOTE before training."],
        "unknowns": ["Clinical impact was not measured."],
        "next_questions": ["What evaluation protocol will be used?"],
    },
    {
        "headline": "Review the aggregate evidence",
        "observations": ["Recruit more participants from the smaller group."],
        "unknowns": ["The estimated cost is unknown."],
        "next_questions": ["What evaluation protocol will be used?"],
    },
])
def test_malformed_or_unsupported_output_uses_fallback(response):
    result = generate_explanation(
        audit_report(), context="Audit overview", provider=lambda *args: response
    )
    assert result["status"] == "fallback"
    combined = json.dumps(result["content"]).lower()
    assert "dataset is fair" not in combined
    assert "recruit 552" not in combined


def test_provider_failure_uses_fallback_and_is_not_cached():
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise ConnectionError("local model unavailable")

    cache = {}
    first = generate_explanation(audit_report(), context="Audit overview",
                                 provider=unavailable, cache=cache)
    second = generate_explanation(audit_report(), context="Audit overview",
                                  provider=unavailable, cache=cache)
    assert first["status"] == second["status"] == "fallback"
    assert len(calls) == 2
    assert cache == {}


def test_context_is_controlled_not_free_form():
    with pytest.raises(ExplanationError, match="Unsupported explanation context"):
        build_prompt(audit_report(), "Here are patient details")
    assert "Audit overview" in ALLOWED_CONTEXTS
