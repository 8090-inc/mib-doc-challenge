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

## Validation contract (iter-15 image)

| Metric | Value |
| --- | ---: |
| Predictions | **5,000 / 5,000** |
| Throughput | ~0.83–1.0 s/PDF class (train measured ~0.83) |
| Image size | **0.46 GiB** |
| Peak container RAM | ~1.3 GiB class (prior measured runs) |
| Validation score | **Not reported** (private labels) |

`predictions.jsonl` matches the iter-15 Docker validation run and passes `validate_submission.py --require-complete`.

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
| `predictions.jsonl` | Validation predictions — **matches iter-15 Docker validation run (post TRANSIT embed OCR)** |
| `MEMO.md` | Technical memo (architecture, trust model, measured train results) |
| `SUBMISSION.md` | This file |

## Train proxy (public labels only)

Full-train Docker eval (iteration 14, commit `215bc56`): **121.18 / 150** — classification 64.1, extraction 42.0, calibration 15.08, 11 CFAs. Not a validation score.
