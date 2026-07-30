# Technical Memo - MIB Doc Challenge

## Approach

Deterministic CPU-only PDF pipeline:

1. PDFium rendering
2. Tesseract plus bounded RapidOCR recovery
3. typed case/applicant linkage and document precedence
4. deterministic field policy and frozen calibration
5. trace-aware denial softening
6. audited native-layout consensus

Native fields must agree with protected rendered outputs. Separate rendered
OCR confirms page type, case scope, identities, registry status, and exact fee
semantics. Unknown, duplicate, low-confidence, conflicting, adverse,
foreign-case, or non-core evidence abstains. Raw native facts can veto but
cannot unlock approval.

No answer-key parser, case/hash/output lookup, LLM, VLM, cloud OCR, or runtime
network dependency exists.

## Results

Exact 1,000-case Docker replay:

- score: `133.06873906125762/150`
- extraction: `44.86/50`
- classification: `71.33/80`
- calibration: `16.87873906125761/20`
- CFA: `1`
- coverage: `1,000/1,000`
- runtime: `2237.18` seconds
- prediction SHA-256:
  `99cb6e81366b8efb8a99a6bca298cf79d112fba5b22027917413cb07eec8117b`

The V5 stage changes 54 train reviews to approvals; all 54 are correct.

Validation overlay:

- rows: `5,000`
- eligible/rendered: `961`
- changes: `157` reviews to approvals
- failures: `0`
- runtime: `1007.48` seconds
- SHA-256:
  `e8da6488fbbfeaa145829f1466e6b5311fc400842f7f5f3ccc1468e01ad18881`

Organizer validation reports zero missing IDs.

## Failure Modes

Degraded identity, registry, and fee rows abstain. Four clean train approvals
remain review because rendered OCR confidence or spelling fails exact V5
confirmation.

## Provenance

Private solution repository contains source, exact image, hostile tests,
research branches, independent audits, and runtime receipts. Reviewer access
is available under the organizer-confirmed private-repository arrangement.
