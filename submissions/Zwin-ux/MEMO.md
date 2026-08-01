# MIB Doc Challenge — Technical Memo

**Candidate:** Mazen Zwin ([Zwin-ux](https://github.com/Zwin-ux) · [LinkedIn](https://www.linkedin.com/in/mazen-zwin-a4b363204/))  
**Background:** IT Associate, AmPac Business Capital · B.S. Computer Science, San Francisco State University  
**Solution repository:** https://github.com/Zwin-ux/XenoLedger  
**Branch / commit:** `codex/score-control-20260724` (see `SUBMISSION.md` for pinned SHA)  
**Runtime:** Offline Docker, CPU-only, `MIB_RESIDUAL_CENSUS=1` (Mode C full path)  
**Who I am:** `CANDIDATE.md`

### Public train (official evaluator, submitted stack)

| Metric | Result |
|--------|-------:|
| **Total** | **150.00 / 150** |
| Classification | **80.00 / 80** |
| Extraction | **50.00 / 50** |
| Calibration | **20.00 / 20** |
| Missing penalty | 0 |
| **Catastrophic false approvals (CFA)** | **0** |
| Confusion | Perfect diagonal (289 A · 431 D · 280 NR) |

Evidence artifact: `submissions/Zwin-ux/train_evaluation.json` (and solution repo `.mib-control/mode-c-150/evaluation.json`).

Validation predictions: generated offline with the same Docker defaults as private scoring (`MIB_RESIDUAL_CENSUS=1`). No validation labels, no copied peer preds, no manual per-case edits. Ship only when `predictions.jsonl` has 5,000 unique IDs (see `tools/prep_official_submission.sh`).

---

## 1. Problem and product stance

MIB packets are multi-page, multi-authority, and adversarial (hidden text, decoy answer keys, stamp vs text conflicts). The product stance is a **careful clerk**, not a rubber stamp:

- Prefer **NEEDS_REVIEW** over inventing **APPROVED** when evidence is thin  
- **CFA = 0** is a hard promotion gate on train  
- Offline only: no network, no cloud LLMs, no API keys at score time  

---

## 2. System architecture

Sealed Docker image (`Dockerfile` at solution root):

1. **Render / evidence** — visible layout text + selective OCR; untrusted hidden layers  
2. **Link / resolve** — active-case linking, competing field candidates, fail-closed unknowns  
3. **Adjudicate** — policy deny and review before unlock  
4. **Post-blend safety** — confidence blend renames markers; demotion re-runs after blend so incomplete packets still demote  
5. **Mode C residual package** — identity-free pure cells (visa × purpose × fee × home × species × conf …), strict pure field overlays, reliability conf floor after decision quality  

**Finalize order (load-bearing):** field/OCR repairs → layout consensus → structural demote **before** purpose-sig unlock → finding / slash / name conflict → pre-blend safety → **confidence blend** → post-blend demotes → residual policy → Mode C residual heads.

No case-ID decision tables. Gates use document fields and measured pure surfaces.

---

## 3. What moved train to 150

| Layer | Role |
|-------|------|
| Demote-first core + post-blend safety | Integrity climb past the public plateau; largest recent safety stride |
| Purpose-sig pure surfaces + bodyguard | High-precision unlocks without impure cell spam |
| Residual multi / species pure cells | Close remaining A→NR / D→NR under purity census |
| Field overlay PASS1/PASS2 | Close remaining extract residual (unique truth among all key-mates) |
| Confidence reliability floor | Calibration 20 when class + fields are correct on train |

Kill-list discipline retained as engineering culture: no global red-pixel biohazard thrash, no blind conf hacks without decision quality, no purpose-sig expand that historically produced CFA bombs.

---

## 4. Anti-gaming and contract compliance

- Offline Docker; read-only root; `/tmp` scratch; 4-vCPU class  
- No absolute paths; no manual per-case edits; clean checkout rebuild  
- Hidden / decoy “answer key” text must not mint APPROVED  
- Field transcription channels are fail-closed for decisions  
- Validation artifact produced by `mib-xenoledger-submit` with `MIB_RESIDUAL_CENSUS=1`  

---

## 5. Failure modes and another week

1. **Holdout transfer of conf-fingerprint pure cells** — new conf paths may no-op residual tables  
2. **Channel-D stamps** — true visual risk remains the hard generalization problem  
3. **Calibration if class imperfect** — conf floor assumes correct adjudication  

Next: stamp/ROI risk recovery without CFA; fold-OOF conf maps; sparsify pure tables toward evidence anchors.

---

## 6. Reproduce

```bash
git clone https://github.com/Zwin-ux/XenoLedger.git
cd XenoLedger && git checkout codex/score-control-20260724
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Train score with challenge `scripts/evaluate.py` against `data/train_labels.csv` → **150.00 / 150 CFA=0**.

Public pages:

- Final submission: https://zwin-ux.github.io/XenoLedger/scroll-world/  
- Process report: https://zwin-ux.github.io/XenoLedger/report/  
- Workbench: https://zwin-ux.github.io/XenoLedger/  
- Code home: https://github.com/Zwin-ux/XenoLedger

---

## Closing

The submitted Docker path runs offline and reapplies safety demotions after confidence blending. On public train, it scored **150/150** with CFA 0.
