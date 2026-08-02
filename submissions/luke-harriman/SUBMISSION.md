# Submission — luke-harriman

**Public solution repository:** https://github.com/luke-harriman/mib-doc-challenge-solution

That repository contains the `Dockerfile`, the full pipeline source, and the fitted
assets. It builds and runs offline with no network, no API keys, and no external
services:

```bash
docker build -t mib .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib /input /output/predictions.jsonl
```

## Contents of this folder

| File | What it is |
| --- | --- |
| `predictions.jsonl` | Predictions for all 5,000 validation cases. Passes `scripts/validate_submission.py --require-complete` with exit 0. |
| `MEMO.md` | Technical memo: approach, failure modes, and next steps. |
| `SUBMISSION.md` | This file. |

## Approach in one paragraph

The corpus is the output of one deterministic program, so the pipeline models that
program rather than fitting label statistics: visibility-filtered PDF parsing, dual-engine
OCR with matched-filter recovery on pages both engines fail, fusion by measured source
precedence, and a rule engine that reproduces the generator's adjudication function,
with expected-value decisions under the published scoring matrix. No LLM, no VLM, no
network. The hidden "answer key" injected into ~25% of packets is filtered both
structurally and by content and is never used.

## Declared third-party components

PyMuPDF (AGPL-3.0 — solution repository is published in full), RapidOCR / PP-OCR ONNX
(Apache-2.0), Tesseract (Apache-2.0), OpenCV (Apache-2.0), NumPy (BSD-3), RapidFuzz (MIT).
No code was copied from other participants' submissions.
