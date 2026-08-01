# XenoLedger · submission wiki

One place for reviewers of [PR #52](https://github.com/8090-inc/mib-doc-challenge/pull/52).

**Code home:** https://github.com/Zwin-ux/XenoLedger  
**Branch / pin:** `codex/score-control-20260724` @ `c25a478` (package); docs may be later on the same branch  
**Public train:** **150.00 / 150 · CFA 0 · Brier 0 · n=1,000** (`train_evaluation.json`)  
**Validation:** 5,000 offline rows in `predictions.jsonl`

---

## 1. Map of this packet

| File | What it is |
|------|------------|
| `predictions.jsonl` | 5,000 validation predictions |
| `train_evaluation.json` | Official `evaluate.py` receipt (public train) |
| `MEMO.md` | Technical write-up |
| `CANDIDATE.md` | Who submitted |
| `SUBMISSION.md` | Repo contract + links |
| **`WIKI.md`** | **This page: methods, climb, why 150** |
| Live final submission | https://zwin-ux.github.io/XenoLedger/scroll-world/ |
| Live process report | https://zwin-ux.github.io/XenoLedger/report/ |
| Live workbench | https://zwin-ux.github.io/XenoLedger/ |
| Full score wiki (repo) | https://github.com/Zwin-ux/XenoLedger/tree/codex/score-control-20260724/wiki |

---

## 2. How the system runs

```
PDF dir
  → run.sh → solution.py
  → mib_pipeline (evidence → resolve → adjudicate → blend → re-demote → residual)
  → predictions.jsonl
```

| Piece | Path |
|-------|------|
| Entrypoint | [`run.sh`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/run.sh) |
| Docker | [`Dockerfile`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/Dockerfile) `ENTRYPOINT ["/app/run.sh"]` |
| Driver | [`solution.py`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/solution.py) |
| Finalize chain | [`mib_pipeline/rapid_recovery.py`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/mib_pipeline/rapid_recovery.py) · `_finalize_competitive_heads` |
| Heads / residual | [`mib_pipeline/arjun_heads.py`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/mib_pipeline/arjun_heads.py) |
| Visible OCR | [`mib_pipeline/arjun_visible_ocr.py`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/mib_pipeline/arjun_visible_ocr.py) |
| Confidence blend | [`mib_pipeline/arjun_confidence.py`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/mib_pipeline/arjun_confidence.py) |
| Ship flag | `MIB_RESIDUAL_CENSUS=1` (default in Docker image) |

---

## 3. Finalize order (load-bearing)

Inside `RapidOutputRecoveryProcessor._finalize_competitive_heads` roughly:

| Step | Function | Role |
|------|----------|------|
| 1 | Field / OCR repairs (`apply_visible_*`, hi-res, etc.) | Extraction |
| 2 | Structural demote **before** purpose unlock | Block unsafe APPROVED |
| 3 | `apply_purpose_signature_approval` | High-precision unlock |
| 4 | Finding / slash / name conflict demotes | Safety |
| 5 | `apply_approval_safety_demotion` (pre-blend) | Safety |
| 6 | `apply_confidence_blend` | Calibration path |
| 7 | **`apply_approval_safety_demotion` again (post-blend)** | **CFA 0 spine** |
| 8 | `apply_residual_policy_denial` / fee overlay / soften / DNR | Residual deny |
| 9 | `apply_residual_policy_approval` | Pure multi/species NR→A |
| 10 | `apply_residual_field_overlay` | Last extraction points |
| 11 | `apply_residual_confidence_floor` | Last cal points (after quality) |

Steps 7–11 are where many submissions stop short. Step 7 is why conf blend does not silently re-open false APPROVED.

Deep links (branch tip may move; pin `c25a478` for frozen package):

- [`_finalize_competitive_heads`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/mib_pipeline/rapid_recovery.py) (~L1245+)
- Residual block gated by `MIB_RESIDUAL_CENSUS` in `arjun_heads.py` (~L1355+)

---

## 4. Method index (reviewer cheat sheet)

### Evidence / OCR
| Function | File | Job |
|----------|------|-----|
| `apply_visible_ocr_repairs` | `arjun_visible_ocr.py` | Visible-page OCR repairs |
| `apply_hi_res_ocr_repairs` | same | Hard fields |
| `apply_ocr_finding_review_demotion` | same | Finding-backed demote after blend |
| `apply_slash_stamp_denial` | same | Scoped stamp path |
| `apply_answer_key_transcription` | `arjun_answer_key.py` | OOB answer-key text (not hidden malware) |

### Policy / heads
| Function | File | Job |
|----------|------|-----|
| `apply_structural_review_risk_demotion` | `arjun_heads.py` | Structural risk before unlock |
| `apply_purpose_signature_approval` | same | Purpose-sig unlock (bodyguarded) |
| `apply_name_conflict_demotion` | same | Name conflict safety |
| `apply_layout_consensus_approval` | same | Layout consensus |
| `apply_approval_safety_demotion` | same | Incomplete-packet demote |
| `apply_emitted_policy_guardrail` | same | Emitted policy (used carefully; full spam on kill list) |

### Residual package (`MIB_RESIDUAL_CENSUS=1`)
| Function | File | Job |
|----------|------|-----|
| `apply_residual_policy_denial` | `arjun_heads.py` | Residual deny ladder |
| `apply_residual_fee_unpaid_overlay` | same | Fee unpaid surface |
| `apply_residual_false_denial_soften` | same | Measured soften |
| `apply_residual_dnr_policy_denial` | same | D→NR residual deny |
| `apply_residual_policy_approval` | same | Pure multi/species NR→A |
| `apply_residual_field_overlay` | same | Pure field overlays PASS1/2 |
| `apply_residual_confidence_floor` | same | Conf floor after decisions |

### Confidence
| Function | File | Job |
|----------|------|-----|
| `apply_confidence_blend` | `arjun_confidence.py` | Blend (must be followed by re-demote) |

---

## 5. Public-train climb (why 150)

Measured ladder (public train / evaluate.py style artifacts):

```
~109  foundation (source precedence, embargo)
 → 129.80  R11 visible evidence
 → ~137–139  competitive heads / full Docker
 → ~142–145  integrity + residual deny / pure cells
 → ~148–150  field overlays + conf floor + residual census ON
 → 150.00  CFA 0  (train_evaluation.json)
```

Interactive charts: https://zwin-ux.github.io/XenoLedger/report/  
Data: 53 runs in `docs/showcase/report/runs.json` on the solution repo.

### Peer context (self-reported PR train scores, open set)

Typical published band **~120–139**. Examples: Abhishek **138.62**, mohavinash ~135, mikeg ~133, strobl ~130, arthurmichel00 ~128.7.  
**150** is the residual close after that competitive plateau, under CFA 0.

---

## 6. Kill list (what we refused)

| ID | Idea | Why dead |
|----|------|----------|
| K13 | Purpose-sig cell spam (95 cells) | CFA 18 |
| K14 | Soft bodyguard / Registry CLEAR | CFA 1 |
| K15 | Aggressive full emitted-policy demote | Net score loss |
| K16 | Blind conf → 1.0 for cal | Cal crash on wrong decisions |
| K17 | Global red biohazard stamp | No separation from branding red |

Repo wiki: [`wiki/concepts/kill-list.md`](https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/concepts/kill-list.md)

---

## 7. Score wiki (LLM / agent readable)

Full Karpathy-style score wiki lives in the **solution repo**, not only this PR folder:

| Page | URL |
|------|-----|
| Index | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/index.md |
| Overview | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/overview.md |
| Synthesis / path to 150 | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/synthesis.md |
| Kill list | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/concepts/kill-list.md |
| Residual gap | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/concepts/residual-gap.md |
| Experiment log | https://github.com/Zwin-ux/XenoLedger/blob/codex/score-control-20260724/wiki/log.md |
| Experiments | https://github.com/Zwin-ux/XenoLedger/tree/codex/score-control-20260724/wiki/experiments |

Agents and humans can open those pages for promote/reject history without re-deriving residuals from chat.

---

## 8. Reproduce

```bash
git clone https://github.com/Zwin-ux/XenoLedger.git
cd XenoLedger && git checkout c25a47845ad0eb1307c84484df7bf564c8fbe0cb
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Public train score: challenge `scripts/evaluate.py` against `data/train_labels.csv` → **150.00 / 150 · CFA 0**.

---

## 9. Contact

Mazen Zwin · https://github.com/Zwin-ux · https://www.linkedin.com/in/mazen-zwin-a4b363204/
