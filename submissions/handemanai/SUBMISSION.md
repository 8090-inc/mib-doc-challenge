# Submission — handemanai

**Public solution repository:** <https://github.com/handemanai/mib-doc-challenge-solution>

Offline, CPU-only document adjudication: visible-text forensics, trap-masked OCR, closed-vocabulary parsing, provenance-aware evidence fusion, deterministic policy adjudication, and calibrated confidence. Expected-value analysis is used to evaluate candidate policies offline; it does not route production decisions. The runtime contains no instruction-following model, but it still treats hidden text and conflicting document channels as an evidence-poisoning threat.

## Artifact identity

| Item | Identity |
| --- | --- |
| Submitted file | `5,000` records; `0` missing; `1,683,486` bytes |
| Predictions SHA-256 | `4ff616d449d1931b461220b21b9c9ca2d1dba3bb82b6e3c021bf659b8f2822be` |
| Prediction-producing public source | [`4313d28b34abc4cef4c89586060f4d3d34848c88`](https://github.com/handemanai/mib-doc-challenge-solution/commit/4313d28b34abc4cef4c89586060f4d3d34848c88) |
| ARM64 local Docker image ID | `sha256:21515e59b31fecaed2eb9983527c0751079abc9c9d3c7711142214c523bdae3f` (286,493,358 bytes) |
| AMD64 local Docker image ID | `sha256:f6447a9720c0ca52616d83f245ecb804d418b94bd503f8fe57fe551a3e36f95d` (316,434,546 bytes) |

The submitted predictions came from one end-to-end container invocation of that public source using the official 4-vCPU, 8-GiB, no-network resource limits, on native ARM64: **19,186.18 seconds** (**3.8372 seconds/PDF**) with **82 fresh-process retries, all recovered** (81 watchdog exits with missing primary state and one primary per-case timeout), zero terminal failures, governor level 0 throughout, and no batch-deadline backfill. No prediction row was edited by hand. The linux/amd64 release image was separately built and tested under emulation on Apple silicon. On an eight-case OCR-sensitive panel, adjudications matched across architectures, while emitted fields were not row-identical on any of the eight. Exactly two emulated AMD64 cases reached both the per-case timeout and retry-failure path and emitted conservative fallback rows. The ARM64 fee-reader panel was unchanged from the prior producer. The full native-ARM64 source/runtime manifest binding passed. No full AMD64 throughput or cross-platform row-identity claim is made. The file passes:

```bash
python3 scripts/validate_submission.py \
  --submission submissions/handemanai/predictions.jsonl \
  --manifest data/validation_manifest.csv --require-complete
```

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

Measured under those restrictions:

| Official constraint | Measured result |
| --- | --- |
| Average runtime ≤ 6 s/PDF | `3.8372` s/PDF on native ARM64 |
| 5,000-PDF runtime ≤ 30,000 s | `19,186.18` s on native ARM64 |
| Memory ≤ 8 GiB | 8 GiB hard limit enforced by Docker |
| Image ≤ 4 GiB uncompressed | 316,434,546-byte AMD64 image; 286,493,358-byte ARM64 image |
| Models ≤ 1 GiB total / 250 MiB each | 28,750,436 bytes total / 10,857,958 bytes largest |
| Output ≤ 25 MiB | `1,683,486` bytes |

The release image was verified for linux/amd64 under emulation. It uses no network, GPU, or API key; it contains no hard-coded host data path and accepts arbitrary mounted input/output paths. Governor level 0 is tested as output-equivalent to the ungoverned path, and the 12-case red-team output repeated byte-identically across two native ARM64 runs and one emulated AMD64 run. Full-batch byte identity is not claimed across scheduling, governor, architecture, or timeout-boundary changes.

## Review notes

- **No answer table or case-specific runtime lookup.** Prediction code and model artifacts contain no validation-case answer mapping.
- **Hidden values cannot support approval or denial.** The runtime does not parse hidden verdict direction. Generic hidden-content presence and field-category indicators may remain as audit, conservative distrust, or calibration signals; hidden values never populate fields or support `APPROVED` or `DENIED`.
- **Viewer binding is fail-closed.** The baseline P0-B observer decodes an embedded scan only when exact resource, geometry, crop/rotation, paint, and compositing checks bind it to the viewer's page; otherwise it uses a fresh composited render. The independent native ledger abstains when raw-scan authorization fails.
- **Cancellation is viewer-bound and monotone.** A word and vector stroke must both be viewer-trusted before cancellation can suppress evidence, and negated authority is rejected. Ambiguous adverse cancellation may narrow to review; it cannot create approval.
- **Raw-to-canonical strike provenance is fail-closed.** Accepted raw authority spellings remain bound to their canonical values so normalization aliases cannot evade matching strikes. Rank-1 values, evidence, and conflicts are rebuilt together before strict binder validation. This is conservative token/field provenance, not exact occurrence or page attribution.
- **Visible rank-1 authority is explicit.** A visible rank-1 adjudicator finding on an accepted note surface may override lower-rank fields. Native-text authority also requires exact 250-DPI composited raster/OCR corroboration of every authority-bearing value; otherwise authority is stripped. Pages confidently naming a foreign case are quarantined; native-only alternate authority additionally requires an exact body Case ID. Conflicts remain recorded, and emitted fields change only when explicit correction text is present.
- **Confidence is descriptive, not the policy.** A deterministic rule engine adjudicates first; an out-of-fold calibrator then estimates confidence from evidence quality.
- **Completion is deadline-bound.** A hard finalization reserve signals all workers before one bounded reap, preserves durable states, and atomically backfills any unresolved cases with validator-safe `NEEDS_REVIEW` rows.
- **Retry capacity is bounded.** Up to 128 failed-case candidates may receive one fresh-process retry, subject to a measured 3,600-second retry wall and the batch finalization reserve.
- **Reproducibility scope is precise.** The predictions were generated directly from the public source identity above. [`NOTICE.md`](https://github.com/handemanai/mib-doc-challenge-solution/blob/4313d28b34abc4cef4c89586060f4d3d34848c88/NOTICE.md) lists model and dependency provenance, including PyMuPDF/AGPL-3.0 obligations and the non-hash-locked rebuild boundary.
- **Tests.** The complete pinned release suite reported 1,183 passed, 106 controlled skips, and zero failures with the full challenge checkout mounted. The adversarial corpus produced 12 valid records with no missing cases or leaked poison tokens, byte-identically across two native ARM64 runs and one emulated AMD64 run.

`MEMO.md` gives the technical rationale and failure analysis. It also discloses the authorship experiment directly: Brian is a practicing surgeon, is not seeking a job through this challenge, directed the work through agentic AI, and owns the objective, evidence rules, safety gates, trade-offs, and final submission decisions.
