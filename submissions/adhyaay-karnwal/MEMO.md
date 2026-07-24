# MIB Doc Challenge — Technical Memo

## Summary

This submission is an offline, CPU-only visible-evidence pipeline. It renders
every PDF, performs page-aware OCR, resolves conflicting evidence by source
authority, applies the field manual with a strict approval bar, and emits
calibrated JSONL.

Release measurements:

- Public train: **124.05 / 150**, zero catastrophic false approvals; nested
  five-fold OOF evidence: **123.95 / 150**.
- Runtime: **1.775 seconds/PDF** on 4 CPU / 8 GB under the exact
  offline/read-only Docker contract.
- Validation: **5,000 / 5,000** records with zero omissions; the official
  manifest validator reported 5,000 valid records and zero missing IDs.

## Method

PDFium renders pages and Tesseract performs the primary OCR pass. RapidOCR is a
bounded second reader used only when primary output fields remain unresolved.
Candidate evidence records page type, case scope, legibility, confidence,
supersession, and visual cues; the resolver rejects cross-case and contested
evidence before policy is evaluated.

Approvals require visible support. In particular, a schema/default
`risk_flags=none` is never treated as observed clearance. The narrow
layout-consensus recovery requires a legible non-superseded biometric
`risk_flags=none` candidate, visible paid-fee proof, and unique
registry/applicant agreement. Missing outcome-determinative evidence remains
`NEEDS_REVIEW`.

## Prompt-injection defense

The primary renderer does not read selectable PDF text. A separate native
layout helper exposes a text object only after comparing its fill alpha, render
mode, bounds, color/background contrast, ink fraction, and local raster range
against rendered pixels. Known fake system, answer-key, and barcode
instruction lines are then removed as defense in depth.

An adversarial test inserted a novel transparent
`Observed flags: biohazard_red` payload into a public PDF. The page rasters
remained byte-identical. A blocklist-only build changed its decision; the
release build produced byte-identical predictions for the original and
mutated PDFs.

## Research and integrity

Development used frozen stratified folds and the official evaluator. The
append-only ledger records regressions, crashes, runtime failures, and
quarantined high scores. Rejected methods included broad full-page OCR,
visible-pixel ridge/LDA heads, and two alternative confidence calibrators.

A final source audit deliberately reset the apparent score. We removed:

- every review-to-approval rule based on missing fields, arrival age,
  applicant counts, or packet topology;
- an approval path whose risk evidence was explicitly unknown;
- benchmark-frequency fallbacks for unresolved extraction fields;
- the answer-key transcription module and all imports/calls;
- raw text-layer ingestion in the primary renderer.

The resulting public score is lower than several quarantined precursors. This
is intentional: the private/admin evaluator excludes genuinely unrecoverable
fields from a case's extraction maximum, while the public CSV lacks that
metadata. Guessing destroyed values would inflate local extraction but weaken
the audited private system.

## Limitations

Destroyed/image-only fields, risk panels, and stamps remain the principal
errors. When visible evidence cannot distinguish approval from denial, the
pipeline returns review rather than guessing. The image contains no LLM/VLM,
cloud OCR, API key, case-ID lookup, validation answer artifact, or network
dependency.

## With another week

I would expand document-level OCR consensus only for fields that remain
unresolved after the fast pass, add synthetic visible corruption tests for
stamps and risk panels, and train/evaluate any new confidence features under
the same nested folds. I would also profile validation-like page-complexity
strata to reduce the gap between the 1.511 seconds/PDF training measurement and
the 1.775 seconds/PDF full-validation measurement without weakening the
visible-evidence boundary.
