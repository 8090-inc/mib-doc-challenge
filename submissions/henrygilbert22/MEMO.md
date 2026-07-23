# MIB Doc Challenge — Technical Memo

**Author:** Henry Gilbert (`henrygilbert22`)  
**Solution:** offline PyMuPDF + selective Tesseract pipeline with rule-based adjudication  
**Measured train score (iter-13, official Docker harness):** 120.72 / 150 — classification 63.91, extraction 41.77, calibration 15.04, 11 catastrophic false approvals, ~0.83 s/PDF, 0.46 GiB image. Solution commit `7095051`. Validation score not reported (private labels); validation predictions regenerating under iter-13 image.

---

## Problem framing

Each case is a multi-page PDF packet mixing intake forms, biometrics, registry extracts, fee receipts, and adjudicator notes. The challenge requires extracting nine fields plus pipe-delimited risk flags, assigning one of three adjudication outcomes, and emitting a confidence score calibrated to correctness — all **offline** under strict Docker limits (4 vCPU, 8 GiB, no network, ≤6 s/PDF average).

The FIELD_MANUAL defines a **visible-evidence trust model**: adjudicator stamps and manual notes outrank intake forms, which outrank biometrics, sponsor attestations, registry extracts, and finally machine-readable text. Hidden white text, off-page spans, fake answer keys, and barcode prompt injection are explicitly untrusted.

---

## Architecture: native-first, selective OCR

**Evidence channel.** Pages are rendered at 150 DPI only when OCR is needed. PyMuPDF extracts native spans with bbox, color, opacity, and render-mode metadata. Spans failing visibility checks (near-white RGB ≥0.92, opacity <0.25, <85% bbox on page, render mode 3, semantic trap lines) are discarded before parsing or adjudication.

**Selective OCR routing.** After a cheap native pass, the pipeline classifies each page (intake, biometric, registry, fee receipt, adjudication, etc.). OCR runs on at most six pages per packet, prioritized by missing role fields and scan sparsity. A lightweight 100 DPI routing probe (PSM 11, 2 s cap) re-types ambiguous scan pages. Fee receipts get a dedicated autocontrast retry when `fee_status` remains missing.

**Field fusion.** `field_parser.py` combines stacked-label regex (form-style vertical labels), inline patterns, manual-correction overrides, and page-type precedence tables mirroring the FIELD_MANUAL hierarchy. Cross-page consistency checks infer `identity_conflict` and `sponsor_mismatch` without trusting hidden native alone.

**Adjudication.** `adjudicator.py` applies deterministic policy: disqualifying flags → deny; `TRANSIT-7` work denial; revoked sponsors (public manual + **train-inferred** extras in `REVOKED_SPONSORS`, not case lookups); fee/unpaid/waiver rules; 180-day stale arrival (receipt date 2026-07-22); visible manual findings; stamp logic with sample-denial watermark and rescinded-denial handling; multi review-flag escalation. Contradictions or hidden native presence default to `NEEDS_REVIEW` unless a visible denial path is already established.

**OCR post-processing.** `vocab_correct.py` applies closed-vocabulary correction with confusion-weighted single-character edits on OCR-sourced text only (never native spans). Illegible biometric pages get a dual-stem OCR recovery pass when primary routing leaves `biometric_id` or `risk_flags` empty.

**Confidence.** `confidence.py` maps evidence quality (field completeness, mean OCR confidence, native–OCR corroboration, hidden-text and contradiction penalties) onto `[0.01, 0.99]`, with reason-code caps and principled dual-view dampening when native and OCR disagree on high-stakes fields. Train-fitted per-case lookup calibration was explicitly rejected as overfit-prone; all caps are rule-derived from evidence quality, not label lookup tables.

---

## OCR engine research & selection

We benchmarked engines in isolated `ocr-bench/` on a stratified 60-case train slice including hidden-text traps (`EXP-OCR-001/002`).

