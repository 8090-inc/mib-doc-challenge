# Technical Memo - MIB Doc Challenge (mikeg-cerebras)

## Approach

This submission uses a deterministic, CPU-only PDF pipeline derived from the
MIT-licensed public Abhishek/Strobl lineage. It rasterizes each page, runs
Tesseract and RapidOCR over rendered pixels, resolves typed evidence across the
packet, applies conservative field-manual policy, and emits a calibrated
confidence. Missing or conflicting decision evidence routes to review. A final
checksum-pinned Jeffreys calibration changes confidence only when emitted
`fee_status` is literal `unknown` and adjudication is `NEEDS_REVIEW`. An outer
trace-aware stage then softens three narrow denial states to review unless
current-case, rendered-pixel evidence contains an authoritative visible
`Finding: DENIED`.

The submitted branch contains no answer-key parser, raw PDF-text recovery
head, LLM, VLM, cloud OCR, or runtime network dependency. The final image is
0.55 GiB and runs under the official read-only, offline Docker contract.

## Results

On all 1,000 public training cases, the exact promoted runtime scores
**129.88963483899036 / 150**: extraction 44.86/50, classification 68.09/80,
and calibration 16.93963483899035/20, with no missing cases and one
catastrophic false approval. Relative to the protected calibrated base, the
outer stage changes exactly three adjudications from `DENIED` to
`NEEDS_REVIEW`, changes no confidence or extraction value, and gains
0.025525618881403034 total points. The measured full-runtime wall clock is
2.514 seconds per PDF on four CPUs.

For validation, the existing 5,000-row artifact was used without labels to
enumerate the 18 output-eligible rows. The protected image reproduced those
rows byte-for-byte before the exact promotion image ran on the same PDFs.
The merged artifact preserves all IDs, schema, order, confidence, and
extraction values while changing 16 adjudications from `DENIED` to
`NEEDS_REVIEW`. Its SHA-256 is
`36232106f99a5ad5fea2083e93f441745e6e277669265a377205e98140eb1b17`.

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
