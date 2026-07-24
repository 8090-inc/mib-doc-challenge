# Technical Memo — handemanai (preliminary)

> **Status: placeholder.** These predictions come from an earlier build of the
> pipeline; the final predictions, the full 1–2 page technical memo, and the
> public solution repository will be updated on this pull request before the
> submission deadline.

## Approach (summary)

An offline, Dockerized document-intake pipeline: PDF object forensics with
hidden-text distrust, OCR with quality-gated escalation, field extraction into
per-field evidence pools with closed-vocabulary normalization, a deterministic
adjudication policy engine reconstructed from the field manual and labeled
examples, and calibrated per-case confidence. Decisions fail closed: when
outcome-determinative evidence is unrecoverable from the visible document, the
system prefers `NEEDS_REVIEW` over guessing, and approval requires trusted
visible evidence.

- No network access at runtime; CPU-only; no LLM/VLM in the submitted runtime.
- Hidden text, off-crop content, and planted "answer keys" are treated as
  untrusted and never used as field evidence.
- Confidence is an estimate of adjudication correctness, fit out-of-fold on
  training data.

## Failure modes and planned work

Documented in full in the final memo, including hedge-mass analysis on
evidence-absent packets and perturbation-robustness measurements.
