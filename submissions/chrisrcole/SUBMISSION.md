# Submission

- Public solution repository: <https://github.com/chrisrcole/mib-doc-challenge-gibbs-cole>
- Entrypoint: `docker run <image> <input_pdf_dir> <output_predictions_path>`
- Runtime: offline CPU-only Python — RapidOCR/PP-OCRv5 ONNX, PyMuPDF, OpenCV,
  and small candidate-trained models (no LLM, VLM, or network access)

The repository includes the `Dockerfile`, full runtime source (`mib/`),
model artifacts (`models/`), attribution and licensing notes
(`ATTRIBUTION.md`, `NOTICE.md`), and a working-notes log of measured
improvements (`COLE_NOTES.md`).

This submission builds on Tyler Gibbs's prior resubmission runtime
(MIT-licensed, chain of provenance in `ATTRIBUTION.md`) and integrates
additional note-recovery, page-classification, and time-governed runtime
techniques developed by Chris Cole. See `submissions/chrisrcole/MEMO.md` for
the full technical memo and attribution breakdown.
