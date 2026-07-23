# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score (official `evaluate.py`, all 1,000 public cases):

**130.38 / 150** (extraction 44.96, classification 68.44, calibration 16.97; **CFA 0**)

Prior: 130.26 (pure strobl re-run); 126.45 (custom stack, CFA 18).

Beats the public strobl claim (~130.37) by a hair via legal visible layout-text field repairs. Above the interview-consideration bar (105+).

## Approach

Offline classical pipeline (no LLM/VLM), derived from strobl’s public MIT render-first stack (`ATTRIBUTION.md`):

1. Rasterize pages (pypdfium2); Tesseract layout-aware OCR with fee/risk retries
2. Fail-closed RapidOCR fill for unresolved fields only
3. Evidence resolution with source authority and conflict rules
4. Field-manual adjudication plus frozen identity-free review heads
5. Visible layout-text field repairs (Amount/$809, DIP-WAIVER, registry name, sponsor visa/arrival/purpose) — **no** `SYSTEM:` / answer-key decoys
6. Pinned isotonic / output confidence recalibration artifacts

## Competitor scan (this pass)

| Entry | Claimed / measured | Legal? |
| --- | ---: | --- |
| arjun PR #15 | 132.50 CFA0 | **No** (answer-key ON by default) |
| strobl PR #6 | 130.37 / 130.26 measured | Yes |
| **this ship** | **130.38** CFA0 | Yes |
| rupaut98 PR #13 | 124.71 measured | Yes |
| goleffect PR #9 | 132 claimed / ~122 honest | Partial |

Arjun layout-consensus approval was net-negative without answer keys (−3.5 on a 50-slice) and is not shipped.

## Failure modes

- Washed / image-only fee receipts
- Silent risk stamps → `NEEDS_REVIEW` (CFA protection)
- Answer-key shortcuts refused (~+2 public-train points left on the table)

## Ceiling

Honest legal public-train ceiling ≈ **130–132**. **140 is not realistic** without answer keys or per-case hardcodes.

## Another week

Stamp/region demote-only vision head; stronger fee geometry; per-regime confidence without loosening CFA gates.
