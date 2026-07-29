# MIB Doc Challenge — Submission

- **Solution repository (public, contains `Dockerfile`):** <https://github.com/callingmoonshots/mib-doc-challenge-solution>
- **Candidate:** patelchanakya / Calling Moonshots
- **Upstream attribution:** Derived under MIT from Brian Pridgen's public
  [`handemanai` baseline](https://github.com/handemanai/mib-doc-challenge-solution/tree/4b37a7815bea79de0a01beca6eb6566e1611af73);
  the original copyright and license are preserved.

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
- Measured under those exact flags via the organizers' own
  `scripts/run_docker_submission.py`: **0.27 GiB image** (4 GiB cap),
  **14,144,822 bytes of model artifacts** (1 GiB total / 250 MiB per-artifact
  caps), **4.36s/PDF** on the fresh full-1,000 run, and **6h36m46s total
  (4.761s/PDF)** on the required 5,000-case validation run against the 8h20m
  limit.
- Immutable validation image:
  `sha256:119ef2a0d92d30a121e89379fdf22fd2dd1f38822f0e32694dd6fa9b0f9e210f`;
  source-manifest SHA-256:
  `a852a584e8e1644b8d830e159d3efd48803e18c7f33dfece859a1a480205dc1b`.
- Exact public-data score: **134.71711362222223 / 150**, versus
  **128.82639727555556** for the original image: 45.4722 extraction, 71.9300
  classification, and 17.3149 calibration. Catastrophic false approvals:
  **12 versus 1**; all are included in the official score.
- Deterministic seeds; the fresh full-1,000 Docker output was semantically
  identical for every case to the frozen compliance replay.
- Per-case deadlines, a parent heartbeat watchdog, and planned worker recycling
  keep a single packet or a native-library process-lifetime fault from
  preventing validator-safe output. Completed rows are durable before a worker
  is replaced, and the scorer-facing file is refreshed during long runs.

## Reproduce

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-out,dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/validate_submission.py \
  --submission /tmp/mib-out/predictions.jsonl \
  --manifest data/validation_manifest.csv
```

## Predictions

The submitted `predictions.jsonl` is not in this repository — it lives in the
challenge repository under `submissions/patelchanakya/`, together with the memo and
this provenance record. Its SHA-256 is
`2d52fae3e8d0f85b9668fa6301440f73854ef6c0aef9ee64abb1903302091529`.
Reproducing the command above on `data/validation` regenerates it. The
organizers' validator and an independent second invocation both report 5,000
valid records, 5,000 unique manifest IDs, and no missing cases.
