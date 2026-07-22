# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score  
123.39 / 150 (extraction 42.33, classification 65.80, calibration 15.26; CFA 27)  
Prior visible_core ship: 122.36 / 150; earlier baselines 118.47 → 113.7  
Above the published interview-consideration bar (105+)  
130 not reached this pass: binding gap is unread fee receipts (~268 paid still UNKNOWN) and silent biohazard/warrant/memory stamps (25/27 CFAs). No answer-key / mode-default leakage.

## Approach

Classical offline pipeline (no LLM): trusted `pdftotext` (drop `SYSTEM:` decoy lines), render-first Tesseract OCR (`visible_core`), optional fail-closed RapidOCR for residual fees/flags, field-manual adjudication, identity-free confidence strata. Manual findings override forms; no mode-default fee fill.

## Failure modes

- Image-only fee receipts → UNKNOWN fee → review.
- Silent risk stamps with no OCR text → residual CFA when flags panel is missing.
- Prefer `NEEDS_REVIEW` on thin evidence; never trust hidden answer keys.
