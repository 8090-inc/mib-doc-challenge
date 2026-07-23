# Submission — henrygilbert22

## Solution repository

**URL:** https://github.com/henrygilbert22/mib-doc-challenge-solution

> **Status:** Repository creation and push are **pending Henry review**. The working implementation is at `/home/henry/projects/mib-doc-challenge-work/mib-solution` locally. Do not treat the GitHub URL as live until confirmed.

## Docker contract

| Item | Value |
| --- | --- |
| Entrypoint | `run.sh <input_pdf_dir> <output_predictions_path>` |
| Base image | `python:3.12-slim` + Tesseract 5 (`eng`) |
| Network | None |
| Resources | 4 CPU, 8 GiB RAM, read-only root, `/tmp` tmpfs, `/output` bind mount |
| Parallelism | `MAX_WORKERS=4` process pool |
| Models | None bundled (Tesseract via apt; no ONNX/LLM weights) |
| Measured image | 0.46 GiB uncompressed (iter-13 full eval) |
| Measured throughput | ~0.83 s/PDF on 1,000 train PDFs |

## Validation contract (iter-13 image)

| Metric | Value |
| --- | ---: |
| Predictions | **Regenerating** (Docker run in progress) |
| Throughput | TBD (prior iter-5 run: 0.957 s/PDF) |
| Image size | **0.46 GiB** (iter-13 train) |
| Peak container RAM | TBD |
| Validation score | **Not reported** (private labels) |

`predictions.jsonl` in this folder will be replaced once the iter-13 validation Docker run completes and passes `validate_submission.py --require-complete`.

## Reproduce validation predictions

From a checkout containing both the challenge repo and solution repo:

```bash
python3 /path/to/mib-doc-challenge/scripts/run_docker_submission.py \
  --repo /path/to/mib-doc-challenge-solution \
  --input-dir /path/to/mib-doc-challenge/data/validation \
  --output /path/to/output/predictions.jsonl \
  --manifest /path/to/mib-doc-challenge/data/validation_manifest.csv \
  --require-complete \
  --timeout-seconds 30000 \
  --cpus 4 \
  --memory 8g \
  --image-tag mib-submission
```

Then validate schema:

```bash
python3 /path/to/mib-doc-challenge/scripts/validate_submission.py \
  --submission /path/to/output/predictions.jsonl \
  --manifest /path/to/mib-doc-challenge/data/validation_manifest.csv
```

## This PR folder

| File | Purpose |
| --- | --- |
| `predictions.jsonl` | Validation predictions — **regenerating under iter-13 image** |
| `MEMO.md` | Technical memo (architecture, trust model, measured train results) |
| `SUBMISSION.md` | This file |

## Train proxy (public labels only)

Full-train Docker eval (iteration 13, commit `7095051`): **120.72 / 150** — classification 63.91, extraction 41.77, calibration 15.04, 11 CFAs. Not a validation score.
