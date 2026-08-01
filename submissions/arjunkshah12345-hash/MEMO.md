# Technical Memo — Moonshots extraction + Strobl graft (private-first)

## Approach

Dual-pipeline graft aimed at private transfer, not public-train laundry:

1. **Calling Moonshots / tyler OCR** (`mib/`) for field extraction and base
   adjudication (RapidOCR-onnxruntime, native ledger, review model).
2. **Strobl visible-evidence pipeline** (`mib_pipeline/`) as an independent
   second opinion (pypdfium2 + Tesseract + RapidOCR recovery + pinned
   calibration).
3. **VisibleScoreFinalizer** on Moonshots rows → hybrid fields/decisions.
4. **Graft demote** (`mib_pipeline/graft.py`): if hybrid is `APPROVED` but Strobl
   is not, and hybrid confidence ≤ **0.913**, emit Strobl adjudication +
   confidence. Never invents `APPROVED`.

Public train (official `evaluate.py`, locked): **136.07 / 150, CFA = 0**
(field 45.48, class 72.74, cal 17.84). Threshold is the lowest CFA=0 cut on the
confidence×disagree frontier.

## Why this wins private vs vibemarketer-class ~135 CFA=0

Moonshots alone is ~134.6 with CFA≈9 (private poison). Soft floors to CFA≈0
collapse to ~131–133. Strobl alone is CFA-safe but weaker extraction (~133).
Blindly taking Strobl on every disagreement also collapses score.

The graft keeps Moonshots field strength and only demotes mid-confidence
approvals when an independent clerk refuses — kills DENIED→APPROVED CFAs
without over-demoting high-confidence true approvals. Organic: no AK, no
case-ID lists, no copied validation predictions.

## Attribution

Moonshots/tyler OCR (`mib/`, models); Strobl MIT pipeline (`mib_pipeline/`);
see `ATTRIBUTION.md` and `third_party_licenses/`.
