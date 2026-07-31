# Technical Memo

## Architecture

The solution is a deterministic offline document pipeline with five stages:

1. PDF ingestion and page rendering. Each packet is opened page by page and
   rasterized with Poppler so the rendered image becomes the primary evidence
   boundary.
2. OCR and text acquisition. Rendered pages are passed through local Tesseract.
   A filtered PDF text layer is used only as a bounded fallback when OCR has
   already confirmed the visible document type.
3. Document-type parsers. Specialized extractors recognize intake forms,
   registry extracts, sponsor letters, biometric slips, fee receipts, and
   manual adjudicator notes, then normalize their fields into a shared case
   representation.
4. Evidence resolution and policy. Parsed facts are merged in field-manual
   priority order, with manual findings and corrections overriding weaker
   sources. A deterministic rules engine then decides `APPROVED`, `DENIED`, or
   `NEEDS_REVIEW`.
5. Confidence and output. The system assigns confidence from evidence quality,
   completeness, and agreement, then emits one schema-valid JSON record per
   case.

This architecture is designed around prompt-injection resistance. Hidden text,
off-page objects, and machine-readable instructions do not become primary
evidence because the rendered page is authoritative. The text layer can correct
a closely matching OCR value or fill a missing field only when OCR independently
confirms the corresponding visible document type, and it never supplies an
adjudication on its own.

At the implementation level, `solution.py` organizes the pipeline as parallel
case processing over four CPU workers. Each worker renders pages, extracts OCR,
collects typed evidence, applies policy, and writes normalized output. The
runtime requires no network, uses CPU only, and writes temporary raster files
only beneath `/tmp`, which keeps it compatible with the evaluator's read-only
container configuration.

## Approach

Within that architecture, the core strategy is evidence-first adjudication.
Parsing recognizes the main public packet types, then resolves evidence in
field-manual order. Explicit manual corrections and adjudicator findings take
precedence, followed by intake, biometric, sponsor, registry, and fee evidence.
The deterministic policy engine handles disqualifying and review-only flags,
revoked sponsors, visa and fee rules, missing evidence, and stale arrivals.
Confidence is reduced when required fields are missing, OCR fails to produce a
recognized value, or the packet contains only weak support for a decision.

## Failure Modes

Very severe blur or page damage can still defeat OCR. Layouts that use labels not
represented in the public data may leave fields unknown. The public field manual
is intentionally incomplete, so unseen private policy exceptions can differ from
the deterministic fallback rules. Manual findings remain the strongest signal
when present.

## Next Improvements

With another week, I would add orientation detection, selective high-resolution
re-OCR for low-confidence regions, image preprocessing for damaged scans, and a
small layout classifier trained only from public packets. I would also calibrate
confidence on held-out public cases rather than using evidence-tier estimates.

## Verified Public Result

The final image was run against all 1,000 training PDFs with the published
offline, read-only, four-CPU, 8 GiB limits. It produced all expected records,
passed the public validator, and scored **107.79 / 150**:

- field extraction: 37.89 / 50
- classification: 58.62 / 80
- calibration: 11.28 / 20
- catastrophic false approvals: 23

## Key Files

Reviewers can orient quickly with these files in the public solution
repository:

- `Dockerfile`: offline submission image definition
- `run.sh`: evaluator-compatible entrypoint
- `solution.py`: end-to-end OCR, parsing, policy, and output pipeline
- `tests/test_solution.py`: regression coverage for core extraction logic
- `reports/training-evaluation.json`: published local training-set score
- `SUBMISSION.md`: repository link and reviewer file guide
