# Submission: rupaut98

- Solution repository (public, Dockerfile at root): https://github.com/rupaut98/mib-doc-solution
- Predictions: `predictions.jsonl` (5,000 validation cases, validated with `scripts/validate_submission.py`)
- Technical memo: `MEMO.md`

## Reproduce

```bash
docker build -t mib-submission https://github.com/rupaut98/mib-doc-solution.git
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Runtime: Tesseract (offline OCR) + PyMuPDF + RapidFuzz rules. No LLMs, VLMs,
cloud OCR, or network access.