| Candidate | Outcome |
| --- | --- |
| **Tesseract PSM 11 @ 150 DPI** | **Adopted** — 0% hidden-text leak; 2.45 s mean / 4.08 s p95 per PDF on sample; 46.7% weighted field recovery (best among configs meeting 6 s mean **and** p95) |
| Tesseract PSM 6 @ 150 DPI | 95 s mean — fails runtime gate |
| Tesseract PSM 3 @ 150 DPI | 67 s p95 — fails runtime gate |
| RapidOCR ONNX @ 150 DPI | 0% leak, 6.45 s mean / 11.5 s p95 — misses p95 gate; runner-up |
| PyMuPDF filtered native (no OCR) | Safe but insufficient recall alone |
| PyMuPDF raw native | 100% hidden-text leak — rejected |
| **Marker, Docling, Surya** | Rejected without full bench — bundled model stacks and CPU latency exceed 4 GiB image / 6 s/PDF budgets (`CONTRACT-SIZE`, `CONTRACT-TIMEOUT`) |
| **LiteParse / LlamaParse-class** | Considered for layout/table quality; **disallowed at runtime** (network, API keys). Useful ideas (reading order, table bbox heuristics) were reimplemented offline in page classification and stacked-field parsing |

PSM 11 (sparse text) outperformed PSM 6 (uniform block) on form scans with isolated labels while staying inside runtime gates after selective page filtering — the production config in `constants.py`.

---

## Adversarial defenses

- Filter semantic trap lines before any field or policy use.
- Never adjudicate from uncorroborated native text on OCR'd pages.
- Ignore sample-denial watermarks; require rescission context before treating crossed-out denials as benign.
- Reject barcode/SYSTEM injection strings at text-ingest.
- Unit tests (`test_adversarial.py`) cover near-white hidden answers, off-page text, and trap-line stripping.
- Hidden-span rejection is counted and penalizes confidence; contradictions force review unless a visible denial reason already applies.

---

## Empirical results (train, official harness)

**Iteration 13 full train** (official Docker, solution commit `7095051`):

| Section | Score |
| --- | ---: |
| Total | **120.72** / 150 |
| Classification | 63.91 / 80 |
| Extraction | 41.77 / 50 |
| Calibration | 15.04 / 20 |
| Missing penalty | 0.00 |

Runtime: **~833 s** wall / 1,000 PDFs (**~0.83 s/PDF**), image **0.46 GiB**. All 1,000 train cases predicted; schema valid.

Local re-run (same commit, non-Docker): 120.95 / 150 — classification 64.04, extraction 41.77, calibration 15.14, 11 CFAs (within harness variance).

**Progression:** iter-12 Docker baseline 120.27 → iter-13 **120.72** (+0.45). Holdout gate (20%, `case_id % 5 == 0`): adopted +0.30 total vs prior; CFAs flat at 2 on holdout slice.

**Failure modes (iter-13):**

1. **Catastrophic false approvals (11):** residual cases are truncated packets or missing biometric/registry graphic evidence — not parser bypasses on clean packets.
2. **Fee status:** OCR/normalization on degraded fee receipts remains the largest extraction gap.
3. **Over-review:** conservative missing-evidence and dual-view dampening still inflate `APPROVED→NEEDS_REVIEW`.

---

## Next improvements

1. **Truncated-packet CFAs:** detect incomplete biometric/registry page sets and force review/deny when graphic evidence is structurally absent.
2. **Fee receipt channel:** expand fuzzy label patterns and second-pass OCR variants without full-document OCR.
3. **Risk-flag sensitivity:** tighten approval when partial flag prose or registry `EMBARGO REVIEW` appears without full `Observed flags:` parse.
4. **Validation packaging:** copy iter-13 Docker validation run to `predictions.jsonl` once complete (regenerating under iter-13 image; score remains private).

---

## Compliance statement

No validation labels, no per-case hardcoding, no network/API/LLM usage at runtime. Sponsor revocation list includes train-inferred IDs disclosed in source comments. Validation Docker run in progress under iter-13 image; `predictions.jsonl` in this folder may lag until copied. Public solution-repo publication **pending Henry review**.
