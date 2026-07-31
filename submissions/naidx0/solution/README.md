# MIB Doc Challenge — Solution

An offline, CPU-only document-processing pipeline that reads a directory of PDF case packets and
writes `predictions.jsonl` (one JSON object per case): extracted applicant fields plus an
`APPROVED` / `DENIED` / `NEEDS_REVIEW` adjudication and a calibrated confidence.

No network, no LLM/VLM, no cloud APIs at runtime — only Tesseract OCR, classical image processing,
and a rules engine reverse-engineered from the public training labels.

## Layout
```
solution/
  Dockerfile        # tesseract-ocr + poppler + pinned Python deps
  run.sh            # entrypoint: run.sh <input_pdf_dir> <output_path>
  requirements.txt  # pinned Python dependencies
  solution.py       # orchestrates ingest -> extract -> adjudicate, parallel + robust
  ingest.py         # PDF -> per-page evidence (text layer + OCR), with trust tagging
  extract.py        # evidence -> 12 fields, fuzzy enum canonicalization
  adjudicate.py     # verified decision policy + confidence calibration
  trust.py          # prompt-injection / hidden-text filtering
  POLICY.md         # the reverse-engineered adjudication policy, with evidence
```

## Build & run (the exact scoring contract)
```bash
docker build -t mib-submission submissions/naidx0/solution
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Local scoring against the training labels
```bash
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json
```

## Design notes
- **Two-mode reading.** Each form page is either a clean PDF text layer or a degraded scanned image.
  The pipeline reads the text layer with per-span colour and position when present, and falls back to
  Tesseract OCR (grayscale, contrast, deskew, orientation correction) for image pages.
- **Injection resistance.** White / near-white text, off-crop text, barcode payloads, and fake
  `SYSTEM:`/"answer key" prompts are tagged untrusted and excluded from every field and the decision.
  A value available only from untrusted text is treated as unknown, which pushes the case to
  `NEEDS_REVIEW` rather than a confident (wrong) answer.
- **Cross-page resolution.** Fields follow a source precedence (I-8090 form > biometric slip >
  registry > sponsor letter); contradictions among trusted pages trigger review.
- **Policy engine.** See `POLICY.md` — hard denials are evaluated before review signals, so an
  illegible-but-otherwise-disqualified packet is denied, while an illegible-only packet is reviewed.
- **Calibrated confidence** approximates the probability the decision is correct, to score well on the
  Brier-based calibration metric and to avoid the severe false-approval penalty.
