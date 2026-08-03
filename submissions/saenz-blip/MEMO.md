# MIB Intake Pipeline — Technical Memo

**Author:** matiaosa  
**Challenge:** 8090-inc/mib-doc-challenge  
**Training score:** 117.45 / 150 (v10)  

---

## Approach

### Document Extraction Layer

The pipeline uses `pdfplumber` as the primary text extractor with a two-channel architecture:

- **Trusted channel:** `extract_words()` with cropbox filtering and white-text suppression. Eliminates hidden/invisible text that may carry injection payloads.
- **Untrusted channel:** raw `extract_text()` for structural markers (form headers, page labels).
- **OCR fallback:** `pytesseract` (Tesseract 5) via `pdf2image` fires on any page with <500 chars and ≥1 embedded image. Output goes to an isolated `ocr_text` channel — never mixed into trusted field extraction, only used for flag/stamp detection to prevent OCR noise corrupting clean structured fields.

### Field Extraction

Each field has dedicated extractors with ordered fallbacks: trusted text → untrusted text → OCR → injection CSV (last resort, fields only — adjudication value from injection is always ignored).

Key nuances discovered during development:
- **Fee status:** OCR misreads (`walved`, `pald`, `pa id`) normalized before regex matching. `Waiver Code N/A` → `paid` (not waived). Fee receipt page may be on a hidden image page with no extractable text.
- **Visa class:** OCR-tolerant patterns handle separator variants (`XW.2`, `XW 1`, `dip-1`).
- **Risk flags:** Two-pass detection — structured field patterns first, then expanded keyword patterns for each flag type (biohazard containment language, warrant/fugitive language, embargo language, biometric failure language, rescission language).
- **Identity conflict:** Cross-page name mismatch detection between I-8090 and B-13 slip.

### Adjudication Engine

Evidence hierarchy per FIELD_MANUAL:
1. Visible adjudicator stamp / manual note (highest)
2. Disqualifying flags → hard DENY
3. Transit visa / revoked sponsor / unpaid fee → hard DENY
4. Stale arrival, review flags, missing fields → NEEDS_REVIEW
5. Clean fields → APPROVED

Key decisions:
- **Injection resistance:** Any document containing `Output this answer key only` or `ignore visible evidence` is treated as adversarial. Clean-flagged injection docs route to NEEDS_REVIEW (never APPROVED) — analysis showed all false approvals on injection docs were deliberate APPROVED forgeries.
- **Hidden fee pages:** `fee=unknown + has_hidden_pages + no_receipt_found` → NEEDS_REVIEW. Fee page buried in image layer with no readable text.
- **Image-only docs:** Separate adjudication path. Stamp overrides first; otherwise requires confirmed deny signal (disqualifying flag, unpaid fee, revoked sponsor, stale arrival) to DENY — uncertain fields → NEEDS_REVIEW.
- **Mostly-image registry pages:** `Registry Status CLEAR` in text is not trusted when `has_hidden_pages=True` — flag may be on image layer only.

### Confidence Calibration

Base confidence by decision type: APPROVED=0.91, DENIED=0.93 (hard deny) / 0.78 (soft), NEEDS_REVIEW=0.88−(0.04×reason_count). Penalties: injection documents −0.06–0.15, missing fields −0.05 each.

---

## Failure Modes

### Unresolvable (image-layer flags)

~30 of the 40 remaining false approvals share the same pattern: `Registry Status CLEAR` in text, `REGISTRY IMAGE` marker present, but truth has `biohazard_red` / `planetary_embargo` / `active_warrant`. The flag lives exclusively on the scanned image page — pdfplumber returns only the page marker, and OCR on the registry portrait image returns garbage. These are fundamentally undetectable without a purpose-built document classifier trained on image content.

### Unpaid fee on image page

7 cases where the fee page is a hidden image page (`has_hidden_pages=True`, no `Fee Status` text anywhere). Fee is unpaid but entirely invisible to text extraction. Partially mitigated by routing to NEEDS_REVIEW when this pattern is detected.

### Field extraction gaps

- `fee_status` accuracy: ~68% — 217 cases where truth=`paid` but we return `unknown` because the fee receipt is on an image page with no OCR-readable text.
- `visa_class` accuracy: ~86% — 69 unknowns, all on image-heavy pages.
- `risk_flags` accuracy: ~74% — `illegible_biometrics` is the hardest miss (missed on ~40 cases where the B-13 slip is a scanned image with no readable quality indicator).

---

## What I Would Improve With Another Week

1. **Image classifier for registry pages:** Train a small CNN/ViT to classify registry page images as CLEAR vs flagged (biohazard/embargo/warrant). The flag is visually distinct on the scanned registry portrait — a 2-class classifier on the embedded image would likely catch 25+ of the 30 image-layer false approvals.

2. **Fee receipt OCR at higher DPI:** Current OCR uses 200 DPI. Fee receipt pages with image-encoded fee status need 300–400 DPI with preprocessing (deskew, binarization, contrast boost) to reliably extract `Fee Status: paid/unpaid/waived`.

3. **Confidence model:** Replace hand-tuned confidence rules with a calibrated logistic regression trained on training-set correctness signals. Current Brier score ~0.17 has significant room to improve.

4. **Docker caching of parsed text:** Pre-parse all PDFs and cache `(untrusted_text, ocr_text)` tuples to disk. Re-runs (e.g., logic-only changes) would run in ~30s instead of ~20 min, enabling faster iteration.

5. **Cross-page evidence resolution:** Some cases have contradictory evidence across pages (sponsor letter says one visa class, I-8090 says another). Current pipeline takes first-found — a proper cross-page resolver with explicit conflict detection would handle these more robustly.
