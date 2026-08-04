# Submission — ShreyShingala

**Solution repository (public, contains a `Dockerfile`):** https://github.com/ShreyShingala/ocr-document-pipeline-challenge

## Contents of this folder

| File | What it is |
| --- | --- |
| `predictions.jsonl` | Predictions for the 5,000-packet validation set |
| `MEMO.md` | 1-2 page technical memo — approach, failure modes, next steps |
| `SUBMISSION.md` | This file |

## How to run the image

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/abs/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/abs/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

The entrypoint takes `<input_pdf_dir> <output_predictions_path>` and runs fully offline.

## Contract compliance

Measured inside the image under the published scoring contract, not on the host:

| Requirement | Limit | Measured |
| --- | --- | --- |
| Image size | 4 GiB | 933 MB |
| Largest model artifact | 250 MiB | 14.7 MB (`mib.traineddata`) |
| Total model artifacts | 1 GiB | 28 MB |
| Runtime, average | 6 s/PDF | 2.32 s/PDF |
| Network at runtime | none | runs under `--network none`; no HTTP call in shipped code |
| Read-only rootfs + tmpfs | required | `TMPDIR=/tmp`, verified under `--read-only` |
| LLM / VLM / cloud OCR | forbidden | none; RapidOCR ONNX + Tesseract LSTM, both local |
| Case-id or filename keyed rules | forbidden | zero occurrences in the shipped tree |
| Hidden text, answer keys, barcode payloads | forbidden | dropped at the parse trust boundary |

Deterministic score on the public training set, in-container: **133.65 / 150** (70.46
classification, 45.75 extraction, 17.44 calibration), 11 catastrophic false approvals, 0 missing
cases, 0 invalid records.
