# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score  
**125.25 / 150** (extraction 43.15, classification 66.64, calibration 15.46; CFA 18)  
Prior: 124.31 / 150; 124.13 (isotonic); 123.39 (CFA 27); visible_core 122.36  
Above the published interview-consideration bar (105+)  
130 not reached. Fee gating + crop recovered 21 UNKNOWN→paid/waived (19 correct). ~377 fees still UNKNOWN on washed receipts. Silent-stamp CFAs remain: many lack any recoverable stamp pixels/text (labels disagree with visible PDF). No answer-key / mode-default leakage.

## Approach

Classical offline pipeline (no LLM): trusted `pdftotext` (drop `SYSTEM:` decoy lines), render-first Tesseract OCR (`visible_core`), dual recovery for residual gaps — hi-res Tess fee-crop ensemble (autocontrast / invert / contrast / dual-threshold ×2 upscale) + fail-closed RapidOCR (UNKNOWN/empty only), **injection-stripped fee/bio page gating** (SYSTEM answer-key overlays no longer inflate native length and hide sparse fee rasters), fuzzy Observed-flags value matching, mystery-sparse silent-stamp demotion, gated fee promote, identity-free confidence strata + isotonic recalibration.

## Failure modes

- Image-only / washed fee receipts → UNKNOWN fee → review (OCR rarely recovers Amount; remaining ~326 recoverable misses show 0/20 Rapid hits).
- Silent risk stamps with no OCR/CV text on clean labeled packets → residual CFA; red/blue ink detectors do not separate CFA from true approvals without large collateral.
- `MIB_STRICT_FLAGS` / no-B13 bar nets negative class unless fee+panel OCR matches strobl (~42/50 fee on holdout slice vs our ~29/50).
- Prefer `NEEDS_REVIEW` on thin evidence; never trust hidden answer keys.
