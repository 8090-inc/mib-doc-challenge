# Submission — 1uk4

**Solution repository:** https://github.com/1uk4/mib-solution
**Submitted state:** tag `submission-2026-08-03`

## Build & run

```bash
git clone https://github.com/1uk4/mib-solution
cd mib-solution
docker build -t mib-submission .
docker run --rm --network none \
  -v /path/to/pdfs:/input:ro -v /path/to/out:/output \
  mib-submission /input /output/predictions.jsonl
```

Entrypoint matches the contract (`<input_pdf_dir> <output_predictions_path>`).
Image: `python:3.12-slim` + `tesseract-ocr` + `pillow` — 0.26 GiB, no
model artifacts, no network use at runtime, runs under `--read-only`
with tmpfs `/tmp`. Measured 3.5 s/PDF under the full grading harness
(4 vCPU / 8 GiB).

## Repository orientation

The live pipeline is `v4/` (standalone; the Docker image ships it alone).
`v1/`–`v3/` are earlier iterations kept as frozen history.
`docs/TECHNICAL_DEBRIEF.md` is the design document;
`docs/TECHNICAL_MEMO.md` the layer-by-layer engineering review;
`v4/OBSERVATIONS.md` the dated ledger of every measured experiment,
accepted and rejected. Tests: `python3 -m pytest v4/tests` (159).
