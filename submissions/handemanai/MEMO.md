# MIB Doc Challenge — Technical Memo

I am a practicing surgeon, not a software engineer. I cannot read or write code.
I entered this challenge to test a simple question: **If AI can write the code,
are curiosity and persistence enough to compete?** My role was to keep
pushing—to ask skeptical questions, demand repeated review, and refuse to accept
work that had not been tested. The agents did all of the implementation,
testing, analysis, and drafting.

## Results at a glance

- **Public training:** **128.90/150** across 1,000 cases (**66.32**
  classification, **45.34** extraction, and **17.24** calibration), with one
  catastrophic false approval.

- **Fixed holdout:** **126.46/150** across 201 cases, with no catastrophic false
  approvals.

- **Full validation run:** **5,000 valid rows with 0 missing** in **5 hours, 19
  minutes, 46 seconds**, or **3.84 seconds per PDF**.

- **Reliability:** **82 of 82 retries recovered**, with **0 terminal failures**,
  governor level 0 throughout, and no batch-deadline backfill.

- **Release verification:** **1,183 tests passed, 106 controlled skips, and 0
  failures**.

## Approach

The production runtime is deterministic. Models were used to build and
repeatedly challenge the system, but no instruction-following model adjudicates
cases. Its governing rule is simple: a value may influence a decision only if
the runtime can explain where it came from and why that source is trusted.

**Separate visible evidence from hidden content.** The PDF layer is examined
for render mode, opacity, color, crop position, clipping, transparency,
geometry, font context, and paint order. Untrusted regions are overwritten
before enhancement or OCR so contrast repair cannot bring hidden text back into
view. The runtime does not parse hidden verdict direction. Hidden values never
populate output fields and never support approval or denial; generic
hidden-content metadata may only lower trust, narrow a case to review, or
contribute to confidence calibration.

**Recover evidence through independent channels.** RapidOCR begins with a
lower-resolution pass and escalates when decision-relevant fields remain
missing. Native PDF text, masked page renders, targeted pixel readers, and an
authorized raw-scan view remain distinct evidence sources. The raw-scan path is
available only when resource identity, geometry, crop, rotation, paint, and
compositing checks bind the pixels to the page a viewer sees. Otherwise it
abstains or uses a new composited render. Parsed values are constrained by the
field schema, closed vocabularies, plausibility checks, source rank, and
cross-page agreement.

**Preserve authority and provenance.** A visible adjudicator stamp or signed
manual note can outrank ordinary fields, but only on an accepted note surface.
Authority originating in native PDF text must also be reproduced by an exact
250-DPI composited raster/OCR read. Cancellation requires both a viewer-visible
word and a visible stroke; negated or ambiguous authority cannot create an
approval. Foreign-case pages are quarantined, conflicts stay attached to the
record, and fields change only when the document contains explicit correction
text.

**Adjudicate first, then calibrate.** Deterministic policy applies the field
manual and label-supported exceptions. Every ordinary approval is checked
against the exact fields that will be emitted. The second evidence ledger may
corroborate a result or move it toward a safer outcome, but it cannot create an
approval by itself. Once the decision is fixed, an out-of-fold
logistic/isotonic model estimates confidence from evidence quality and decision
path. Expected-value analysis was used to compare candidate policies during
development; it is not part of the production decision route.

This architecture is deliberately conservative. When decisive visible
evidence is absent, `NEEDS_REVIEW` is preferable to filling gaps from a hidden
surface, a filename-specific rule, or a generator prior.

## Evaluation and failure boundary

The remaining public-training catastrophic false approval is MIB-000865. Its
visible intake scan reports XW-2 while the label is TRANSIT-7, and the labeled
value was not recoverable through the frozen, audited visible-evidence
channels. A broader corroboration rule removed that error but also demoted four
correct approvals and reduced classification score. I retained the general
policy rather than specialize around one case or use untrusted content. The
larger residual risk is missing evidence: new layouts, faint ink, or absent
flags can still force review or produce an incorrect extraction.

A 12-case synthetic adversarial corpus covers hidden and decoy content,
optional-content layers, visible answer-key bait, barcodes and QR instructions,
watermarks, foreign-case material, and clean controls. It produced 12 valid
rows with no missing cases or leaked poison tokens, byte-identically across two
native ARM64 runs and one AMD64 run emulated on Apple silicon.

## Runtime and reproducibility

The validation result above came from one end-to-end native-ARM64 invocation
under the official **4-vCPU, 8-GiB, CPU-only, no-network** contract. Of the 82
recovered fresh-process retries, 81 followed watchdog exits with no primary
state and one followed a per-case timeout. The final prediction file is
1,683,486 bytes with SHA-256
`4ff616d449d1931b461220b21b9c9ca2d1dba3bb82b6e3c021bf659b8f2822be`.

Completion is protected by per-case deadlines, a parent heartbeat, worker
replacement after 48 durable cases, atomic checkpoints, one bounded retry per
candidate, a 3,600-second retry wall, a batch governor, and a finalization
reserve that emits conservative `NEEDS_REVIEW` rows for anything unresolved.

The prediction-producing source is
`4313d28b34abc4cef4c89586060f4d3d34848c88`, and its native-ARM64 source,
image, configuration, input, evidence, and output binding passed. The AMD64
image was built and tested under emulation, not on native x86 hardware. On an
eight-case OCR-sensitive panel, adjudications matched across architectures,
but fields differed on all eight and two AMD64 cases exhausted both timeout and
retry before emitting conservative fallbacks. I therefore make no claim of
full-batch AMD64 throughput or cross-platform row identity.

## With another week

I would run the full workload on native x86 hardware, test rasterized “Reason”
lines and faint-ink restoration on a prospectively frozen corpus, and expose
per-field confidence in the evidence ledger. Any change would need held-out
benefit, artifact-bound reproduction, and no new catastrophic false approvals
before replacing this release.
