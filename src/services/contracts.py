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


# --- Input validation (W02) -------------------------------------------------
# validate_input(data: bytes, ...) -> (ValidationResult, DataFrame | None).
# 'accepted' means the CSV parsed with a consistent structure inside the size
# limits; it says nothing about data quality or privacy. On 'rejected' the
# frame is None and errors explain why. Messages never quote cell values.
VALIDATION_SCOPE = 'input_validation'
ACCEPTED = 'accepted'
REJECTED = 'rejected'


class ValidationIssue(TypedDict):
    code: str
    message: str
    details: Dict[str, object]  # counts, line numbers, column names; no cell values


class ValidationResult(TypedDict):
    schema_version: str
    scope: str
    status: Literal['accepted', 'rejected']
    byte_count: int
    row_count: Optional[int]  # None when the file was not parsed
    column_count: Optional[int]
    limits: Dict[str, int]  # max_bytes, max_rows, max_columns
    errors: List[ValidationIssue]  # any error means 'rejected'
    warnings: List[ValidationIssue]  # accepted, but worth showing
    limitations: List[str]


# --- Potential identifier screening (W02) -----------------------------------
# screen_identifiers(df, ...) -> ScreeningResult. Heuristic screening only:
# 'no_patterns_found' means none of the listed checks matched in the scanned
# coverage, never that the data is de-identified. Findings report counts and
# column names, never matched values. certifies_deidentification is always
# False.
SCREENING_SCOPE = 'identifier_screening'
NO_PATTERNS_FOUND = 'no_patterns_found'
SCREENING_STATUSES = (REVIEW_NEEDED, INSUFFICIENT_EVIDENCE, NO_PATTERNS_FOUND)


class ScreeningCoverage(TypedDict):
    row_count: int
    rows_scanned: int  # leading rows whose values were checked, in every column
    column_count: int  # every column gets a name check and a value check
    complete: bool  # True only if every row was value-checked
    checks: List[str]  # finding codes this screen can produce


class ScreeningResult(TypedDict):
    schema_version: str
    scope: str
    status: Literal['review_needed', 'insufficient_evidence', 'no_patterns_found']
    certifies_deidentification: bool  # always False
    coverage: ScreeningCoverage
    findings: List[Finding]  # same shape as representation findings
    limitations: List[str]


def overall_status(statuses: List[str]) -> str:
    """Combine attribute statuses; no attributes means insufficient evidence."""
    for status in STATUSES:
        if status in statuses:
            return status
    return INSUFFICIENT_EVIDENCE


# --- Change preview (W03) ---------------------------------------------------
# preview_changes(df, actions, *, column_roles) -> (PreviewResult, DataFrame | None).
# Only allowlisted cleaning actions run, in order, on a separate copy; the
# source frame is never modified. Any blocked action blocks the whole preview
# (output None) so a partial change set is never presented. Actions naming a
# column with a protected role are blocked unless that action sets
# allow_protected=True. The output keeps source index labels for traceability.
PREVIEW_SCOPE = 'change_preview'
PREVIEW_READY = 'preview_ready'
PREVIEW_BLOCKED = 'blocked'
APPLIED = 'applied'
BLOCKED = 'blocked'
NOT_RUN = 'not_run'  # an earlier action was blocked

PROTECTED_ROLES = ('outcome', 'prediction', 'identifier', 'demographic')
COLUMN_ROLES = PROTECTED_ROLES + ('feature',)
ALLOWED_ACTIONS = ('drop_duplicate_rows', 'drop_rows_with_missing', 'fill_missing',
                   'strip_whitespace', 'drop_column')


class ActionResult(TypedDict):
    index: int  # position in the requested action list
    action: str
    columns: List[str]
    status: Literal['applied', 'blocked', 'not_run']
    reason: Optional[str]  # why it was blocked; None otherwise
    evidence: Dict[str, object]  # rows_removed, cells_changed, fill_value, ...
    warnings: List[str]


class GroupCounts(TypedDict):
    observed_count: int
    missing_count: int
    counts: Dict[str, int]  # recorded label -> rows


class PreviewResult(TypedDict):
    schema_version: str
    scope: str
    status: Literal['preview_ready', 'blocked']
    actions: List[ActionResult]
    before: Dict[str, object]  # row_count, column_count, demographic_counts
    after: Optional[Dict[str, object]]  # None when blocked
    schema: Optional[Dict[str, object]]  # columns_removed, dtype_changes, preserved
    source_fingerprint: str
    output_fingerprint: Optional[str]
    limitations: List[str]


class ChangePreviewError(ValueError):
    """Invalid preview request (action list or column roles), not a blocked action."""
