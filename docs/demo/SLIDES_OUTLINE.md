# MedGuard pitch deck outline

Target: seven slides, three minutes, large type, one idea per slide. Use screenshots from the synthetic guided demo only.

## 1. See the evidence before you train

**On screen:** MedGuard name, one-line promise, hero screenshot.

**Say:** Healthcare ML teams need a reviewable account of what a dataset contains before training. MedGuard turns a CSV into dataset-readiness evidence while preserving the source.

## 2. The failure mode

**On screen:** three short statements: hidden cohort gaps; identifier exposure; unsupported fairness or harm claims.

**Say:** A polished dashboard can still analyze the wrong copy, hide missing evidence, or turn representation into a clinical conclusion. MedGuard separates measurements, flags, limitations, and unknowns.

## 3. One validated evidence path

**On screen:** validation → identifier screening / quality / representation → audit record → reviewed copy.

**Say:** Raw CSV bytes are validated once. Every check uses the returned table. Fingerprints before and after analysis verify source preservation.

## 4. Honest representation and privacy

**On screen:** cohort table beside identifier-screening coverage.

**Say:** MedGuard keeps recorded category labels, reports nonmissing denominators, and compares with a reference only when the user supplies one. Identifier screening reports potential signals and never certifies de-identification.

## 5. Changes are reviewable

**On screen:** before/after preview with protected roles and acceptance state.

**Say:** Five allowlisted cleaning actions run on a separate copy. Protected demographics, identifiers, outcomes, and predictions are excluded from UI targets. No SMOTE or automatic cohort balancing is offered.

## 6. AI is optional and bounded

**On screen:** deterministic fallback result with “Unverified explanation” visible.

**Say:** The audit works without AI. An explicit explanation request sends only minimized aggregate evidence to local Ollama. Timeout, malformed output, or unsafe claims produce a visible deterministic fallback. W04 sources appear as reviewed context cards, while AI retrieval remains disabled until it is verified end to end.

## 7. Evidence and next step

**On screen:** tests, exports, limitations, repository QR/link.

**Say:** The release includes deterministic acceptance coverage and portable JSON/CSV evidence. It is a research workflow prototype, not clinical or privacy certification. Next, define a model-specific evaluation protocol and complete governance review with intended users.

## Appendix slides

- Result contract and status precedence.
- Input limits and identifier-screening coverage.
- Test matrix and release-validation record.
- Pre-existing baseline versus October 24 hackathon work.
- Open limitations: embedding retrieval, deployment, and intended-user validation.
