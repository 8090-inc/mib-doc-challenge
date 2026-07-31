# Technical memo: MIB intake pipeline

## System and canonical result

I built an offline, CPU-only document pipeline that reads each case two ways, quarantines
untrusted PDF text, repairs bounded OCR errors, fuses evidence by the field manual's
precedence rules, and applies a deterministic policy. It calls no hosted inference or OCR
service, and runtime networking is disabled.

On the final 1,000-case public training run in Docker under the challenge resource contract,
the system scored **106.80/150**: 56.41/80 classification, 36.91/50 extraction, and
13.47/20 calibration, with one false approval and zero missing cases. Docker is the quoted result
because small aggregate differences between Tesseract builds can mask record-level OCR
changes. The 0.11 GiB image contains no weights trained on challenge data or bundled
separately; it has only the distribution-packaged Tesseract language and orientation data.
Including bounded rescue, it processed a PDF in 1.21 seconds on average at 4 vCPU against
the 6-second budget.

The complete flow and policy order are in the public
[architecture document](https://github.com/santho090/mib-doc-challenge/blob/main/ARCHITECTURE.md).

## Design choices

### Treat the text layer as evidence, not truth

One packet contains a fake answer key in its text layer while the rendered page shows
different evidence. Every page is rendered and OCR'd even when native text exists. The text
layer is accepted only when the render does not reveal substantial content it lacks and no
injection pattern is present. Reversing that comparison rejects clean sparse forms because
OCR naturally under-reads them.

### Require readable risk evidence for approval

"No flags seen" is not the same as "no flags exist." A missing, blank, or destroyed
`Observed flags` line cannot support approval, even when OCR splits the destruction marker.
The page is retried when possible. If the evidence stays unreadable, the case routes to
`NEEDS_REVIEW` unless an earlier denial rule applies. Unreadable hard flags had produced
false approvals before this guard was added.

### Use a robust batch epoch

Staleness needs a notion of "now," but the packets do not expose a reliable receipt date.
Using the maximum arrival date let one year misread as 2028 shift the cutoff and create 13
wrong denials. The shipped version uses the 97th percentile, which resists a single outlier.
A 6/8 year repair is allowed only when it moves an impossible future date into a bounded
window behind that inferred epoch.

### Calibrate confidence from measured outcomes

The deployed lookup contains Laplace-smoothed training accuracy by `(rule_path, evidence
tier)`. Five-fold out-of-fold Brier estimates generalization; the final table is fitted on
all public training cases. Document evidence selects the path and tier but cannot provide a
confidence value directly.

## Measured gains and remaining loss

The host development score progressed from 94.45 to 100.51, then 105.67 and 107.22.
Replacing seeded confidence with measured calibration produced the largest gain. Requiring
readable flag evidence, moving unknown-fee review behind denial rules, and adding a fee
fallback reduced false approvals from five to one. Bounded rescue and narrow policy fixes
then lifted extraction and total score.

Rescue re-reads at most three pages at 350 dpi using three preprocessing variants. Fee pages
take priority when fee status is unknown; otherwise the lowest-quality pages run first. The
merge is fill-only, so a rescued value cannot overwrite the fast pass.

The remaining loss is concentrated in `fee_unknown` and `incomplete_evidence`. I tried
rerouting subsets selected from observable document features to `APPROVED`; every tested
subset still contained truth-`DENIED` cases. I left them as `NEEDS_REVIEW`.

## Failure modes and provenance

- Destroyed or absent evidence can remain unknown. Fused glyphs, explicit destruction
  markers, and missing pages route toward review rather than approval. Region-level OCR may
  recover more than the current whole-page ladder.
- Decoy sponsor IDs require source trust. A revoked ID found only on an untyped page is
  contradictory evidence. This sponsor condition routes to review unless an earlier denial
  rule applies.
- Output is finalized at batch end. Extraction is buffered so the batch epoch can be
  computed before policy runs. A hard process kill during extraction therefore leaves no
  partial scoreable file. The measured runtime and per-case watchdogs provide large budget
  margin, but incremental checkpointing is the next reliability fix.
- Packets are capped at 12 pages. This bounds adversarial runtime, but decision evidence
  placed later in a private layout would be ignored.
- Training-derived registries may not transfer. Unknown field vocabulary escapes snapping,
  but sponsor and embargo registries remain a risk if the private generator changes values.

The field manual says examples may reveal additional policy facts. I disclose three
training-derived resources: three revoked sponsor IDs, two embargoed home worlds, and a
144-first-name/144-last-name OCR repair lexicon. They apply uniformly. `case_id` filters
pages for another applicant in a mixed packet, but no literal ID selects an answer or rule.

## What I would do with another week

I would add a small trained stamp and annotation detector, region-level re-OCR around
decision-critical labels, and a route-by-route flag precision/recall audit. I would also
extend the rendered unseen-layout fuzz suite and run the full 1,000-case certification on
amd64. The amd64 image builds today, and an eight-case smoke run matched arm64 exactly.
