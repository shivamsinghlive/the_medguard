"""Shared result contract (v1) between analysis services and the UI.

These are in-process Python types, not an HTTP API. Results are plain dicts
that are JSON-safe: unavailable numbers are None, never NaN or Infinity.
Change fields only after the shared contract document is updated.
"""
from typing import Dict, List, Literal, Optional, TypedDict

SCHEMA_VERSION = '1.0'
REPRESENTATION_SCOPE = 'dataset_representation'

# There is deliberately no clearance status: representation evidence can show
# what needs review, never that a dataset is fair.
REVIEW_NEEDED = 'review_needed'
INSUFFICIENT_EVIDENCE = 'insufficient_evidence'
DESCRIPTIVE_ONLY = 'descriptive_only'
STATUSES = (REVIEW_NEEDED, INSUFFICIENT_EVIDENCE, DESCRIPTIVE_ONLY)  # precedence order

# Issue-triage labels, never clinical-risk estimates.
PRIORITIES = ('high', 'medium', 'low')

Status = Literal['review_needed', 'descriptive_only', 'insufficient_evidence']
Priority = Literal['high', 'medium', 'low']


class GroupResult(TypedDict):
    label: str
    count: int
    proportion: Optional[float]  # of non-missing values; None if none observed
    reference_proportion: Optional[float]  # None without a supplied reference
    difference_pp: Optional[float]  # percentage points, observed - reference


class AttributeResult(TypedDict):
    column: str
    status: Status
    observed_count: int  # non-missing values; the proportion denominator
    missing_count: int
    groups: List[GroupResult]


class Finding(TypedDict):
    id: str  # '<column>:<code>', unique within a result
    code: str
    column: str
    priority: Priority
    title: str
    evidence: Dict[str, object]
    suggested_action: str


class RepresentationResult(TypedDict):
    schema_version: str
    scope: str
    status: Status
    row_count: int
    attributes: List[AttributeResult]
    findings: List[Finding]
    limitations: List[str]


class RepresentationInputError(ValueError):
    """Invalid column selection or reference population."""


def overall_status(statuses: List[str]) -> str:
    """Combine attribute statuses; no attributes means insufficient evidence."""
    for status in STATUSES:
        if status in statuses:
            return status
    return INSUFFICIENT_EVIDENCE
