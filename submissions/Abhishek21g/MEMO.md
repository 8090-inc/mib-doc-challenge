# Technical Memo — MIB Offline Intake Pipeline

**Author:** Abhishek Enaguthi  
**Solution repo:** https://github.com/Abhishek21g/mib-doc-challenge-solution  
**Train score (local `evaluate.py`):** **123.39 / 150**  
(extraction **42.33**, classification **65.80**, calibration **15.26**; CFA **27**)

Prior on the same harness: 113.7 → 118.47 → 122.36 → **123.39**.

## Approach

Classical document engineering (no LLM), Centauri-I offline contract.

1. **Trusted text pass.** `pdftotext` / layout text; drops `SYSTEM:` / answer-key decoy lines while retaining the rest of the page (decoys often share fee/intake evidence).

2. **Render-first OCR (`visible_core`).** Every page rasterized (~150 DPI via pdftoppm) + Tesseract PSM 3+11 (goleffect/strobl idea, clean-room). Candidate merge by document role. **RapidOCR (ONNX)** in Docker is fail-closed: fills still-unknown fee / missing flags panel only (`MIB_NO_RAPID=1` disables).

3. **Fee recovery.** `Amount`/`$809` → paid with **FORM I-8090 excluded**; DIP waiver / `$0.00` → waived; OCR debris map for Fee Status; authoritative unpaid narratives. No mode-default fill for missing fees.

4. **Evidence precedence.** Manual findings override forms. Native intake outranks OCR. Closed-vocab fuzzy + `NAME_PARTS`; sponsor digit OCR; `2028`→`2026` date repair.

5. **Adjudication.** Field-manual tree; damage → weak review; optional `MIB_STRICT_FLAGS=1` visible-risk bar (default off — full demotion nets negative on public train); review→approve recovery when flags panel was observed and the packet is clean.

6. **Confidence.** Frozen identity-free strata (`decision×fee×visa×flags×completeness`) fitted on public train — not case-ID keys, not OCR self-scores.

## Competitor context (honest)

| Entry | Claimed / measured | Notes |
| --- | ---: | --- |
| thegoleffect | 132.44 claim | `SYSTEM:` answer-key fallback + mode defaults — we refuse |
| strobl | 130.37 claim; 0 CFA | Dual RapidOCR + visible-risk bar + isotonic calib |
| afifi | 117.73 | Hygiene only |
| **Ours** | **123.39** | `visible_core` + strata cal; no answer keys |

**130 not reached.** Oracle fee+flags re-adjudicate ≈131: binding gap remains ~268 paid fees still UNKNOWN (often image-only receipts neither Tess nor quick Rapid reads) and silent biohazard/warrant/memory stamps (25/27 CFAs). Strict flags bar kills CFA but costs more true approvals than it returns (~118). Hitting 130 needs strobl-scale dual-OCR wall-time + stamp CV — not answer-key leakage.

## Failure modes

- Silent risk stamps with zero OCR text → residual CFAs if missing panel is treated as `none`.
- Illegible / redacted fee scans: unknown → review.
- Calibration 15.3 vs strobl ~17: strata help; full isotonic still short without better decisions.

## Engineering judgment

Prefer `NEEDS_REVIEW` when evidence is thin; never trust hidden answer keys. One Dockerfile, offline, no network. Shipping current best (**123.39**) while dual-OCR / stamp work continues toward 130.
