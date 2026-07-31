# Zeinalii — MIB document challenge technical memo

## Approach

The submitted system is an offline, CPU-only document ensemble built around
three principles: visible evidence is authoritative, contradictory evidence
fails closed, and every decision must be reproducible from the submitted
container.

The primary processor renders every PDF page before extracting fields. PDFium,
Tesseract, and bounded RapidOCR recovery produce candidates with page role,
geometry, OCR confidence, visibility, and evidence type. Resolution then
applies document precedence, active-record scope, conflict, and strike-through
rules. The fields emitted in the final row come from this render-first path;
hidden PDF text cannot fill a field that is absent from the visible document.

A structured processor provides an independent adjudication view. It uses
raster OCR plus native spans only when those spans pass on-page geometry,
crop, size, contrast, and rendered-ink checks. A third Poppler/Tesseract path
provides a raster-only safety vote. Native spans cannot replace submitted
raster-resolved fields, and an auxiliary processor cannot independently
introduce an approval. The ensemble preserves an approval only when visible
identity or risk authority is present and no unresolved review-risk flag
remains. Missing, conflicting, or weak evidence generally resolves to
`NEEDS_REVIEW`.

Active-record linking prevents an archived or adjacent record from supplying
the current applicant's finding. White text, black render-mode-3 text, faint or
off-crop spans, and planted instructions are rejected as authority. In
pixel-identical perturbation tests, plain packets, white and black hidden-text
variants, a painted fake-system prompt, and a targeted hidden
`active_warrant` injection all produced the same final prediction hash.

Confidence is produced by a small source-aware correctness model followed by a
decision-specific monotone map. The map was fitted on the complete public
training replay. It is therefore deployment calibration, not evidence of
private-set performance.

## Evaluation and reproducibility

I separate the exact public/full-fit replay from estimates of generalization.
On all 1,000 labeled public packets, the frozen image scored
**139.5799/150**: 45.0122 extraction, 75.39 classification, and 19.1777
calibration. It answered every case, produced no technical fallback, and had
zero catastrophic false approvals.

The more conservative grouped evaluation refits learned action and confidence
heads inside each outer training partition. After applying the final
fail-closed approval gate, its deployment-matched center is **134.599/150**
with a case-bootstrap 95% interval of 132.943–136.224 and zero catastrophic
false approvals; the forward estimate is 134.060. Fixed extraction and policy
rules were still developed while public cases were visible, so I treat these
as stress estimates rather than claiming the whole processor was unseen.

Validation labels are unavailable. The model, thresholds, and runtime were
frozen before the one-shot validation run, and validation predictions were not
used for model selection or row-level repair. The validation result is
therefore reported only as a runtime, completeness, and format measurement:
the exact container answered all 5,000 PDFs with zero omissions and zero
fallbacks in 25,546.14 seconds, or **5.109228 seconds/PDF**. The resulting
JSONL passed the organizer validator with 5,000 valid records and zero missing
IDs.

Runtime optimization followed the same promotion boundary. A faster
single-OCR-mode candidate was rejected after the complete labeled replay found
three regressions and a 0.003333-point score loss. The promoted selective OCR
policy retained layout OCR on field-bearing pages, removed a redundant pass on
clear manual and biometric pages, and reproduced the safe 1,000-case output
byte for byte. Its exact 1,000-case runtime was 4.5992 seconds/PDF.

The final amd64/Linux image is 1.016 GB, below the 4 GiB limit. Its model files
total 50.74 MB; the largest is 21.23 MB. It runs with no network, GPU, API key,
LLM, VLM, cloud OCR, or runtime download. It passed the organizer-style
4-vCPU, 8-GiB, 512-PID, read-only-root contract with writes limited to `/tmp`
and the requested output mount. Dependency licenses and OCR model provenance
are included in the solution repository.

## Failure modes

The main remaining weakness is extraction under compound visual damage:
washout, rotation, occlusion, stains, fragmented grids, or several defects at
once. Applicant name, arrival date, home world, fee, and sponsor fields are
the most exposed in validation-like public slices. A stronger recognizer alone
does not solve this problem because recognizing a plausible value does not
establish page role, record ownership, or visible authority.

Adjudication is intentionally conservative. Unreadable risk evidence can leave
a true approval in `NEEDS_REVIEW`; relaxing that boundary introduced
catastrophic false approvals in grouped experiments. Full-data confidence
fitting also makes the public replay optimistic relative to unseen data.
Finally, unusual reversed page order can affect a decision even though benign
blank-page insertion is stable.

## With another week

I would build a bounded damage-recovery pass selected only by label-free page
quality signals. It would establish page role first, then apply field-specific
deskew, contrast normalization, line suppression, and independent OCR
agreement. Any selector or recalibrator would be trained inside
layout-family and temporal outer folds. Promotion would require nonnegative
deltas in every split, zero catastrophic false approvals, stable
active-record and prompt-injection perturbations, and compliance with the
six-second CPU budget.
