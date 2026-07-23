# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score  
**124.31 / 150** (extraction 42.50, classification 66.35, calibration 15.47; CFA 18)  
Prior: 124.13 / 150 (isotonic calib +0.18); 123.39 (CFA 27); visible_core 122.36; earlier 118.47 → 113.7  
Above the published interview-consideration bar (105+)  
Validation predictions: fee-crop + mystery demotion + isotonic (Rapid off). 130 not reached: ~398 fees still UNKNOWN on washed-out image receipts; silent raster stamps still drive residual CFA. No answer-key / mode-default leakage.

## Approach

Classical offline pipeline (no LLM): trusted `pdftotext` (drop `SYSTEM:` decoy lines), render-first Tesseract OCR (`visible_core`), dual recovery for residual gaps — hi-res Tess fee-crop ensemble + fail-closed RapidOCR (strobl-style, UNKNOWN/empty only), fuzzy Observed-flags value matching, mystery-sparse silent-stamp demotion (APPROVED→REVIEW when unlabeled image pages exist and no flags panel), gated fee promote (fee fill alone cannot approve without flags panel / explicit finding), identity-free confidence strata + isotonic recalibration.

## Failure modes

- Image-only / washed fee receipts → UNKNOWN fee → review (OCR rarely recovers Amount).
- Silent risk stamps with no OCR/CV text → residual CFA after selective demotion.
- Prefer `NEEDS_REVIEW` on thin evidence; never trust hidden answer keys.
