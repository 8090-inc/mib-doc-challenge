# MIB Doc Challenge — Submission

- **Solution repository (public, contains `Dockerfile`):** <https://github.com/LukaJurisic/mib-doc-challenge-solution>
- **Generation receipt:** [`docs/V6_S4_BASELINE_GENERATION_RECEIPT.json`](https://github.com/LukaJurisic/mib-doc-challenge-solution/blob/9e140db7f2ca88d3af569d129df869164e2efdfa/docs/V6_S4_BASELINE_GENERATION_RECEIPT.json)
- **Current submitter:** Luka Jurisic (`LukaJurisic`)
- **Attributed technical origin:** Calling Moonshots,
  [`callingmoonshots/mib-doc-challenge-solution@9ed5ed360ae40053dfee80bff09eef29a83a3980`](https://github.com/callingmoonshots/mib-doc-challenge-solution/tree/9ed5ed360ae40053dfee80bff09eef29a83a3980)
- **Executable baseline prediction source:**
  `7da47773b39609a4e162a5e1b448d5f5657436bc`
- **Earlier upstream attribution:** Calling Moonshots derived its implementation
  under MIT from Brian Pridgen's public
  [`handemanai` baseline](https://github.com/handemanai/mib-doc-challenge-solution/tree/4b37a7815bea79de0a01beca6eb6566e1611af73);
  the original copyright and license are preserved.

This repository is a fork and release/infrastructure adaptation. Luka's changes
are prediction-neutral orchestration, build pinning, provenance, validation,
and packaging; the upstream prediction logic, models, evidence sources, rules,
thresholds, outputs, adjudications, confidence values, and serialization remain
unchanged.

## What this is

An offline, CPU-only adjudication engine for the MIB intergalactic intake desk.
It reads adversarial PDF case packets, extracts the ten applicant fields, and
recommends `APPROVED` / `DENIED` / `NEEDS_REVIEW` with a calibrated confidence.
Every decision is backed by a per-case evidence ledger.

See `MEMO.md` for the full technical write-up (approach, negative results,
failure modes, and what another week buys).

## Runtime contract compliance

- Runs under `--network none --cpus 4 --memory 8g --read-only --tmpfs /tmp`.
- Entrypoint accepts `<input_pdf_dir> <output_predictions_path>`.
- No LLM, VLM, cloud OCR, or network service at inference time. OCR is RapidOCR
  (PP-OCRv4 mobile detector + en_PP-OCRv5 mobile recognizer, ONNX); everything
  else is classical CV, deterministic rules, and a candidate-trained shallow
  forest restricted to `insufficient_evidence` reviews. Its runtime is a
  dependency-free JSON evaluator and its features exclude case IDs and open
  applicant/sponsor identities. The optional 2.6M-parameter character
  transducer remains disabled. Nothing in the runtime follows instructions, so
  the injection surface the dataset targets does not exist in this system.
- The production image is built once for `linux/amd64` from a digest-pinned
  base, published by OCI digest, and reused by every GitHub Actions task. Exact
  source, image, model, dependency, and inspection hashes are recorded in the
  attached `V6_S_IMAGE_BUILD_MANIFEST.json` and generation receipt.
- Exact independently reproduced public-data score:
  **134.71776441333333 / 150** (45.47333333333333 extraction,
  71.92999999999999 classification, 17.314431080000002 calibration), with
  **12 catastrophic false approvals** and prediction SHA-256
  `79e05c3c1ea8639d4cb3a5b97036fdff2fc2ed5492b4818b56d2e536eb2f78d5`.
- The frozen 40-case prediction SHA-256 is
  `3d3f2f4e6a538c9955c1a755eb64627045a2b7cfbb283767bab4024be8d8b198`.
- Luka's V6-S3 pipeline independently generated 5,000 complete validation rows
  with SHA-256
  `08ba6fb615129dccd78ce29025d8d3945b7bea1b1e5bec4a0093fb8e7ec8e71f`.
  This is Luka's frozen regression hash, not an organizer truth oracle. No
  participant prediction rows were downloaded or compared.
- Per-case deadlines, a parent heartbeat watchdog, and planned worker recycling
  keep a single packet or a native-library process-lifetime fault from
  preventing validator-safe output. Completed rows are durable before a worker
  is replaced, and the scorer-facing file is refreshed during long runs.

## Reproduce

Run these commands from a checkout of the organizer challenge repository so its
validation data and validator remain available. The executable prediction-code
identity in the pinned solution release remains
`7da47773b39609a4e162a5e1b448d5f5657436bc`.

```bash
git clone https://github.com/LukaJurisic/mib-doc-challenge-solution \
  /tmp/mib-doc-challenge-solution
git -C /tmp/mib-doc-challenge-solution checkout --detach \
  9e140db7f2ca88d3af569d129df869164e2efdfa
docker build -t mib-submission /tmp/mib-doc-challenge-solution
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-out,dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/validate_submission.py \
  --submission /tmp/mib-out/predictions.jsonl \
  --manifest data/validation_manifest.csv \
  --require-complete
```

## Predictions

The submitted `predictions.jsonl` lives in the challenge repository at
`submissions/LukaJurisic/predictions.jsonl`, together with this memo and
provenance record. The release gate requires exactly 5,000 valid rows, 5,000
unique manifest IDs, no missing or extra IDs, byte-identical repeat
finalization, official `--require-complete` validation, and SHA-256
`08ba6fb615129dccd78ce29025d8d3945b7bea1b1e5bec4a0093fb8e7ec8e71f`.

## Runtime disclosure

The untouched Luka laptop run hit the hard 30,000-second limit with 4,755 of
5,000 extraction states observed complete and no valid terminal artifact. The
later V6-RU affinity run was stopped after 707 states in 6,082.654 seconds, an
optimistic projection of approximately 43,017 seconds. The local runtime gate
therefore **did not pass**, and organizer-host performance remains unresolved.

The prediction artifact is generated with disclosed, deterministic,
prediction-parity GitHub Actions orchestration from the exact frozen source.
That establishes prediction validity and completeness; it does not prove that
the original container meets the organizer's 30,000-second limit on the
organizer's host. See `docs/V6_S_LOCAL_RUNTIME_DISCLOSURE.md` and the generated
receipt set for complete evidence.
