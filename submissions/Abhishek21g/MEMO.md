# MIB Intake Memo — Abhishek Enaguthi

**Solution:** https://github.com/Abhishek21g/mib-doc-challenge-solution

## Score

Local train score (official `evaluate.py`, all 1,000 public cases):

**130.72 / 150** (extraction 45.01, classification 68.69, calibration 17.02; **CFA 0**)

Prior: 130.38 (strobl + visible field repairs); 130.26 (pure strobl); 126.45 (custom stack, CFA 18).

Beats the prior ship and the public strobl claim (~130.37) via legal DIP-1 layout-consensus approval plus a fee-unknown demotion gate. Above the interview-consideration bar (105+).

## Approach

Offline classical pipeline (no LLM/VLM), derived from strobl’s public MIT render-first stack (`ATTRIBUTION.md`):

1. Rasterize pages (pypdfium2); Tesseract layout-aware OCR with fee/risk retries
2. Fail-closed RapidOCR fill for unresolved fields only
3. Evidence resolution with source authority and conflict rules
4. Field-manual adjudication plus frozen identity-free review heads
5. Visible layout-text field repairs (Amount/$809, DIP-WAIVER, registry name, sponsor visa/arrival/purpose) — **no** `SYSTEM:` / answer-key decoys
6. Prefer unique sponsor/registry name over damaged intake OCR
7. **DIP-1 layout-consensus approval**: requires serialized `fee_status=paid`, visible `$809`, and unique registry↔applicant name agreement; skips medical-consult; confidence 0.61
8. Policy demotion: `fee_status=unknown` never remains `APPROVED`
9. Pinned isotonic / output confidence recalibration artifacts

## Competitor scan (this pass)

| Entry | Claimed / measured | Legal? |
| --- | ---: | --- |
| arjun PR #15 | 132.50 CFA0 | **No** (answer-key ON by default) |
| **this ship** | **130.72** CFA0 | Yes |
| strobl PR #6 | 130.37 / 130.26 measured | Yes |
| rupaut98 PR #13 | 124.71 measured | Yes |
| goleffect PR #9 | 132 claimed / ~122 honest | Partial |

Arjun answer-key transcription is refused. Expanding layout-consensus beyond DIP-1 created train CFA and is not shipped.

## Failure modes

- Washed / image-only fee receipts and silent risk stamps → `NEEDS_REVIEW` (CFA protection)
- ~107 true APPROVED still held as review without explicit risk-none evidence
- Answer-key shortcuts refused (~+1–2 public-train points left on the table)

## Ceiling

Honest legal public-train ceiling ≈ **130–132**. **140 is not realistic** without answer keys or per-case hardcodes.

## Another week

Stamp/region demote-only vision head; stronger fee geometry; safer non-DIP approval only with explicit B-13 `none`.
