# Evidence Ladder — Technical Memo

## Approach

The pipeline is a cost-gated OCR escalation over a field-manual rule engine. It
reads a directory of PDF packets, extracts nine fields, adjudicates against the
public policy, and emits a calibrated confidence. Most of the work was contributed by Sol and Opus via loops. Probably the thing that I messed up on over and over again is maintaining good data hygiene. It's really easy for the solution to overfit and get like 149/150 on like a 100 example-subset. Sometimes the overfitting is more subtle. Had a lot of fun designing the proper autoresearch loops. I only made directional contributions. This Memo was written with AI assistance.

**Extraction.** Each packet climbs an escalating chain of text streams, gated on
unresolved fields so expensive passes only hit the hard remainder: native text
layer → page OCR → Sauvola threshold fallback → `tessdata_best` → PP-OCRv6
neural pass → embedded-raster pass → oriented pass for rotated forms. A
noisy-channel stage then repairs closed-vocabulary fields against a character-
error prior, with real-word overrides requiring cross-source agreement. Visual
detectors recover stamped risk marks (biohazard seal, planetary embargo) that
OCR alone routinely misses.

**Adjudication.** Rules implement the field manual (visa class, sponsor
revocation, fee status, disqualifying risk flags, trusted-evidence precedence).
A learned arbiter then re-decides from the evidence in `replace` mode: it is
denied the features that encode the runtime's own verdict, so it forms an
independent opinion rather than copying one. Trusted adjudicator findings and
hard policy denials keep field-manual precedence over the model. Confidence is
calibrated on out-of-fold predictions, never in-sample ones.

**Provenance.** Every shipped artifact is fitted on an 800-packet DEV split,
selected by inner eight-fold out-of-fold evaluation, with a frozen HOLD200 used
only for aggregate generalization checks. No case IDs, filenames, or split
membership enter features.

## Held-out result

On untouched HOLD200 (host): **124.05 / 150** (extraction 45.53, classification
61.80, calibration 16.72, false approvals 2). This may be slightly inaccurate on a small fraction of cases due to
Tesseract/poppler build differences.

It meets constraints: runtime in the scoring contract is **5.46 s/PDF** (9% margin under the 6 s
budget), ~2.1 GiB peak memory of 8 GiB.

## Failure modes

Residual loss is mostly *conservatism*, not reckless misclassification, which is reasonable considering rubric. Before
the arbiter, most classification loss was true approvals sitting in
`NEEDS_REVIEW`. Promoting the observable "reviewed + risk none + fee settled"
cohort is not safe: that set mixes true approvals with true reviews and denials,
and every confidence threshold we tried destroyed more review utility than it
rescued.

The structural ceiling is extraction of evidence the packet does not contain.
Across seven OCR streams, only a handful of currently-wrong field values had
the truth available from *any* engine. `risk_flags` dominates residual
classification loss, and most of that loss is physically absent biometric /
risk evidence rather than OCR error. About 5% of adjudications are not a
function of the nine extracted fields even with trusted values — policy
exceptions and incomplete packets that correctly need review.

Secondary modes: sponsor-policy edge cases, fee `waived`/`unknown` ambiguity
without a visible waiver, and oriented/degraded scans that still burn budget
before yielding a usable read.

## What another week would buy

Better classification. Spent too much time exploring neural/ensembling approaches when more crude and less bitter pilled methods seem to be better. I think this does well with extraction but taking a sneak peak at the other PRs we get mogged in classification. 