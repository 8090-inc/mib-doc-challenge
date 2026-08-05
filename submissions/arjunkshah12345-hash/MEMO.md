# Technical Memo — Moonshots extraction + Strobl graft (private-first)

## Approach

Dual-pipeline graft aimed at private transfer, not public-train laundry:

1. **Calling Moonshots / tyler OCR** (`mib/`) for field extraction and base
   adjudication (RapidOCR-onnxruntime, native ledger, review model).
2. **Strobl visible-evidence pipeline** (`mib_pipeline/`) as an independent
   second opinion (pypdfium2 + Tesseract + RapidOCR recovery + pinned
   calibration).
3. **VisibleScoreFinalizer** on Moonshots rows → hybrid fields/decisions.
4. **Graft** (`mib_pipeline/graft.py`): demote if hybrid is `APPROVED` and
   Strobl is `DENIED` (always) or Strobl is `NEEDS_REVIEW` with hybrid conf ≤
   **0.913**. Promote if hybrid is `NEEDS_REVIEW` and Strobl is `APPROVED`
   with Strobl conf ≥ **0.90**. DENIED-always is private fail-closed insurance
   (no-op on the locked 1k frontier). Promote recovers high-conf clerk
   approvals the hybrid left in review — measured CFA-safe on train.

Public train (official `evaluate.py`, locked): **136.71 / 150, CFA = 0**
(field 45.48, class 73.32, cal 17.91). Demote cut 0.913; promote floor 0.90.

## Why this wins private vs vibemarketer-class ~135 CFA=0

Moonshots alone is ~134.6 with CFA≈9 (private poison). Soft floors to CFA≈0
collapse to ~131–133. Strobl alone is CFA-safe but weaker extraction (~133).
Blindly taking Strobl on every disagreement also collapses score.

The graft keeps Moonshots field strength, always honors Strobl `DENIED`,
demotes mid-confidence approvals when Strobl says `NEEDS_REVIEW`, and only
promotes when Strobl high-conf `APPROVED` overrides hybrid review. No label-fit
Engine B / stack referee. Organic: no AK, no case-ID lists, no copied val preds.

## Attribution

Moonshots/tyler OCR (`mib/`, models); Strobl MIT pipeline (`mib_pipeline/`);
see `ATTRIBUTION.md` and `third_party_licenses/`.
