# Submission — tcballard

**Solution repository:** https://github.com/tcballard/mib-doc-challenge
(`main` branch), solution code under `solution/`, `Dockerfile` at the
repository root.

The built image runs fully offline (no network, CPU only, no GPU) and
accepts exactly the required two arguments:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Contents of this folder

- `predictions.jsonl` — predictions for the 5,000-case validation set.
- `MEMO.md` — technical memo (approach, results, failure modes, next steps).
- `SUBMISSION.md` — this file.

## Runtime

- Offline OCR (`tesseract-ocr`) + PyMuPDF; no API keys or external services.
- Parallelized across CPU cores; measured 4.1s per PDF end-to-end on 4 vCPU (200-packet cold-start sample), within the
  6s/PDF budget.
- Image size and model-artifact limits are satisfied (no large model artifacts;
  the pipeline is rules + Tesseract).

## Reproducibility / anti-gaming

- No hardcoded per-case answers or lookup tables keyed to specific PDFs.
- Embargo-world and revoked-sponsor policy lists are derived from public training
  labels and in-document adjudicator-note reasons; regenerate them with
  `python3 solution/scripts/derive_policy_lists.py`.
- Deterministic: same input always yields the same output.
