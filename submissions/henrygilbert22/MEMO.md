# MIB Doc Challenge — Technical Memo

**Author:** Henry Gilbert (`henrygilbert22`)  
**Solution commit:** `81d46d1` (Docker train scored on `215bc56`; later commits are polish/import-structure only — same pipeline behavior)  
**Official Docker train (iter-15):** 121.18 / 150 — classification 64.10, extraction 42.00, calibration 15.08, 11 CFAs  
**Image / throughput:** 0.46 GiB, ~0.83–1.1 s/PDF (train with embedded-image OCR ~1.1 s/PDF)  
**Validation:** 5,000 / 5,000 under iter-15 image (`predictions.jsonl`); score not reported (private labels)

---

## Problem

Each case is a multi-page PDF: intake forms, biometrics, registry extracts, fee receipts, adjudicator notes. Output nine fields, pipe-delimited risk flags, one adjudication outcome, and a confidence score — all offline (4 vCPU, 8 GiB, no network, ≤6 s/PDF mean).

The FIELD_MANUAL defines visible-evidence precedence: adjudicator stamps and manual notes beat intake, which beats biometrics, sponsor attestations, registry, then machine text. Hidden white text, off-page spans, fake keys, and barcode injection are untrusted.

---

## Pipeline

1. **Native extract** — PyMuPDF spans with bbox, color, opacity, render mode. Drop near-white (RGB ≥0.92), low opacity (<0.25), off-page (<85% bbox), render-mode-3, and semantic trap lines before parsing or policy.

2. **Selective OCR** — Page-type routing after a cheap native pass. Tesseract PSM 11 @ 150 DPI on at most six pages per packet, prioritized by missing role fields and scan sparsity. 100 DPI routing probe (PSM 11, 2 s cap) for ambiguous scans. Fee receipts get autocontrast retry when `fee_status` stays empty.

3. **Embedded-image OCR** — Separate pass on passport/registry raster blocks when visa class (TRANSIT-7) or species/home-world remain unknown after page OCR. Targets graphic-only fields, not full-document OCR.

4. **Field fusion** — Stacked-label regex, inline patterns, manual-correction overrides, page-type precedence from the FIELD_MANUAL. Cross-page checks infer `identity_conflict` and `sponsor_mismatch`.

5. **Closed-vocab correction** — `vocab_correct.py`: confusion-weighted single-character edits on OCR text only; native spans untouched.

6. **Adjudication** — Deterministic rules in `adjudicator.py`: disqualifying flags → deny; TRANSIT-7 work denial; revoked sponsors; fee/unpaid/waiver; 180-day stale arrival (receipt 2026-07-22); visible manual findings; stamp logic (sample-denial watermark, rescinded denial); multi review-flag escalation. Contradictions or hidden native → `NEEDS_REVIEW` unless a visible denial path exists.

7. **Confidence** — Heuristic in `confidence.py`: field completeness, mean OCR confidence, native–OCR corroboration, hidden-text and contradiction penalties, reason-code caps, dual-view dampening when native and OCR disagree on high-stakes fields. Mapped to `[0.01, 0.99]`. No train-fitted lookup table.

Serialization-only fee and categorical imputation fills missing report fields in the output JSONL but does not feed adjudication, which always uses extracted evidence values.

**OCR engine:** Tesseract PSM 11 @ 150 DPI (0% hidden-text leak on bench slice, inside 6 s mean/p95 after selective routing). RapidOCR runner-up but p95 >6 s. Marker/Docling/Surya rejected on image size and CPU latency. Raw PyMuPDF native rejected (100% hidden-text leak).

---

## Rejected (and why)

| Idea | Why not |
| --- | --- |
| Train-fitted lookup calibrator | Per-case confidence caps from public labels; overfit on re-score |
| Fee imputation driving adjudication | Train lookup on `(visa, fee, risk_evidence)` tuples; adjudication must use extracted evidence, not imputed fee |
| Page-presence CFA gates (e.g. no biometric page → force review) | Fixes ~5/11 CFAs on train but flips ~14 truth-APPROVED packets; net −0.4 classification pts |
| ARCHIVE overlay (COPY/FILED/ARCHIVE + lone `7` → TRANSIT-7) | Fires on one train case (MIB-000865); case-specific hack |
| Full-document OCR / heavyweight layout models | Contract size and latency |

---

## Results (train, official Docker harness)

| Section | Score |
| --- | ---: |
| Total | **121.18** / 150 |
| Classification | 64.10 / 80 |
| Extraction | 42.00 / 50 |
| Calibration | 15.08 / 20 |
| CFAs | 11 |

Local re-run (same commit, non-Docker): 121.34 / 150 — harness variance, same 11 CFAs.

**Climb:** iter-12 Docker 120.27 → iter-15 121.18 (+0.91). Changes were holdout-gated where applicable; CFAs held at 11.

**Residual CFAs (11):** Mostly truncated packets missing biometric/registry graphic pages, or disqualifying flags present in truth but not in visible registry/OCR text. Not parser bypasses on complete packets. Example: MIB-000865 has biometrics but TRANSIT-7 misread — not fixable by page-count gates.

**Other gaps:** Degraded fee-receipt OCR; conservative missing-evidence and dual-view dampening still push `APPROVED → NEEDS_REVIEW`.

---

## Compliance

No validation labels, no per-case hardcoding, no network/API/LLM at runtime. Sponsor revocation list includes train-inferred IDs (commented in source). Public solution-repo URL pending review.
