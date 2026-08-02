# Submission - zaifnatra

## Public solution repository

https://github.com/zaifnatra/mib-doc-solution

The repository contains the full Dockerized pipeline (`solution.py`, `Dockerfile`, `run.sh`, `requirements.txt`), the technical memo (`MEMO.md`), and the measurement harness (`analysis/`) that produced every number in the memo.
It builds and runs fully offline under the scoring contract:

```bash
docker build -t mib-solution .
docker run --rm --network none --cpus 4 --memory 8g --read-only \
  --tmpfs /tmp -v "$PWD/input:/input:ro" -v "$PWD/output:/output" \
  mib-solution /input /output/predictions.jsonl
```

## Summary

Given a directory of PDF case packets, the pipeline extracts the applicant record and adjudicates each case as `APPROVED` / `DENIED` / `NEEDS_REVIEW`, writing one JSON object per case to `predictions.jsonl`.

- **Public training score: 120.14 / 150** (classification 62.94 / 80, extraction 42.14 / 50, calibration 15.07 / 20), measured on the exact offline submission image via the official `run_docker_submission.py` harness under the scoring runtime (`--network none`, 4 vCPUs, 8 GiB, read-only root FS). 1,000 / 1,000 records, 0 missing, 0 invalid.
- **Runtime: 3.29 s/PDF** on 4 vCPUs (3,294 s for 1,000 packets), against the 6 s/PDF budget. Image size 0.11 GiB against the 4 GiB cap.
- No LLM/VLM or network access. Offline OCR (Tesseract), classical parsing, trust-precedence rules, and batch-learned vocabularies only.

See `MEMO.md` in this folder (and in the solution repo) for the full technical write-up.

## Contents of this folder

- `predictions.jsonl` - validation-set predictions (5,000 cases).
- `MEMO.md` - 1-2 page technical memo.
- `SUBMISSION.md` - this file.
