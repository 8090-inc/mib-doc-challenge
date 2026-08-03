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

The holdout result above had no catastrophic false approvals. Public training
still contains one: MIB-000865. Its visible scan says XW-2 while the label says
TRANSIT-7, and no trusted visible channel recovers the labeled value. A broader
rule fixed that case but demoted four correct approvals and lowered the score,
so the release keeps the general rule rather than special-casing one example.
This exposes the main remaining risk: faint, missing, or unfamiliar evidence
can still force review or produce an incorrect extraction.

The hidden-content defenses were also tested on 12 synthetic adversarial cases
containing decoy layers, visible answer-key bait, QR instructions, watermarks,
foreign-case material, and clean controls. All 12 produced valid rows with no
missing cases or leaked poison tokens, byte-identically across two native ARM64
runs and one AMD64 run under emulation. This was a focused security check, not a
claim of broad robustness.

## Runtime and reproducibility

The 5,000-case result above came from one end-to-end native-ARM64 run under the
official **4-vCPU, 8-GiB, CPU-only, no-network** contract. The runtime made 82
fresh-process retries; all recovered and none became a terminal failure. Case-level
checkpoints, bounded retry, worker replacement, and a final time reserve are
designed to prevent an individual failure from ending the batch.

The AMD64 image was built and tested only under emulation, not on native x86
hardware. On an eight-case OCR-sensitive panel, decisions matched across
architectures, but extracted fields differed on all eight and two AMD64 cases
exhausted both timeout and retry before emitting conservative fallbacks. The
release therefore makes no claim of native-AMD64 throughput or cross-platform
row identity.

## With another week

I would run the full workload on native x86 hardware, test rasterized “Reason”
lines and faint-ink restoration on a prospectively frozen corpus, and expose
per-field confidence in the evidence ledger. Any change would need held-out
benefit, artifact-bound reproduction, and no new catastrophic false approvals
before replacing this release.
