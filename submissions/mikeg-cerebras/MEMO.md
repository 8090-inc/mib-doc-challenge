# Technical Memo - MIB Doc Challenge (mikeg-cerebras)

## Approach

This submission uses a deterministic, CPU-only PDF pipeline derived from the
MIT-licensed public Abhishek/Strobl lineage. It rasterizes each page, runs
Tesseract and RapidOCR over rendered pixels, resolves typed evidence across the
packet, applies conservative field-manual policy, and emits a calibrated
confidence. Missing or conflicting decision evidence routes to review.

The submitted branch contains no answer-key parser, raw PDF-text recovery
head, LLM, VLM, cloud OCR, or runtime network dependency. The final image is
0.55 GiB and runs under the official read-only, offline Docker contract.

## Results

On all 1,000 public training cases, the exact submitted runtime scores
**129.7994503976586 / 150**: extraction 44.86/50, classification 68.06/80,
and calibration 16.8794503976586/20, with no missing cases and one
catastrophic false approval. The measured wall-clock proxy is 1.853 seconds
per PDF on four CPUs.

The same image produced all 5,000 validation records in 2.168 seconds/PDF.
The validated JSONL SHA-256 is
`f80aa5d16f123e2ab9e447594b36a59a8cc0fa1c6ea6c6c728ba74880b3e7e73`.

## Failure modes

Severely degraded scans and packets with genuinely ambiguous visible evidence
remain the main limitations. The pipeline intentionally holds some valid
packets for review rather than infer a clean risk or fee state from weak
evidence.

## What another week would buy

More held-out robustness testing, calibration validation, and additional
image-consistency checks.

## Note to reviewers

The private solution repository and exact branch in `SUBMISSION.md` contain the
reproducible container, full provenance, hidden-key independence audit, and
experiment history. Reviewer access is available on request under the
organizer-confirmed private-repository arrangement.
