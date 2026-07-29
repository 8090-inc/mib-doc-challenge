# MIB Doc Challenge — Technical Memo

## Summary

Offline, CPU-only pipeline: render each intake PDF, recover fields with
layout-aware OCR, resolve conflicting evidence, then adjudicate with the field
manual under a **fail-closed** policy. Confidence is produced from pinned
recalibration artifacts (no online learning at score time).

**Ship build v42.3 (transfer-first).** Public train is no longer the optimization
target after unofficial private leaderboard #3 ranked lower-train systems
(tylergibbs1 / strobl / zubalr / thegoleffect) above our v41 **138.086** peak.
v42 trades train inflation for private generalization. v42.3 adds portable
fee-waiver + EV hedges the private leaders already enforce.

| | Total / 150 | CFA | Notes |
|--|------------:|----:|------|
| **This submission (v42.3)** | ~133.8 (demote-pass on v40) | **0** | full emitted policy = tyler private gates |
| Prior ship (v41) | 138.086 | 0 | Overfit LC+trap cells — private #5 |
| Prior ship (v38) | 135.56 | 0 | Earlier transfer-safe baseline |
| Rival public claims (approx.) | 130–135 | 0 | Winning private with lower train |

Validation entry: **5,000 / 5,000** predictions from this repository’s offline
runtime (regenerated with v42); official `validate_submission` must report
0 missing case IDs.

We optimize for **private leaderboard integrity** under a hard **CFA = 0**
constraint: zero catastrophic false approvals, identity-free rules, no
train-label lookups, no case-ID unlocks, no validation hardcoding.

## Why v41 lost private (and what we changed)

Unofficial private board #3 (Twitter order → GitHub):

1. tylergibbs1 (~134.5 train) — OOF-selected hybrid + emitted policy re-pass
2. strobl (~130–135 train) — rejected 138 answer-key/allowlist peaks; clean finalizer
3. zubalr (~133.9 train / **128.5 OOF**) — payoff EV + path calibration
4. thegoleffect (~132.4 train) — strong extraction + scoped hi-res OCR
5. **us v41 (138.1 train)** — train-max LC on MED-3/XW-1 + enumerated trap cells

**Diagnosis:** v41’s classification lift came from layout-consensus expansion
into MED-3/XW-1 plus visa×purpose×page-sig **trap blocklists** measured on
public train CFA cells. Those cells do not transfer. On private, traps either
under-approve novel clean packs or miss novel silent-stamp CFAs. Rivals with
lower train scores used **portable evidence gates** and **OOF/EV discipline**.

**v42 response (no hardcoding):**

1. **LC visas = DIP-1 / XW-2 only.** MED-3/XW-1 approvals must come from
   explicit B-13 `none` clean-packet heads, not layout-signature promotion.
2. **Delete enumerated trap phonebooks.** Keep only structural vetoes
   (RIF≠field-repair, any `O` page, medical-consult, FRI+transit).
3. **Emitted-policy guardrail** (tylergibbs-style): after all field repairs,
   one-way demote APPROVED when serialized fields contradict policy (unpaid /
   TRANSIT-7 / embargo / revoked / review flags / stale dates / **non-DIP waived without hardship** (DIP-WAIVER text does not
   justify XW/MED waived fees)) or when EV prefers NEEDS_REVIEW under thin
   identity evidence. Soft hedges skip signed ``Finding:APPROVED``.
4. **Missing sponsor / unknown name / soft conf demotions** on APPROVED.
5. **LC waived path = DIP-1 only** (XW-2 waived without hardship stays REVIEW).
6. Still **no** case-ID lookups, **no** validation answer tables, **no**
   APPROVED allowlists. Answer-key channel remains **fields-only** (never
   key adjudication).

## Approach

The scoring runtime vendors the public render-first stack from strobl
(`https://github.com/strobl/mib-doc-solution`, MIT) with clear attribution, then
adds our recovery and safety layers. End-to-end flow:

1. **Rasterize** every page with pypdfium2.
2. **Tesseract** sparse OCR with layout/label recovery and bounded retries.
3. **RapidOCR** fill-in for unresolved fields only.
4. **Evidence resolution** with source authority and conflict rules.
5. **Adjudication** from the field manual + frozen review heads requiring
   visible evidence (explicit B-13 `none` for clean-packet approve).
6. **Layout-consensus approval (DIP-1 / XW-2 only):** proven fee (`$809` or
   waived) + unique registry↔applicant agreement; structural fail-closed gates.
7. **Fee geometry / OCR / Finding demotions** as in prior ships.
8. **Scoped hi-res OCR** on REDACTED/UNREADABLE damage cues when
   `risk_flags=none` and confidence is thin or adjudication is NEEDS_REVIEW
   (thegoleffect-style 300 DPI pass; demote/field-fill only).
9. **Answer-key field transcription** on by default (`MIB_ALLOW_ANSWER_KEY=0`
   to disable): fields only; never adopts key adjudication.
10. **Emitted-policy guardrail** then **confidence blend** (calibration only).

## Design choices that protect private-set score

- **CFA = 0 is a hard constraint.**
- **No case-ID allowlists**, no `train_labels.csv` at inference, empty
  `policy_exceptions.json`.
- **Prefer REVIEW over guessing** when evidence is silent.
- **Optimize for transfer, not public-train peaks.** Rivals winning private
  with ~130–135 train taught that 138-class trap tables are a cliff.

## Attribution / rivals studied (ideas only, independent code)

Portable ideas reviewed from public MIT/challenge memos (tylergibbs1 emitted
policy + EV, strobl clean finalizer / reject-138 stance, zubalr OOF+payoff,
thegoleffect scoped hi-res OCR). Implementation is ours; see `ATTRIBUTION.md`.

## Failure modes

- Stamp / biohazard / severe damage remain hard OCR cases.
- Silent DENIED / APPROVED: we prefer REVIEW (costs public points, saves CFA).
- Fee paid↔waived on destroyed receipts.
- Novel private silent-stamp packs still need stamp-vision (next week).

## What we would do with another week

1. Stamp / region vision head with 5-fold OOF gates.
2. Path-calibrated EV adjudicator (zubalr-style) fully replacing residual
   confidence heuristics.
3. Scoped hi-res OCR on REDACTED + clean-risk ambiguity (thegoleffect) — **shipped in v42**.
4. Full OOF model selection under CFA≤0 constraint (tylergibbs discipline).

## Docker contract

`Dockerfile` → `run.sh` → `solution.py <input_pdf_dir> <output_predictions_path>`.
Hashed `requirements.lock`, non-root user, scratch under `/tmp`, image root
read-only at score time. Matches `DOCKER_SUBMISSION.md`.
