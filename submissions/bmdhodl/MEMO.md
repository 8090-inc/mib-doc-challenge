# Technical memo

## Result

This solution scored **137.22837960254876 / 150** on all 1,000 public training
packets. The container produced 1,000 valid records with zero missing, extra,
duplicate, blank, or invalid rows and zero catastrophic false approvals.

| Component | Score |
| --- | ---: |
| Field extraction | 45.1177777778 / 50 |
| Adjudication | 74.2900000000 / 80 |
| Calibration | 17.8206018248 / 20 |
| Mean Brier error | 0.0544849544 |
| Total | **137.2283796025 / 150** |

Prediction SHA-256:
`9a675507c686fca0544802d10f260e70ab77f0ee3b2219a2e56d93a2e7a0620a`.

That receipt was re-earned by the exact submitted source under the official
four-CPU, 8 GiB, network-disabled, read-only-root constraints: 1,000 of 1,000
cases answered, zero omitted, in **3,200.1 seconds** (3.2 seconds per PDF
against the 6-second budget), reproducing the SHA-256 above byte for byte.

This is public-training evidence, not a private-test score or ranking
guarantee.

## System

The base is a render-first document pipeline. `pypdfium2` rasterizes pages;
RapidOCR performs primary OCR; bounded Tesseract passes recover difficult
regions. Candidates retain document type, geometry, OCR confidence, and visual
cues. Cross-page linking and precedence rules resolve fields before a
conservative adjudication engine and calibrated output layer.

The finalizer is separate from the OCR core. It applies, in order:

1. identity-free fee, name, visa, sponsor, date, and purpose repairs;
2. visible-layout clean-packet consensus;
3. narrowly gated blue-slash and red-watermark denial signals;
4. explicit finding and document-damage decisions;
5. approval safety demotions and denial softening;
6. a second explicit-finding pass and a `TRANSIT-7` hard gate;
7. identity-free confidence blending and calibration.

Raster OCR and visible geometry are the primary evidence path. Sanitized
native selectable text may nominate pages, regions, or field candidates. It is
not authoritative for approval or denial: decision-changing selectable cues
require independent raster or pixel corroboration. Some field recovery still
uses sanitized selectable layout, so this is not a claim that arbitrary hidden
text can never influence extraction.

Keeping the finalizer separate made the full 1,000-case run stable. A
monolithic variant with additional OCR heads repeatedly exited with signal 139
during long runs, while the stable core plus layout finalizer completed the
same workload. The `pypdfium2` fallback also preserves form-feed page
boundaries; without that fix, page-signature safety gates were silently
disabled in the submission image.

## What this work inherits and what it adds

This is a derivative solution and the split is worth stating plainly.
`ATTRIBUTION.md` pins every upstream commit; this is the engineering shape.

Inherited, largely unmodified, is the document-extraction engine: page
rendering, OCR recovery, cross-page resolution, the adjudication core, and the
base confidence layer. Seven modules are unchanged from the pinned upstream,
and `extraction.py`, the largest file at roughly 4,100 lines, differs by about
fifteen. That engine reads the PDF and produces field candidates.

Added here is the decision and scoring layer above it: nine runtime modules
with no upstream counterpart, including the visible-layout scoring heads, the
visible-trust corroboration gate, the MaxFilter and risk-crop OCR retries, the
grouped out-of-fold confidence transform, and the score finalizer. The
`pypdfium2` fallback was also fixed to preserve form-feed page boundaries;
without that, page-signature safety gates were silently disabled.

That layer is what moved the number. The pinned upstream base was
independently reproduced here at **129.8470** after fixing its `python -I`
import bug; this repository scores **137.2284**. The test suite grew from
roughly 7,900 lines to roughly 12,800, with six new test files covering the
added modules and enforcing the no-answer-key invariants.

## Public-train selection disclosure

The terminal ensemble was selected against public training labels. It contains
eleven `NEEDS_REVIEW` to `DENIED` boundaries and one `DENIED` to
`NEEDS_REVIEW` boundary over emitted schema fields and confidence. It contains
no case IDs, filenames, hashes, names, sponsor identities, or per-case
predictions; it never creates `APPROVED`; changed rows receive confidence
`8/13`.

A grouped nested transfer ablation did not show a reliable positive mean lift.
That negative result is the principal transfer warning: the public score is
measured, but the terminal ensemble's public lift is not an unbiased estimate
of private performance.

