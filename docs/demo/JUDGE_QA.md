# Judge Q&A

## What makes this different from a dashboard?

The visible workspace is backed by versioned, JSON-safe result contracts and deterministic services. Validation, screening, quality evidence, and representation analysis feed the same exportable audit record. The UI does not invent conclusions that are absent from those services.

## Is a 73/27 demographic split biased?

The split is an observed representation measurement. Whether it is appropriate depends on the intended population and study design. MedGuard reports counts, denominators, missingness, and an optional user-supplied comparison without applying an undocumented fairness threshold.

## Does MedGuard make a dataset HIPAA compliant?

No. It heuristically screens column names and values for potential identifiers and reports its coverage and limitations. It always sets `certifies_deidentification` to false. Formal Safe Harbor or Expert Determination work is outside the prototype.

## Does it send patient records to an LLM?

No AI call exists in the deterministic audit path. The optional explanation runs only after an explicit button click and targets local Ollama. Its prompt excludes records, cell values, group labels, column names, and file names. If the model is absent, slow, malformed, or fails claim checks, MedGuard shows a deterministic fallback.

## Are the explanations grounded in medical sources?

Not in the current branch. The W04 reviewed source inventory is not present on `main`, so source-grounded RAG is disabled. The explainer is limited to aggregate audit evidence and is visibly labeled unverified.

## Why are automatic fixes disabled?

Automatic balancing can change the meaning of a healthcare dataset and cannot establish improved model performance without held-out evaluation. The change workflow returns a separate preview, excludes protected roles from UI targets, and requires the researcher to accept the result before exporting the reviewed copy.

## How do you know analysis did not mutate the data?

The audit runner fingerprints the validated DataFrame before and after its services run and raises an error if the fingerprint changes. Service and integration tests also compare inputs before and after analysis.

## What happens with malformed or very large files?

Validation rejects malformed CSV, non-UTF-8 or binary input, duplicate headers, header-only files, and files beyond the configured size, row, or column limits. Rejected input does not reach analysis.

## What is already real versus planned?

Working now: structural validation, potential-identifier screening, descriptive quality evidence, representation evidence, source-preservation checks, reviewable change previews, explicit acceptance, optional bounded local explanations, JSON/CSV export, and an independent release-validation record. Planned: reviewed source-grounded explanations and model-specific evaluation.

## What should happen before clinical use?

The prototype would need a defined use context, threat model, privacy and security review, validated data governance, model-specific evaluation, clinical and regulatory review, monitoring, and evidence from intended users. This hackathon build is a dataset-readiness aid, not a clinical device.
