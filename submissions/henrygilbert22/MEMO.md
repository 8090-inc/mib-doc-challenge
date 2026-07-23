# MIB Doc Challenge — Technical Memo

**Author:** Henry Gilbert (`henrygilbert22`)  
**Solution:** offline PyMuPDF + selective Tesseract pipeline with rule-based adjudication  
**Measured train score (iter-5, official Docker harness):** 116.40 / 150 — classification 62.48, extraction 39.20, calibration 14.72, 15 catastrophic false approvals, 0.81 s/PDF, 0.46 GiB image, 1.37 GiB peak RAM. Validation score not reported (private labels).

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

**Confidence.** `confidence.py` maps evidence quality (field completeness, mean OCR confidence, native–OCR corroboration, hidden-text and contradiction penalties) onto `[0.01, 0.99]`, with reason-code caps so explicit policy denials stay high and missing-evidence reviews stay low — targeting Brier calibration (train mean Brier 0.132, 14.72 / 20 pts).

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

**Iteration 5 full train** (`eval-runs/iteration-5-full/`):

| Section | Score |
| --- | ---: |
| Total | **116.40** / 150 |
| Classification | 62.48 / 80 |
| Extraction | 39.20 / 50 |
| Calibration | 14.72 / 20 |
| Missing penalty | 0.00 |

Runtime: **806.5 s** wall, **0.807 s/PDF**, peak memory **1,365 MiB**, image **0.459 GiB**. All 1,000 train cases predicted; schema valid.

**Progression:** iter-1/2 tuned on a 60-case stratified slice (103.82 → 120.96). Full-train iter-3 baseline 114.46 (20 CFA) → iter-4 116.08 (15 CFA, selective OCR) → iter-5 116.40 (parser/adjudication hardening). Holdout 100-case eval: 116.29, 0 CFA.

**Failure modes (iter-5):**

1. **Catastrophic false approvals (15):** almost all `DENIED→APPROVED` with strong field extraction but missed disqualifying `risk_flags` (14/15 missed `risk_flags` in worst-case analysis).
2. **Fee status (~59% accuracy):** OCR/normalization on degraded fee receipts.
3. **Over-review:** 128 `APPROVED→NEEDS_REVIEW` — conservative missing-evidence and low-OCR gates.
4. **Residue denials misclassified as review:** 91 `DENIED→NEEDS_REVIEW`.

---

## Next improvements

1. **Risk-flag sensitivity:** tighten approval when biometric/adjudication pages show partial flag prose or registry `EMBARGO REVIEW` without full `Observed flags:` parse.
2. **Fee receipt channel:** expand fuzzy label patterns and second-pass OCR variants (already prototyped in bench) without full-document OCR.
3. **CFA elimination:** block `clean_packet` approval when any high-risk page type lacks explicit negative flag attestation.
4. **Calibration pass:** separate confidence curves for review vs deny reason families (counterfactual analysis showed `all_risk_none_approvals` group carries most CFA risk).
5. **Submission packaging:** open PR with validated predictions + this memo (validation complete: 5,000/5,000, 0.957 s/PDF, 0.459 GiB image, ~1.29 GiB peak; no validation score).

---

## Compliance statement

No validation labels, no per-case hardcoding, no network/API/LLM usage at runtime. Sponsor revocation list includes train-inferred IDs disclosed in source comments. Final validation complete (5,000/5,000 predictions, schema-validated); public solution-repo publication **pending Henry review**.