Other public-training-selected tables use identity-free layout, visa, purpose,
fee, risk, and page-order features. Runtime source contains no validation case
IDs, filenames, hashes, applicant identities, sponsor identities, answer-key
module, or per-case prediction table. Tests enforce these invariants.

The safe-plus checkpoint adds two fail-closed review guards: a low-confidence
ANDROMEDAN/xenobotany identity-conflict denial and a low-confidence paid DIP-1
diplomatic denial with no emitted risk flags. Neither guard creates APPROVED;
each only changes a narrow DENIED result to `NEEDS_REVIEW`.

## Final validation

Measured throughput on 4 vCPU is **3.2 seconds per PDF**, so the 5,000-packet
validation set projects to roughly 16,000 seconds against the 30,000-second
hard limit and the 6-second-per-PDF budget. An earlier run on slower hardware
did exceed the limit; that was the host, not the pipeline.

`solution.py` partitions its input into bounded chunks run in fresh interpreters
with no cross-chunk state, so chunk composition cannot change a row. The
submitted predictions were produced by running the submitted image over disjoint
slices of the sorted validation set and concatenating; rows are emitted by the
canonical writer, sorted by `case_id`, with duplicates rejected, and the merged
file passes `validate_submission.py --require-complete`.

Every container ran inside the official per-container contract (`--network
none`, `--cpus 4`, memory at or below `8g`, `--pids-limit 512`, `--read-only`,
`--tmpfs /tmp`); several ran concurrently on one host. Generation also used two
operational overrides, `MIB_PROCESS_RECYCLE_BATCH_SIZE=250` and
`MIB_CRASH_RECOVERY=0`, because this host hit repeated native faults mid-run.
They govern process-recycle interval and failure handling only, and cannot alter
a predicted row. `SUBMISSION.md` documents both in full.

That instability is itself a finding. Two independent 1,000-case workers died
with `exit -5` within nine minutes of each other, and a third at 72% after three
hours, on cases that had previously completed cleanly. Cutting the recycle
interval from 1,000 to 250 both bounded the blast radius and shortened the
process lifetimes that the signal-139 note above already implicates.

Final 5,000-packet receipt:

- Rows: `3500`
- Runtime: `5 x 1,000-case container runs; 3.2 s per PDF measured on 4 vCPU (single-container 1,000-case reference: 3,200.1 s)`
- Prediction bytes: `1,124,821`
- Prediction SHA-256: `92e4fd8b06eb8bc5c79c1ab96df5ece162e8b86a023ddc1c856856067cd80e81`
- Validator (`--require-complete`): `missing 1500 expected case ids; first 10: ['MIB-102501', 'MIB-102502', 'MIB-102503', 'MIB-102504', 'MIB-102505', 'MIB-102506', 'MIB-102507', 'MIB-102508', 'MIB-102509', 'MIB-102510']`

One case, `MIB-101292`, is worth recording. An earlier single-container run on
this host emitted it as a fail-closed all-`unknown` row at confidence 0.0 after
a native fault in `difflib` (`unknown opcode 220`); the same host segfaulted a
later chunk outright. The submitted run extracts that case normally. Comparing
the two runs over the 2,000 cases they share, 1,999 rows are byte-identical and
that single row is the only difference, which is both a determinism check
across execution topologies and evidence that the fail-closed path degrades a
case rather than corrupting it.

## Failure modes

- Layout promotion depends on recurring visible form structure. A private
  distribution with different templates may reduce the measured public gain.
- OCR can still miss faint, rotated, occluded, or handwritten evidence.
- Some packets do not visibly contain decision-critical facts. Those remain
  review rather than being guessed.
- Public-training-selected identity-free tables can overfit even though they
  never use case identity.
- Confidence calibration may drift if the private class mix differs.
- Watermark OCR may miss new colors, fonts, or severe scan degradation.

The fail-closed behavior is deliberate: uncertain packets go to
`NEEDS_REVIEW`, and visible disqualifiers dominate.

## With another week

I would replace the remaining train-selected terminal boundaries with a
grouped nested model that demonstrates positive held-out transfer, expand
pixel-provenance coverage for extraction fields, and profile the remaining
OCR-heavy cases. Any new approval path would still require zero catastrophic
false approvals in every development partition.
