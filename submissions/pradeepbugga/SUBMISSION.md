# Submission — pradeepbugga

## Public solution repository

https://github.com/pradeepbugga/mib-doc-challenge

The solution lives on the `main` branch of that repository and includes a
`Dockerfile` at the repository root.

## Building and running

```bash
docker build -t mib-submission .

mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

The image entrypoint is `run.sh`, which takes `<input_pdf_dir>` and
`<output_predictions_path>` positionally, exactly as required by
`DOCKER_SUBMISSION.md`.

## Verified against the scoring contract

Measured locally with the exact runtime flags from `DOCKER_SUBMISSION.md`
(`--network none --cpus 4 --memory 8g --pids-limit 512 --read-only
--tmpfs /tmp:rw,nosuid,nodev,size=2g`):

| Check | Limit | Measured |
| --- | --- | --- |
| Uncompressed image size | 4 GiB | 1.05 GiB |
| Average runtime per PDF | 6 s | 5.51 s (25-PDF sample) |
| Projected 5,000-PDF runtime | 30,000 s | ~27,550 s (~7.65 h) |
| Predictions file size | 25 MiB | 1.6 MiB |
| Model artifacts | 250 MiB / 1 GiB | none |

The container runs correctly with a read-only root filesystem and no network.
Predictions produced inside the container are byte-for-byte identical to those
produced on the host for a 25-PDF sample (25/25 identical), and
`scripts/validate_submission.py` reports 5,000 valid records with 0 missing
case ids against `data/validation_manifest.csv`.

Note on timing: this is meaningfully tighter than an earlier build's measured
1.43s/PDF. The gap is from additional scored-candidate OCR retries added since
(tear-scanline repair, line-level retry, geometry correction), each of which
only fires conditionally and only costs extra OCR passes on pages that need
them — still comfortably under the 6s/PDF budget and the 8h20m hard cap, but
with less margin than before, and worth watching if further retry-heavy
features are added.

## Runtime characteristics

- Base image: `python:3.12-slim`, plus `tesseract-ocr`, `tesseract-ocr-eng`,
  `tesseract-ocr-osd`, and `libgl1`.
- Python dependencies are version-pinned in `requirements.txt`: PyMuPDF,
  OpenCV (headless), NumPy, pytesseract, Pillow.
- No network access at runtime, no API keys, no external services, no GPU.
- No model artifacts — the system is classical CV plus offline OCR plus
  hand-written rules, so the model-size limits do not apply.
- Runs with a read-only container root filesystem; scratch files go to `/tmp`
  and output to the mounted output path.
- Worker count is capped to fit the 4 vCPU budget (`default_worker_count()`
  in `scripts/predict.py`).

## Contents of this folder

| File | What it is |
| --- | --- |
| `predictions.jsonl` | Predictions for all 5,000 validation packets |
| `MEMO.md` | Technical memo: approach, failure modes, next steps |
| `SUBMISSION.md` | This file |
