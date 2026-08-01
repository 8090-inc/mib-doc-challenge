# Submission — midasavocado

**Solution repository:** https://github.com/midasavocado/mib-doc-challenge-solution

Public, MIT-licensed, and contains a `Dockerfile` at the repository root.

## Runtime contract

```bash
docker build -t mib-doc-solution .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-doc-solution /input /output/predictions.jsonl
```

The image accepts exactly `<input_pdf_dir> <output_predictions_path>`. It runs
CPU-only and fully offline: Poppler and Tesseract from the Debian base, RapidOCR
ONNX models vendored in the pinned wheel. No network access, API keys, external
services, LLMs, VLMs, or cloud OCR at runtime. Python dependencies are installed
with `--require-hashes --no-deps` from `requirements.lock`. Temporary files are
written under `/tmp`; the only output is the requested path.

## Verification

```bash
pytest tests            # contract, trust-boundary, and safety-invariant suite
```

The suite runs from a clean checkout with nothing but `pytest` installed — tests
needing the OCR stack or a generated predictions file skip rather than fail. Point
`MIB_PREDICTIONS` at a run to turn the output invariants into a pre-submission gate:

```bash
MIB_PREDICTIONS=/path/to/predictions.jsonl pytest tests
```

## Notes for review

- **Evidence policy.** Visible pixels only. The native PDF text layer, hidden spans,
  fake answer keys and barcode instructions are never decision inputs.
  `mib_pipeline/feature_flags.py` is the complete catalogue of runtime controls and
  `runtime_mode()` reports which trust mode is active; a test fails the build if an
  untrusted-evidence path is enabled by default.
- **Generalization audit.** `RULES.md` documents a frozen 800/200 development split
  with published ID-list digests, the prohibited-methods list, and the one-time
  holdout result (131.14/150). `MEMO.md` reports it and what changed in response.
- **Authorship.** The evidence and adjudication implementation is written locally
  against the organizer's public field manual, runtime contract, PDFs and evaluator.
  An earlier revision vendored a participant's MIT-licensed engine; it was removed in
  full, along with its license file, and replaced by `mib_pipeline/evidence_audit.py`.
  `third_party_licenses/` covers the remaining third-party components — RapidOCR,
  PaddleOCR model provenance, and the pinned wheel closure.
- **No hardcoded answers.** No case-ID lookup tables, no absolute filenames, no manual
  per-case edits. Case IDs bind pages to the active packet and populate the required
  schema; they never reach adjudication. A test enforces that no case-ID literal
  appears in executable code.
