# Submission — handemanai

**Public solution repository:** <https://github.com/handemanai/mib-doc-challenge-solution>

This is an offline, CPU-only document-adjudication system. It recovers the nine
required fields from adversarial PDF packets, applies deterministic policy, and
emits `APPROVED`, `DENIED`, or `NEEDS_REVIEW` with calibrated confidence. It
contains no LLM, VLM, cloud OCR, network service, API key, or component that
follows document instructions.

## Final artifact

| Item | Final identity |
| --- | --- |
| Validation predictions | `5,000` records; `0` missing; `1,683,486` bytes |
| Predictions SHA-256 | `4ff616d449d1931b461220b21b9c9ca2d1dba3bb82b6e3c021bf659b8f2822be` |
| Prediction-producing source | [`4313d28b34abc4cef4c89586060f4d3d34848c88`](https://github.com/handemanai/mib-doc-challenge-solution/commit/4313d28b34abc4cef4c89586060f4d3d34848c88) |
| ARM64 image used for generation | `sha256:21515e59b31fecaed2eb9983527c0751079abc9c9d3c7711142214c523bdae3f` (286,493,358 bytes) |
| AMD64 image tested under emulation | `sha256:f6447a9720c0ca52616d83f245ecb804d418b94bd503f8fe57fe551a3e36f95d` (316,434,546 bytes) |

The submitted file came from one end-to-end native-ARM64 container invocation
of the named source. No row was edited by hand. Under the official 4-vCPU,
8-GiB, read-only-root, no-network contract, the run processed all 5,000 PDFs in
**19,186.18 seconds**—**5 hours, 19 minutes, 46 seconds**, or **3.8372 seconds
per PDF**. It made **82 fresh-process retries**, all recovered: 81 followed
watchdog exits with no primary state and one followed a per-case timeout. There
were zero terminal failures, governor level 0 for every row, and no
batch-deadline backfill. The official validator accepted all 5,000 records, and
the full source/runtime/input/output binding and strict evidence census passed.

## Approach and safety boundaries

- **Visible evidence controls decisions.** Hidden spans are masked before image
  enhancement and OCR. The runtime does not parse hidden verdict direction;
  hidden values never populate fields or support approval or denial. Generic
  hidden-content metadata may only lower trust, narrow to review, or contribute
  to calibration.
- **Evidence remains source-bound.** Native text, masked renders, targeted pixel
  readers, and an authorized raw-scan view remain separate channels. A direct
  scan read must be bound to the page a viewer sees; otherwise that channel
  abstains or uses a fresh composited render.
- **Authority is fail-closed.** Signed-note and stamp findings require an
  accepted visible surface. Native-text authority also requires exact 250-DPI
  raster/OCR corroboration. Foreign-case pages are quarantined, conflicts remain
  explicit, and ambiguous cancellation cannot create an approval.
- **Policy precedes confidence.** Deterministic rules adjudicate the emitted
  fields first. An out-of-fold logistic/isotonic model then estimates confidence
  from evidence quality. Expected-value analysis is development-only and does
  not route production decisions.
- **Completion is conservative.** Per-case deadlines, a parent heartbeat,
  worker recycling after 48 durable cases, atomic checkpoints, bounded retries,
  a batch governor, and a finalization reserve prevent one pathological PDF from
  invalidating the batch. Anything unresolved becomes a valid `NEEDS_REVIEW`
  row.

Prediction code and model artifacts contain no validation-case answer table or
case-specific runtime lookup. The container accepts arbitrary mounted input and
output paths and ships no challenge labels or validation data.

## Published contract measurements

| Official constraint | Measured result |
| --- | --- |
| Runtime ≤ 6 s/PDF average | `3.8372` s/PDF on native ARM64 |
| 5,000-PDF runtime ≤ 30,000 s | `19,186.18` s on native ARM64 |
| Memory ≤ 8 GiB | 8-GiB hard limit enforced by Docker |
| Image ≤ 4 GiB uncompressed | 316,434,546-byte AMD64 image; 286,493,358-byte ARM64 image |
| Models ≤ 1 GiB total / 250 MiB each | 28,750,436 bytes total / 10,857,958 bytes largest |
| Output ≤ 25 MiB | 1,683,486 bytes |

The pinned release suite reported **1,183 passed, 106 controlled skips, and zero
failures** with the complete challenge checkout available. A 12-case adversarial
panel produced 12 valid rows with no missing cases or leaked poison tokens,
byte-identically across two native ARM64 runs and one emulated AMD64 run.

## Build and run

From a clean clone of the public solution repository:

```bash
PRODUCER_SHA=4313d28b34abc4cef4c89586060f4d3d34848c88
git checkout --detach "$PRODUCER_SHA"
docker build --platform linux/amd64 \
  --label "org.opencontainers.image.revision=$PRODUCER_SHA" \
  -t "mib-submission:$PRODUCER_SHA" .
docker run --rm --platform linux/amd64 \
  --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  "mib-submission:$PRODUCER_SHA" /input /output/predictions.jsonl
```

The file in this pull request passes:

```bash
python3 scripts/validate_submission.py \
  --submission submissions/handemanai/predictions.jsonl \
  --manifest data/validation_manifest.csv --require-complete
```

## Limitations and disclosure

The complete generation run was native ARM64. The AMD64 image was built and
tested under emulation on Apple silicon, not on native x86 hardware. On an
eight-case OCR-sensitive panel, adjudications matched across architectures, but
fields differed on all eight and two AMD64 cases exhausted timeout and retry
before emitting conservative fallbacks. No full-batch AMD64 throughput or
cross-platform row-identity claim is made. Dependency and model provenance,
including PyMuPDF's AGPL-3.0 terms and the non-hash-locked rebuild boundary, is
recorded in the source repository's
[`NOTICE.md`](https://github.com/handemanai/mib-doc-challenge-solution/blob/4313d28b34abc4cef4c89586060f4d3d34848c88/NOTICE.md).

I am a practicing surgeon, not a software engineer. I participated in this
challenge to test the capabilities of agentic coding. I directed the agents by
setting the priorities, asking them to research unfamiliar questions, requiring
repeated skeptical reviews, and spending a great deal of time pushing them to
look for hidden evidence, document traps, unsafe approvals, and brittle
improvements. I asked questions, challenged conclusions, and decided what
evidence was strong enough to act on. The agents did all of the implementation,
testing, analysis, and drafting. `MEMO.md` explains the system, its remaining
failure boundary, and what I would do with another week.
