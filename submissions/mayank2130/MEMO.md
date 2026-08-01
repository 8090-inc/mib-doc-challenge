# MIB Document Challenge Technical Memo

## Summary

My submission is a fully offline, CPU-only document pipeline that extracts the
required fields from each PDF packet and applies deterministic adjudication
rules. The system combines two OCR engines, page-template classification,
field-specific normalization, evidence precedence, and conservative confidence
estimates. It is packaged as a Docker image that accepts the required input
directory and output JSONL path, uses no network services, and runs within the
published four-CPU and eight-gigabyte limits.

The final pipeline scored approximately **124.4 out of 150** on the complete
public 1,000-case training benchmark. I report this specifically as a public
training score; validation and private-test labels are not available locally.

## Document and OCR Pipeline

Each PDF page is rendered at 180 DPI using Poppler. I run Tesseract with three
page-segmentation modes: PSM 6 for dense forms, PSM 11 for isolated fields and
stamps, and PSM 1 for orientation-aware recovery. RapidOCR provides a second,
detection-based OCR view. The engines fail differently: RapidOCR often recovers
faint text that Tesseract misses, while Tesseract preserves table rows and
label/value relationships more reliably. Their outputs are combined without
allowing later OCR text to override higher-precedence visible evidence.

Pages are retained separately and classified as intake forms, biometric slips,
sponsor attestations, registry extracts, fee receipts, or adjudicator notes.
Each page is also associated with its visible case ID. This prevents paperwork
for another applicant in the same packet from contaminating the active case.

For unresolved high-value pages, the pipeline performs a selective enhanced OCR
pass. It upscales the existing render, applies CLAHE contrast normalization, and
reruns dense, sparse, and detection-based OCR. The retry is limited to damaged
fee, biometric, registry, note, or nearly empty pages instead of increasing work
for every page.

## Extraction and Evidence Resolution

Constrained fields are normalized against the public challenge vocabularies.
The extractor repairs common OCR character confusions, performs label-scoped
fuzzy matching, recognizes truncated fee values, and ranks plausible labeled
date candidates. Applicant names are reconstructed using the synthetic name
grammar. Risk recovery uses exact aliases plus carefully measured fuzzy rules;
fuzzy disqualifying-risk inference is intentionally disabled where it produced
false positives.

Evidence follows the field manual's precedence. Visible signed findings and
manual notes outrank form data. Intake evidence outranks biometric, sponsor, and
registry evidence, and the machine-readable PDF layer is only a last-resort
source. Hidden instructions and fake answer keys are never used for risk flags
or adjudication. Standalone decision stamps are accepted only on active-case
adjudicator-note pages, excluding sample, crossed-out, and rescinded decisions.

## Adjudication

The deterministic policy first applies trusted explicit decisions. It then
checks disqualifying risk flags, revoked sponsors, stale dates, transit visas,
and unpaid fees. Review-only flags, missing required fields, uncertain fee
readings, unsupported waivers, and MED-3 packets without a visible clean
biohazard result are routed to `NEEDS_REVIEW`.

A packet with no visible biometric template is also routed to review if it would
otherwise be approved. This safety gate does not invent a denial or a missing
risk flag; it represents uncertainty caused by absent evidence and reduces the
most costly false approvals. Confidence is tied to the decision path: explicit
findings and strong denial evidence receive high confidence, while inference and
missing-evidence paths receive lower values.

## Runtime and Reproducibility

The image bundles Poppler, Tesseract, RapidOCR, ONNX Runtime, and headless
OpenCV. ONNX Runtime is limited to one thread per worker, while up to four PDF
workers run concurrently. This avoids CPU oversubscription. The pipeline writes
temporary renders only under `/tmp`, supports a read-only container filesystem,
and writes the final result only to the requested output path. A targeted Docker
smoke test averaged approximately 2.95 seconds per difficult PDF.

## Known Failure Modes

The largest remaining problem is genuinely absent or visually destroyed risk
evidence. Higher-resolution OCR cannot recover a page or field that is not
present, so the system must trade false approvals against excessive review.
Heavy rotation, torn table cells, and conflicting low-quality OCR readings can
still cause incorrect fields. Applicant names and free-text purposes are more
sensitive to damage than constrained enums. Review-only conditions such as
identity conflict and sponsor mismatch are difficult to infer without creating
false flags, so several aggressive inference paths remain disabled.

## What I Would Improve With Another Week

I would train small, template-specific document models using only the public
training set: page-type and damage classifiers, calibrated crop detectors for
risk and fee regions, and an out-of-fold adjudication model over explicit
evidence features. I would also add geometric deskew and rotation estimation
before OCR, learn confidence calibration out of fold, and create a larger
versioned OCR cache for controlled ablation testing. The primary objective would
remain reducing `DENIED` cases incorrectly sent to approval or review without
relaxing evidence precedence or relying on validation-specific case IDs.
