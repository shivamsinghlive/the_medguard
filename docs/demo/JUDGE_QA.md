# Judge Q&A

## What makes this different from a dashboard?

The visible workspace is backed by versioned, JSON-safe result contracts and deterministic services. Validation, screening, quality evidence, and representation analysis feed the same exportable audit record. The UI does not invent conclusions that are absent from those services.

## Is a 73/27 demographic split biased?

The split is an observed representation measurement. Whether it is appropriate depends on the intended population and study design. MedGuard reports counts, denominators, missingness, and an optional user-supplied comparison without applying an undocumented fairness threshold.

## Does MedGuard make a dataset HIPAA compliant?

No. It heuristically screens column names and values for potential identifiers and reports its coverage and limitations. It always sets `certifies_deidentification` to false. Formal Safe Harbor or Expert Determination work is outside the prototype.

## Does it send patient records to an LLM?

No AI or network call exists in the active audit path. The guided demo and deterministic tests run offline. Any future explanation feature must be explicitly requested and must keep original records out of prompts.

## Why are automatic fixes disabled?

Automatic balancing can change the meaning of a healthcare dataset and cannot establish improved model performance without held-out evaluation. The planned change service returns a separate preview, blocks protected roles by default, and leaves acceptance to the researcher.

## How do you know analysis did not mutate the data?

The audit runner fingerprints the validated DataFrame before and after its services run and raises an error if the fingerprint changes. Service and integration tests also compare inputs before and after analysis.

## What happens with malformed or very large files?

Validation rejects malformed CSV, non-UTF-8 or binary input, duplicate headers, header-only files, and files beyond the configured size, row, or column limits. Rejected input does not reach analysis.

## What is already real versus planned?

Working now: structural validation, potential-identifier screening, descriptive quality evidence, representation evidence, source-preservation checks, and JSON/CSV export. Planned: a narrow safe-change preview, optional bounded explanations, and final independent release validation.

## What should happen before clinical use?

The prototype would need a defined use context, threat model, privacy and security review, validated data governance, model-specific evaluation, clinical and regulatory review, monitoring, and evidence from intended users. This hackathon build is a dataset-readiness aid, not a clinical device.
