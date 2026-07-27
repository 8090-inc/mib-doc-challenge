# Technical memo

## Result

The answer-key-free candidate scores **135.012491 / 150** on the complete
1,000-packet public train set using the organizer's exact Docker runner and
evaluator.

| Component | Score |
| --- | ---: |
| Field extraction | 45.050000 / 50 |
| Adjudication | 72.430000 / 80 |
| Calibration | 17.532491 / 20 |
| Mean Brier error | 0.061688 |
| Catastrophic false approvals | 0 |

It produces one schema-valid prediction per manifest case, with no duplicates
or omissions. The image is 0.19 GiB and runs with network disabled, four CPU
cores, 8 GiB RAM, a read-only root filesystem, and a non-root user. The exact
1,000-packet container run completed in 1,479 seconds.

This score is **3.01 points above** the reported 132 benchmark. It is evidence
that the public-train implementation beats that number, not a guarantee about
the private test ranking.

Later public PRs claim roughly 138 on train, but their disclosed/default high
paths consume embedded white `SYSTEM`/answer-table content and add cells
optimized on the public labels. This submission deliberately excludes that
channel because the challenge warns that hidden instructions may be wrong and
the final ranking includes private data plus manual anti-gaming review.

## System

The base is a render-first document pipeline. `pypdfium2` rasterizes pages;
RapidOCR performs primary OCR; bounded Tesseract passes recover difficult
regions. Candidates retain document type, geometry, OCR confidence, and visual
cues. Cross-page linking and precedence rules resolve fields before a
conservative adjudication engine and calibrated output layer.

The finalizer is intentionally separate from the OCR core. It reads only
visible PDF layout and applies, in order:

1. identity-free fee/name/visa/sponsor/date/purpose repairs;
2. visible-layout clean-packet consensus;
3. narrowly gated blue-slash and red-watermark denial signals;
4. explicit finding and document-damage decisions;
5. approval safety demotions and denial softening;
6. a second explicit-finding pass and a `TRANSIT-7` hard gate;
7. identity-free confidence blending and a two-parameter Platt transform.

Keeping this layer separate made the full 1,000-case run stable. A monolithic
variant with additional OCR heads repeatedly exited with signal 139 during long
runs, while the stable core plus layout finalizer completed the same workload.
The `pypdfium2` fallback also preserves form-feed page boundaries; without that
fix, page-signature safety gates were silently disabled in the submission image.

## Score audit and transfer evidence

Relative to the frozen legal base, the finalizer improved total score from
129.8470 to 135.0125:

- 58 `NEEDS_REVIEW → APPROVED` changes; all 58 match public truth;
- 3 narrowly gated `NEEDS_REVIEW → DENIED` changes; all 3 match public truth;
- 12 applicant-name repairs, all 12 improvements and no regressions;
- 3 visa, 3 sponsor, 2 arrival, and 3 fee repairs, all improvements;
- 4 risk-field changes, 2 improvements and no measured regression;
- zero catastrophic false approvals after all changes.

Each of five deterministic reporting partitions improved versus the same base:
`+6.48`, `+5.19`, `+4.76`, `+4.62`, and `+3.34`. These partitions are useful
localization checks, but they are not a substitute for the organizer's private
test because the frozen rules were selected using public training data.

No runtime source contains validation case IDs, filenames, hashes, or label
tables. Embedded generator instructions are removed before visible-layout
logic. The shipped tree has no answer-key module or enable flag, and the tests
enforce that invariant.

The hollow-slash head fires on 1/1,000 public packets and 6/5,000 validation
packets. The guarded red-watermark head fires on 2/1,000 public packets and
20/5,000 validation packets. Both are deny-only; the latter is suppressed when
ordinary OCR exposes explicit `ILLEGIBLE`, `WASHED OUT`, or `REDACTED` review
evidence. The final confidence transform is supported by five-fold OOF
calibration rather than a direct full-fit score search.

## Failure modes

- Layout promotion depends on recurring visible form structure. A private
  distribution with different templates may reduce the 58-case gain.
- OCR can still miss faint, rotated, occluded, or handwritten evidence.
- Some packets do not visibly contain decision-critical facts. Those remain
  review rather than being guessed.
- Safety tables use identity-free visa, purpose, fee, and page-order features
  learned from public data. They can overfit even though they never use case
  identity.
- Confidence calibration may drift if the private class mix differs.
- Watermark OCR may miss new colors, fonts, or severe scan degradation.

The fail-closed behavior is deliberate: uncertain packets go to
`NEEDS_REVIEW`, visible disqualifiers dominate, and no hidden instruction can
supply a field or decision.

## With another week

I would fit every safety and calibration table in a truly nested grouped
cross-validation loop, quantify unlabeled validation feature shift, replace
the remaining OCR watermark regex with a small crop-provenance classifier, and
profile the few remaining OCR-heavy cases. Any new approval path would still
require zero catastrophic false approvals in every development partition.
