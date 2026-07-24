# Submission

**Solution repository:** https://github.com/adityanaidu16/mib-doc-challenge-solution

This repository contains the full offline pipeline for the MIB Doc Challenge:
a Dockerised, network-free document-processing system that extracts applicant
records from PDF packets and adjudicates each case as `APPROVED`, `DENIED`, or
`NEEDS_REVIEW`.

## Contents

- `Dockerfile` — self-contained offline image (0.65 GiB, CPU-only).
- `mib/` — the pipeline (trust layer, OCR, extraction, policy, models).
- `models/calibrator.pkl` — the trained residual/confidence model (0.44 MB).
- `MEMO.md` — technical memo (approach, failure modes, next steps).
- `requirements.txt` — pinned to the exact versions the model was trained under.

## Run contract

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=<pdf_dir>,dst=/input,readonly \
  --mount type=bind,src=<out_dir>,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Validated end-to-end under the exact scoring contract: builds offline, runs with
no network, produces schema-valid predictions at ~1.3 s/PDF serial (5,000 PDFs
well within the 30,000 s hard limit). Parallelism is opt-in via `MIB_WORKERS`.
