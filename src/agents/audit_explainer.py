"""Optional, bounded explanations over aggregate audit evidence.

The active audit never calls this module automatically. Prompt construction
uses an explicit allowlist of aggregate counts and statuses, excluding records,
cell values, group labels, column names, and file names. Source-grounded RAG is
deliberately absent until embedding and retrieval pass an end-to-end test.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import queue
import re
import threading
from typing import Callable, MutableMapping, Optional


PROMPT_VERSION = "audit-explanation-1.0"
OUTPUT_SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "llama3.2:3b"
ALLOWED_CONTEXTS = (
    "Audit overview",
    "Representation evidence",
    "Identifier-screening limitations",
    "Change-preview evidence",
)

SYSTEM_RULES = """You explain aggregate healthcare dataset-audit evidence.
Use only the JSON evidence supplied below. Do not infer model performance,
clinical harm, fairness, safety, regulatory compliance, de-identification,
recruitment targets, costs, or accuracy changes. Do not recommend SMOTE or
automatic demographic balancing. Treat missing evidence as unknown. Use calm,
plain language. Return only JSON with exactly these keys:
{"headline": string, "observations": [string], "unknowns": [string],
 "next_questions": [string]}
Each list must contain 1 to 4 short items.
"""

_UNSUPPORTED_PATTERNS = (
    r"\bdataset (?:is|appears|seems) (?:fair|biased|safe)\b",
    r"\bsafe to (?:deploy|use|share)\b",
    r"\bdata (?:is|are) de-identified\b",
    r"\bhipaa[- ]compliant\b",
    r"\b(?:will|would|guaranteed to) improve accuracy\b",
    r"\b\d+(?:\.\d+)?%\s+(?:more|less)\s+accurate\b",
    r"\bpatients? (?:will|would) be harmed\b",
    r"\b(?:recruit|recruitment|recruiting|enroll|enrollment|enrolling)\b",
    r"\b(?:smote|oversampl(?:e|ing)|undersampl(?:e|ing))\b",
    r"\b(?:estimated\s+)?costs?\b",
    r"\$\s*\d+",
)


class ExplanationError(ValueError):
    """The explanation request or provider output is invalid."""


def _numbers_only(value):
    """Keep JSON-safe numeric evidence while discarding labels and free text."""

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        kept = [_numbers_only(item) for item in value]
        return [item for item in kept if item is not None]
    if isinstance(value, dict):
        kept = {str(key): _numbers_only(item) for key, item in value.items()}
        return {key: item for key, item in kept.items() if item is not None}
    return None


def build_evidence_payload(report: dict) -> dict:
    """Return prompt-safe aggregate evidence from an audit report."""

    dataset = report.get("dataset", {})
    quality = report.get("quality", {})
    representation = report.get("representation", {})
    screening = report.get("identifier_screening", {})

    attributes = []
    for attribute in representation.get("attributes", []):
        groups = attribute.get("groups", [])
        differences = [
            abs(group["difference_pp"])
            for group in groups
            if isinstance(group.get("difference_pp"), (int, float))
        ]
        attributes.append(
            {
                "status": attribute.get("status"),
                "observed_count": attribute.get("observed_count"),
                "missing_count": attribute.get("missing_count"),
                "observed_group_count": sum(1 for group in groups if group.get("count", 0) > 0),
                "group_counts_without_labels": sorted(
                    [int(group.get("count", 0)) for group in groups], reverse=True
                ),
                "largest_absolute_reference_difference_pp": max(differences) if differences else None,
            }
        )

    representation_findings = [
        {
            "code": finding.get("code"),
            "priority": finding.get("priority"),
            "evidence": _numbers_only(finding.get("evidence", {})),
        }
        for finding in representation.get("findings", [])
    ]
    screening_findings = [
        {
            "code": finding.get("code"),
            "priority": finding.get("priority"),
            "evidence": _numbers_only(finding.get("evidence", {})),
        }
        for finding in screening.get("findings", [])
    ]

    payload = {
        "dataset": {
            "row_count": dataset.get("row_count"),
            "column_count": dataset.get("column_count"),
        },
        "quality": {
            "missing_cells": quality.get("missing_cells"),
            "columns_with_missing_values": quality.get("columns_with_missing_values"),
            "duplicate_rows": quality.get("duplicate_rows"),
        },
        "representation": {
            "status": representation.get("status"),
            "attributes": attributes,
            "findings": representation_findings,
        },
        "identifier_screening": {
            "status": screening.get("status"),
            "certifies_deidentification": False,
            "coverage": _numbers_only(screening.get("coverage", {})),
            "findings": screening_findings,
        },
        "model_performance": {"status": "not_measured"},
    }

    change_preview = report.get("change_preview")
    if change_preview:
        payload["change_preview"] = {
            "status": change_preview.get("status"),
            "accepted_for_export": bool(change_preview.get("accepted_for_export", False)),
            "before": _numbers_only(change_preview.get("before", {})),
            "after": _numbers_only(change_preview.get("after", {})),
            "actions": [
                {
                    "action": action.get("action"),
                    "status": action.get("status"),
                    "evidence": _numbers_only(action.get("evidence", {})),
                }
                for action in change_preview.get("actions", [])
            ],
        }

    json.dumps(payload, allow_nan=False)
    return payload


def evidence_digest(report: dict) -> str:
    encoded = json.dumps(build_evidence_payload(report), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def explanation_cache_key(report: dict, context: str, model: str) -> str:
    if context not in ALLOWED_CONTEXTS:
        raise ExplanationError(f"Unsupported explanation context: {context!r}.")
    identity = {
        "input_fingerprint": report.get("dataset", {}).get("fingerprint"),
        "evidence_digest": evidence_digest(report),
        "context": context,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "schema_version": OUTPUT_SCHEMA_VERSION,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_prompt(report: dict, context: str) -> str:
    if context not in ALLOWED_CONTEXTS:
        raise ExplanationError(f"Unsupported explanation context: {context!r}.")
    evidence = json.dumps(build_evidence_payload(report), sort_keys=True, allow_nan=False)
    return f"{SYSTEM_RULES}\nEXPLANATION FOCUS: {context}\nAGGREGATE EVIDENCE:\n{evidence}"


def _fallback_content(report: dict, context: str) -> dict:
    evidence = build_evidence_payload(report)
    dataset = evidence["dataset"]
    quality = evidence["quality"]
    representation = evidence["representation"]
    screening = evidence["identifier_screening"]

    observations = [
        f"The validated table contains {dataset['row_count']:,} rows and {dataset['column_count']:,} columns.",
    ]
    if context in ("Audit overview", "Representation evidence"):
        observations.append(
            f"Representation evidence is {representation['status'].replace('_', ' ')} across "
            f"{len(representation['attributes'])} selected attribute(s), with "
            f"{len(representation['findings'])} review flag(s)."
        )
    if context in ("Audit overview", "Identifier-screening limitations"):
        observations.append(
            f"Identifier screening reported {len(screening['findings'])} signal(s) and does not "
            "certify de-identification."
        )
    if context == "Audit overview":
        observations.append(
            f"The table has {quality['missing_cells']:,} missing cell(s) and "
            f"{quality['duplicate_rows']:,} row(s) in duplicate sets."
        )
    if context == "Change-preview evidence":
        preview = evidence.get("change_preview")
        if preview:
            observations.append(
                f"The change preview is {preview['status'].replace('_', ' ')} with "
                f"{len(preview['actions'])} requested action(s)."
            )
        else:
            observations.append("No change preview is attached to the current audit report.")

    return {
        "headline": "Aggregate audit evidence is ready for human review",
        "observations": observations[:4],
        "unknowns": [
            "Model performance and clinical impact were not measured.",
            "Representation evidence does not establish model fairness.",
            "Identifier screening does not establish de-identification.",
        ],
        "next_questions": [
            "Does the selected demographic scope match the intended study population?",
            "What held-out evaluation protocol will be used before model claims are made?",
        ],
    }


def _parse_content(raw) -> dict:
    if isinstance(raw, dict):
        content = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        try:
            content = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExplanationError("The explanation provider did not return valid JSON.") from exc
    else:
        raise ExplanationError("The explanation provider returned an unsupported value.")

    required = {"headline", "observations", "unknowns", "next_questions"}
    if set(content) != required or not isinstance(content["headline"], str):
        raise ExplanationError("The explanation did not match the required output schema.")
    if len(content["headline"].strip()) < 4 or len(content["headline"]) > 180:
        raise ExplanationError("The explanation headline has an invalid length.")
    for field in ("observations", "unknowns", "next_questions"):
        values = content[field]
        if not isinstance(values, list) or not 1 <= len(values) <= 4:
            raise ExplanationError(f"{field} must contain one to four items.")
        if not all(isinstance(value, str) and 3 <= len(value.strip()) <= 300 for value in values):
            raise ExplanationError(f"{field} contains an invalid item.")

    combined = " ".join(
        [content["headline"]] + content["observations"] + content["unknowns"]
        + content["next_questions"]
    ).lower()
    if any(re.search(pattern, combined) for pattern in _UNSUPPORTED_PATTERNS):
        raise ExplanationError("The explanation included an unsupported certainty or action claim.")
    return content


def _run_with_timeout(provider: Callable, prompt: str, model: str, timeout_seconds: float):
    results = queue.Queue(maxsize=1)

    def invoke():
        try:
            results.put((True, provider(prompt, model, timeout_seconds)))
        except Exception as exc:  # provider failures become a visible fallback
            results.put((False, exc))

    worker = threading.Thread(target=invoke, daemon=True, name="medguard-explainer")
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        raise TimeoutError(f"The explanation provider exceeded {timeout_seconds:g} seconds.")
    succeeded, value = results.get_nowait()
    if not succeeded:
        raise value
    return value


def ollama_provider(prompt: str, model: str, timeout_seconds: float):
    """Call local Ollama lazily; no import or connection occurs before request."""

    import ollama

    client = ollama.Client(host="http://127.0.0.1:11434", timeout=timeout_seconds)
    response = client.generate(
        model=model,
        prompt=prompt,
        format="json",
        options={"temperature": 0.1, "num_predict": 450},
    )
    return response["response"]


def generate_explanation(
    report: dict,
    *,
    context: str,
    model: str = DEFAULT_MODEL,
    provider: Callable = ollama_provider,
    cache: Optional[MutableMapping] = None,
    timeout_seconds: float = 8.0,
) -> dict:
    """Generate or safely fall back after an explicit caller request."""

    if timeout_seconds <= 0:
        raise ExplanationError("timeout_seconds must be positive.")
    cache_key = explanation_cache_key(report, context, model)
    if cache is not None and cache_key in cache:
        cached = deepcopy(cache[cache_key])
        cached["cache_hit"] = True
        return cached

    status, reason = "generated", None
    try:
        raw = _run_with_timeout(provider, build_prompt(report, context), model, timeout_seconds)
        content = _parse_content(raw)
    except Exception as exc:
        status = "fallback"
        if isinstance(exc, TimeoutError):
            reason = "timeout"
        elif isinstance(exc, ExplanationError):
            reason = f"invalid_output: {exc}"
        else:
            reason = f"provider_unavailable: {type(exc).__name__}"
        content = _fallback_content(report, context)

    result = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "status": status,
        "requested": True,
        "cache_hit": False,
        "model": model,
        "context": context,
        "evidence_digest": evidence_digest(report),
        "content": content,
        "reason": reason,
        "limitations": [
            "This optional explanation is not audit evidence and must be reviewed by a person.",
            "Original records, cell values, group labels, column names, and file names are excluded from the prompt.",
            "Reviewed sources exist, but source-grounded RAG is disabled until retrieval is verified end to end.",
        ],
    }
    json.dumps(result, allow_nan=False)
    if status == "generated" and cache is not None:
        cache[cache_key] = deepcopy(result)
    return result
