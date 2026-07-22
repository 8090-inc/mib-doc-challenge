# Technical Memo — MIB Document Processing Pipeline

## Summary

An offline, CPU-only pipeline that turns each PDF packet into a structured applicant
record and an adjudication (`APPROVED` / `DENIED` / `NEEDS_REVIEW`) with a calibrated
confidence. On a held-out train split it scores **129.21 / 150** (classification 68.42/80,
extraction 43.42/50, calibration 17.37/20, 5 catastrophic false approvals).
At **~0.8–2 s/PDF** — comfortably inside the 6 s budget.

## Approach

The pipeline is four stages; each was built and measured independently before integration.

1. **OCR → record (`src/ocr.py`).** Render pages with pypdfium2 (~200 DPI) and read them
   with RapidOCR (PP-OCR via ONNX; models bundled in the wheel, so fully offline).
   Orientation is **gated**: OCR the page as-rendered once, and only if it doesn't look
   upright (few lines / tall boxes / low confidence) try the other three 90° rotations and
   keep the best. That is ~3× cheaper than always trying four. The untrusted PDF **text
   layer** is captured into a separate `hidden_text` field, never mixed with visible OCR.

2. **Extraction (`extract_v2.py` + `vocab.py` + `repair.py`).** Label-anchored key/value
   extraction over the OCR boxes, then **closed-vocabulary snapping**: five fields
   (`visa_class`, `fee_status`, `declared_purpose`, `species_code`, `home_world`) are tiny
   closed sets mined **from the training split only**; a noisy OCR string is snapped to the
   nearest known value — but only when the match is close, otherwise it passes through
   unchanged (measured 0.000 false-snap rate under leave-one-value-out, so unseen private-set
   values are never corrupted). Spacing repair uses **only trusted visible OCR** (see below).

3. **Risk flags (`flags.py`).** `risk_flags` is the highest-weight field (8 pts) and drives
   denials. Detected by rules mined from the training data (distant supervision): full-string
   exact-match went 0.535 → **0.825 with precision 1.000 on every flag** (it never invents a
   flag), at recall 0.638.

4. **Adjudication (`clf_final.py`).** A calibrated, cost-sensitive classifier over the
   extracted fields plus OCR-derived features (confidence, page geometry, evidence presence).
   It is an sklearn `HistGradientBoosting` + ExtraTrees blend — deliberately **not** LightGBM,
   which needs `libomp` (a system library we cannot ship in the air-gapped image). The
   decision layer optimizes expected score under the real payoff matrix (a false approval of
   a `DENIED` case is −4, the worst outcome), and confidence is the model's calibrated
   probability, feeding the 20-point Brier term directly.

**Engineering discipline.** One deterministic train/dev split used everywhere; everything fit
on train and reported on dev; the final classifier **selected on train out-of-fold** (an
earlier version looked ~1 point better purely from being the max over several dev-scored
candidates). Each stage passed an adversarial review for gaming, leakage, and injection.

## Failure modes (known and measured)

- **Unrecoverable "silent-evidence" labels.** ~44% of flagged training cases show *no* visible
  evidence of the flag; ~99 are labeled `DENIED` on admin metadata the packet never contains.
  The challenge maintainer confirmed (issues #4/#5) that these should be `NEEDS_REVIEW` — systems
  should not guess. We deliberately do **not** learn spurious correlates to "recover" them: that
  would inflate the public score and collapse on the private set. This *costs* classification
  points on the public labels but is the correct, generalizing behavior — and it protects the
  catastrophic-false-approval count (tie-breaker #2).

- **Prompt injection was a real bug we shipped, then fixed.** The PDF text layer often has better
  word spacing than OCR, which is tempting because the scorer counts spacing. Our first repair
  guarded value *invention* but not *whitespace*; an adversarial auditor showed a shredded-spacing
  payload could drive three fields to 0% accuracy, and text-layer "agreement" features let an
  echo attack flip adjudications toward `APPROVED`. Both are fixed: `repair()` no longer reads the
  text layer at all, and **no text-layer-derived feature reaches the model**. The defense is now
  structural — the model input is asserted bit-identical between clean and attacked records, so
  any hidden payload is inert (verified 0/200 attack flips on dev).

- **Extraction gaps.** `fee_status` is the weakest field (~65–81%): its value geometry is
  inconsistent and the label/value search misses. Merged-token OCR errors on open fields
  (`applicant_name`) survive because spacing repair is intentionally visible-only.

- **Over-approval is the dominant operational risk.** 3 false approvals remain on dev. The
  pipeline never predicts `APPROVED` when risk evidence is visible, which keeps this low, but a
  wrong approve is −4, so this is the number to watch on the private set.

- **Orientation gating is imperfect on sparse pages.** ~40% of rotation calls are on near-blank
  portrait/stamp pages where "most text wins" is a coin flip; measured impact is ~zero because
  those pages carry no field values, but it is unprincipled.

## What I would improve with another week

1. **Classification is the gap (63.65/80); extraction and calibration are near their ceilings.**
   The highest-value work is better *decisions*: features for cross-page evidence conflict, a
   proper trust-resolution pass over the `FIELD_MANUAL` precedence order (stamp > form > slip >
   sponsor > registry > text layer), and explicit handling of review-only-flag combinations that
   escalate to `DENIED`.
2. **`fee_status` extraction.** Fixing its value-anchoring is the biggest single extraction win and
   would also stop it from over-triggering `NEEDS_REVIEW` downstream.
3. **Cross-validation over a single split.** Move from one 80/20 hold-out to k-fold so the reported
   number has an error bar, and validate on the public `data/validation` set end-to-end.
4. **Tighten the orientation gate** to skip sparse pages (measured: all benefit comes from
   text-rich rotated pages), removing wasted OCR passes.
5. **Parallelize OCR across the 4 vCPUs.** Currently sequential; the budget has headroom, but a
   process pool would add robustness margin on slower private-test hardware.
6. **Confidence per difficulty.** Calibrate separately for evidence-present vs evidence-absent
   cases, since we *know* when risk evidence is missing — honest low confidence there is free
   Brier points.

## What I explicitly ruled out (with data)

Fine-tuning the OCR recognizer looked obvious but **hurt**: a PaddleOCR recognizer fine-tuned on
distant-supervision crops hit 99% crop-level accuracy yet scored *worse* end-to-end (over-segmenting
clean tokens like `MIB-000001` → `MIB-0000013`), was ~10× slower, and would add 400+ MiB to the
image. RapidOCR's remaining errors are detection/field-logic, not character recognition — so a
better recognizer is not the lever.
