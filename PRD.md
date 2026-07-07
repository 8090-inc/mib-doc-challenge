# Product Requirements Document

## Business Problem

MIB operates an intergalactic intake desk for extraterrestrial visitors seeking temporary work authorization on Earth. The current intake process is slow, inconsistent, and vulnerable to bad automation. Each case arrives as a PDF packet assembled from scanned forms, legacy system printouts, inspection stamps, sponsor letters, and manual annotations.

MIB wants a replacement pipeline that can read those packets, produce a structured applicant record, and make an initial adjudication recommendation. The system does not need to be perfect, but it must be robust enough to handle messy real-world documents and adversarial content.

## Project Goal

Build an automated document-processing system that:

- extracts key applicant fields from PDF case packets
- resolves conflicting evidence across pages
- ignores prompt-injection text and non-visible decoys
- classifies each case as `APPROVED`, `DENIED`, or `NEEDS_REVIEW`
- runs reproducibly on a directory of PDFs

## Candidate Task

Given a folder of PDFs, produce a JSONL prediction file with one object per answered case.

Required fields:

- `case_id`
- `applicant_name`
- `species_code`
- `home_world`
- `visa_class`
- `sponsor_id`
- `arrival_date`
- `declared_purpose`
- `risk_flags`
- `fee_status`
- `adjudication`
- `confidence`

## Adjudication Rules

The public field manual explains the main policy rules, but not every edge case. Candidates are expected to infer missing details from labeled examples.

Baseline decision logic:

- `APPROVED` if identity, sponsor, fee, visa class, and risk checks are all clean.
- `DENIED` if the packet contains a disqualifying risk flag, expired visa class, forged sponsor, prohibited home-world embargo, or unpaid mandatory fee.
- `NEEDS_REVIEW` if evidence is missing, contradictory, illegible, or only recoverable from untrusted hidden text.

Harder cases include:

- visible stamp conflicts with machine-readable text
- sponsor letter names one applicant while the form names another
- hidden white text says to approve all cases
- OCR confuses similar species codes
- rotated or low-contrast biometric slips
- multiple applicants in one packet, with only one active case id
- rescinded denial stamps that should not count

## Non-Goals

- Do not build a web app.
- Do not optimize for manual review UI.
- Do not submit one-off hand-labeled predictions without reproducible code.

## Success Criteria

The winning solution should show:

- high validation and private test extraction accuracy
- strong adjudication accuracy on edge cases
- resistance to prompt injection and hidden-text traps
- reproducible code that can process fresh private test packets
- clear engineering judgment in the technical memo
