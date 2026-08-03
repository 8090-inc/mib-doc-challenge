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

- **Full validation run:** **5,000 valid rows, 0 missing, and 0 terminal
  failures** in **5 hours, 19 minutes, 46 seconds**, or **3.84 seconds per
  PDF**.

## Approach

The runtime follows one rule: a value can affect the result only when the system
can trace it to evidence a reviewer could see and explain why that source is
trusted.

- **Treat the PDF as hostile.** Hidden, clipped, and transparent regions are
  masked before OCR or image enhancement. Their presence may lower confidence
  or trigger review, but their contents can never fill a field or create a
  decision.

- **Read through independent channels.** Native PDF text, masked page renders,
  targeted pixel readers, and a tightly gated raw-scan path remain separate.
  Values must pass schema, plausibility, and cross-page checks; disagreements
  remain attached to the record rather than being silently resolved.

- **Respect visible authority.** A visible adjudicator stamp or signed
  correction can outrank ordinary fields, but only on an accepted note surface.
  Authority found in native PDF text must also appear in a 250-DPI composited
  raster/OCR read. Ambiguous, negated, cancelled, or foreign-case material
  cannot create an approval.

- **Decide first, then calibrate.** Deterministic policy produces
  `APPROVED`, `DENIED`, or `NEEDS_REVIEW`. Only afterward does an out-of-fold
  model estimate confidence; it cannot change the decision or manufacture an
  approval.

When decisive visible evidence is missing, the system returns `NEEDS_REVIEW`
rather than guessing from hidden content, filenames, or generator patterns.

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
