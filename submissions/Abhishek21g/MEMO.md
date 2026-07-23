# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score  
**126.45 / 150** (extraction 44.35, classification 66.64, calibration 15.46; CFA 18)  
Prior: 125.25 / 150; 124.31 / 150; 124.13 (isotonic); 123.39 (CFA 27); visible_core 122.36  
Above the published interview-consideration bar (105+)  
130 not reached. Strobl public train claim ~130.37; goleffect claimed 132 depends on answer-key path (honest ~122).

## Approach

Classical offline pipeline (no LLM): trusted `pdftotext` (drop `SYSTEM:` decoy lines), render-first Tesseract OCR (`visible_core`), dual recovery for residual gaps — hi-res Tess fee-crop ensemble (autocontrast / invert / contrast / dual-threshold ×2 + strobl top-30% thresholds 120/140/160/180 PSM 11) + fail-closed RapidOCR (UNKNOWN/empty only), **injection-stripped fee/bio page gating**, fuzzy Observed-flags value matching, mystery-sparse silent-stamp demotion, gated fee promote, identity-free confidence strata + isotonic recalibration.

**Serialization priors (strobl port, identity-free):** after adjudication + confidence, unresolved scored fields are filled with public-train mode priors (`fee_status→paid`, `visa_class→MED-3`, `species_code→TRIANGULAN`, `home_world→Wolf-1061c`, `declared_purpose→reactor maintenance`). Policy still fail-closes on missing fee (NEEDS_REVIEW); only the scored JSONL row is filled. No case-ID hardcodes; no `SYSTEM:` / answer-key leakage.

## Failure modes

- Image-only / washed fee receipts → many still unreadable to Tess/Rapid; prior recovers the paid majority but waived/unpaid unknowns stay wrong on extraction.
- Silent risk stamps with no OCR/CV text on clean labeled packets → residual CFA 18; red/blue ink and blanket no-panel demotion net negative on full train.
- Fee+flags label oracle ~131; honest legal ceiling likely ~130–132 with strobl-class dual OCR + review heads. **140 is not realistic legally** without answer keys or per-case hardcodes.
- Prefer `NEEDS_REVIEW` on thin evidence; never trust hidden answer keys.

## Competitor ports (legal only)

| Source | Ported |
| --- | --- |
| strobl PR #6 | Fee crop thresholds, paid OCR repair `[pnm][ao][i1l][dcl]`, output-only field priors, dual Rapid idea |
| thegoleffect PR #9 | Render-first OCR, stratum confidence; **rejected** answer-key / mode-default leakage path |
| dw820 PR #10 | Gated orientation RapidOCR |

## Next week

Stronger bio-panel OCR for `illegible_biometrics` / silent stamps; strobl review-recovery heads; confidence map refit after fee prior; selective CFA demotion only when EV+ on full train.
