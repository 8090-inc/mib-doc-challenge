# Submission — henrygilbert22

## Solution repository

| | |
| --- | --- |
| **URL** | https://github.com/henrygilbert22/mib-doc-challenge-solution |
| **Status** | **Pending** — repo creation/push not confirmed. Working tree: `/home/henry/projects/mib-doc-challenge-work/mib-solution` |
| **Commit** | `215bc56` |

## Docker contract

| Item | Value |
| --- | --- |
| Entrypoint | `run.sh <input_pdf_dir> <output_predictions_path>` |
| Base image | `python:3.12-slim` + Tesseract 5 (`eng`) |
| Network | None |
| Resources | 4 CPU, 8 GiB RAM, read-only root, `/tmp` tmpfs, `/output` bind mount |
| Parallelism | `MAX_WORKERS=4` process pool |
| Models | None (Tesseract via apt; no ONNX/LLM weights) |
| Image size | **0.46 GiB** (iter-15) |
| Throughput | **~0.83–1.1 s/PDF** (validation ~0.83 class; train with embedded-image OCR ~1 s/PDF) |
| Peak RAM | ~1.3 GiB (prior measured runs) |

## Validation (iter-15 image)

| Metric | Value |
| --- | ---: |
| Predictions | **5,000 / 5,000** |
| Score | Not reported (private labels) |

`predictions.jsonl` is byte-identical to the iter-15 Docker validation run. Passes `validate_submission.py --require-complete`.

## Train proxy (public labels only)

Official Docker full train, iter-15, commit `215bc56`:

| Section | Score |
| --- | ---: |
| Total | **121.18** / 150 |
| Classification | 64.10 |
| Extraction | 42.00 |
| Calibration | 15.08 |
| CFAs | 11 |

Not a validation score.

## Reproduce validation predictions

From a checkout with both challenge and solution repos:

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

Validate schema:

```bash
python3 /path/to/mib-doc-challenge/scripts/validate_submission.py \
  --submission /path/to/output/predictions.jsonl \
  --manifest /path/to/mib-doc-challenge/data/validation_manifest.csv
```

Reproduce train score (requires `data/train_labels.csv`):

```bash
python3 /path/to/mib-doc-challenge/scripts/run_docker_submission.py \
  --repo /path/to/mib-doc-challenge-solution \
  --input-dir /path/to/mib-doc-challenge/data/train \
  --output /path/to/output/train_predictions.jsonl \
  --manifest /path/to/mib-doc-challenge/data/train_labels.csv \
  --require-complete \
  --cpus 4 --memory 8g --image-tag mib-submission

python3 /path/to/mib-doc-challenge/scripts/evaluate_submission.py \
  --submission /path/to/output/train_predictions.jsonl \
  --labels /path/to/mib-doc-challenge/data/train_labels.csv
```

## This folder

| File | Purpose |
| --- | --- |
| `predictions.jsonl` | Validation predictions (iter-15 Docker run) |
| `MEMO.md` | Architecture, rejected ideas, train results |
| `SUBMISSION.md` | This file |
