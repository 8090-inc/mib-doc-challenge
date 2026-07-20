# Naive Offline Baseline

## Approach

This entry is an intentionally naive baseline whose purpose is to verify the full
submission path: building an offline Docker image, discovering input PDFs,
writing schema-valid JSONL, validating every expected case ID, and running the
published deterministic evaluator. It uses the challenge repository's
MIT-licensed `examples/offline_baseline` implementation unchanged.

The program lists every `.pdf` file in the input directory and uses each file's
stem as `case_id`. It does not open, render, OCR, or otherwise inspect the
document. Every case receives the same conservative prediction:

- unknown values for the applicant, species, home world, visa class, declared
  purpose, and fee status;
- `SPN-0000` for the sponsor and `1900-01-01` for the arrival date;
- `none` for risk flags;
- `NEEDS_REVIEW` for adjudication; and
- confidence `0.01`.

Choosing `NEEDS_REVIEW` avoids confidently approving or denying a packet that
the model has not read. The low confidence is meant to describe that lack of
evidence honestly, rather than to optimize the leaderboard score.

## Reproducibility and contract checks

The solution is packaged in a small CPU-only Docker image based on
`python:3.12-slim`. It has no third-party runtime dependencies and makes no
network calls. The image accepts the required two arguments:

```text
<image> /input /output/predictions.jsonl
```

I exercised it with the repository's `scripts/run_docker_submission.py` runner,
including disabled networking, a read-only filesystem, fixed CPU and memory
limits, and the completeness validator. The built image was approximately
0.13 GiB. It produced all 1,000 training records and all 5,000 validation
records, with no missing or duplicate case IDs.

On the public training labels, `scripts/evaluate.py` reported:

| Component | Score |
| --- | ---: |
| Field extraction | 4.95 / 50 |
| Classification | 36.80 / 80 |
| Calibration | 9.02 / 20 |
| Missing-case penalty | -0.00 / 10 |
| **Deterministic total** | **50.77 / 150** |

There were no extra cases, invalid output records, or catastrophic false
approvals. These results are a plumbing check, not evidence of useful document
understanding.

## Failure modes

This baseline ignores all evidence in the packet, so it cannot extract real
field values or distinguish approval, denial, and review cases. Its constant
placeholder date and sponsor ID may occasionally match by chance but are not
grounded in the documents. Likewise, `risk_flags: none` is unsafe as a factual
claim: the choice is present only to satisfy the output schema. Because the
program relies on the PDF filename for `case_id`, incorrectly named files would
also lead to incorrect identifiers.

The constant confidence is not calibrated by class or case difficulty. Although
the conservative adjudication prevents false approvals in the public training
set, it sends every case to a human and therefore provides no operational
automation benefit.

## What I would improve with another week

I would first add deterministic PDF text extraction, normalization, and explicit
field parsers for dates, sponsor IDs, visa classes, and fee status. I would then
add OCR fallbacks for image-only pages, page rotation and deskew handling, and
cross-page evidence reconciliation. Adjudication would be implemented as
auditable rules derived from `FIELD_MANUAL.md`, with `NEEDS_REVIEW` reserved for
missing or contradictory evidence.

Finally, I would evaluate confidence calibration on held-out training data,
build regression tests for malformed and adversarial PDFs, and retain the same
offline Docker harness so that improvements remain reproducible under the
published scoring constraints.
