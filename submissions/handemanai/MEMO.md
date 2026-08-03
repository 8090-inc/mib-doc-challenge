# MIB Doc Challenge — Technical Memo

The offline, CPU-only final runtime scored **128.8990/150** on the complete
1,000-case public training set: 66.32 classification, 45.3422 extraction, and
17.2368 calibration, with one documented catastrophic false approval. An earlier
internal fixed 799/201 checkpoint measured 129.52 on development and 126.46 on
holdout, with zero holdout catastrophic false approvals. It uses no LLM or VLM,
has no instruction-following component, and does not treat arbitrary document
prose as executable commands.

## System design

The pipeline separates evidence recovery from adjudication. An optional ledger
records final fields, source and rank, conflicts, fusion, decisions, and attempts.

**1. Quarantine hidden content.** Public packets contain non-visible text,
including planted answer-key material. The runtime classifies PyMuPDF-exposed
spans by render mode,
opacity, colour, crop, font context, clipping, transparency, geometry, and paint
order. For the composited baseline, untrusted regions are overwritten before
enhancement or OCR, so contrast repair cannot resurrect them. Direct embedded
scan decoding instead requires viewer binding and otherwise falls back to a new
composited render. The runtime does not parse hidden verdict direction. Hidden
values never populate fields or support approval or denial; pattern metadata may
only narrow to review or affect calibration.

**2. Read visible evidence through independent channels.** RapidOCR runs
low-resolution first and escalates when decision-relevant fields remain missing.
NFKC normalization, closed vocabularies, and plausibility checks constrain
outputs. Manual cancellation requires a viewer-visible word and stroke, and
negated authority is rejected. Accepted raw authority spellings remain bound to
their canonical values so normalization aliases cannot evade matching strikes.
Sanitization rebuilds rank-1 values, evidence, and conflicts together before
strict binding. Ambiguous adverse cancellation can only narrow to review. This
is conservative token/field provenance, not exact occurrence or page
attribution. The baseline pixel observer decodes a raw embedded scan only when
exact resource, geometry, crop/rotation, paint, and compositing checks bind its
pixels to the viewer's page; otherwise it uses a new composited render. The
independent native ledger abstains unless raw-scan authorization succeeds.
Fusion may corroborate or narrow, but cannot create approval alone.

**3. Adjudicate deterministically, then calibrate.** Field-manual rules include
label-supported revoked-sponsor and embargo-world exceptions. Expected value
compares policies offline, not in production. Approvals are checked against their
emitted fields. A rank-1 finding may override lower-rank evidence only on an
accepted note surface; native-text authority additionally requires exact
250-DPI composited raster/OCR corroboration. Foreign-case pages are quarantined;
native-only authority requires an exact body Case ID. Conflicts are recorded,
and fields change only with explicit correction text.
Afterward, an out-of-fold logistic/isotonic model calibrates confidence from
evidence quality and decision path.

## What measurement changed

A historical internal census showed 31–41% of fallbacks already contained the
true value in visible OCR: the parser had failed. Six repairs added about 2.4
development points. A
learned hedge resolver produced 32 new false approvals out of fold; opening
approval with missing flags created 19. A 2.6-million-parameter OCR-correction
model changed score only +0.04 on development and -0.05 on holdout, so it ships
disabled. Joint name-grammar decoding shipped because it improved garbled names
without adding a model or changing adjudication risk.

## Failure boundary and robustness

One public-training false approval remains, MIB-000865. The visible intake scan
reports XW-2 while the label is TRANSIT-7; the labelled value was absent from the
audited visible-evidence channels. The documented broad review-only
corroboration gate removed this error but demoted four correct approvals and
reduced classification score, so I retained the general policy rather than
specialize around a case identity or hidden surface. The larger
residual is missing evidence: when a packet has no decisive flags surface,
`NEEDS_REVIEW` is preferable to guessing from generator priors.

A 12-case synthetic adversarial corpus covers hidden or decoy content plus clean
controls. Its output was byte-identical across
two native ARM64 runs and one emulated AMD64 run, with 12 valid rows, no missing
cases, and no leaked poison tokens. The runtime invokes no barcode or QR-decoding
path. Per-case
deadlines, a parent heartbeat watchdog, worker recycling, atomic checkpoints,
and a batch governor protect completion. The supervisor reserves finalization
time, signals all workers before a shared bounded reap, preserves durable state,
and atomically emits conservative rows for anything unresolved. Governor level
0 is tested as output-equivalent to the ungoverned path. Up to 128 failed-case
candidates may receive one fresh-process retry, subject to an unchanged
3,600-second retry wall and the finalization reserve. Full-batch byte identity is
not claimed across scheduling, governor, architecture, or timeout boundaries.
The pinned suite reported 1,183 passed, 106 controlled skips, and zero failures.

Under the official 4-vCPU, 8-GiB, no-network contract, the final native-ARM64 run
completed 5,000 packets in **19,186.18 seconds**
(**3.8372 seconds/PDF**) with **82 fresh-process retries, all recovered**
(81 watchdog exits with missing primary state and one primary per-case timeout),
zero terminal failures, governor level 0 throughout, and no batch-deadline backfill, from source
`4313d28b34abc4cef4c89586060f4d3d34848c88`; full source/runtime manifest
binding passed. On an eight-case OCR-sensitive panel, adjudications matched
across architectures; fields differed on all eight. Two emulated AMD64 cases
also exhausted timeout and retry, producing conservative fallbacks. The ARM64
fee-reader panel was unchanged from the prior producer. No full AMD64 throughput
or row-identity claim is made. The AMD64
image is 316,434,546 bytes
(`sha256:f6447a9720c0ca52616d83f245ecb804d418b94bd503f8fe57fe551a3e36f95d`);
ARM64 is 286,493,358 bytes
(`sha256:21515e59b31fecaed2eb9983527c0751079abc9c9d3c7711142214c523bdae3f`).
Models total 28,750,436 bytes; the largest is 10,857,958 bytes.

## With another week

I would test rasterized “Reason” lines and faint-ink restoration; expose
per-field confidence; and reproduce on native x86 hardware. Each change would
face held-out, zero-new-false-approval promotion gates.

## Author note

I am a practicing surgeon, not a software engineer, and I am not seeking a job
through this challenge. I directed the work through agentic AI, which wrote
nearly all of the code. I evaluated it through behavioral tests, artifacts, and
failure analysis rather than claiming conventional line-by-line authorship. I
set the objective and threat model, chose what could count as evidence, defined
the promotion gates, directed the failure analyses, and made the final calls
about which measured gains were too unsafe or brittle to ship. The AI produced
the implementation; I own the experimental design, skepticism, trade-offs, and
submission decisions. That division of labour is part of the experiment, and I
would rather disclose it plainly than imply conventional authorship.
