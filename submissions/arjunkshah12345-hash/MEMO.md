# Technical Memo — Moonshots + Strobl + Gole graft (private-first)

## Approach

Triple-clerk graft aimed at private transfer:

1. **Calling Moonshots / tyler OCR** (`mib/`) for field extraction and base
   adjudication.
2. **Strobl visible-evidence pipeline** (`mib_pipeline/`) as an independent
   second opinion.
3. **thegoleffect** (`clerks/goleffect/`, MIT) as a third clerk for scored
   fields and CFA-safe class gates.
4. **VisibleScoreFinalizer** on Moonshots rows → hybrid.
5. **Graft** (`mib_pipeline/graft.py`):
   - Demote hybrid `APPROVED` on Strobl `DENIED` (always) or Strobl
     `NEEDS_REVIEW` with hybrid conf ≤ **0.913**.
   - Promote hybrid `NEEDS_REVIEW` when Strobl `APPROVED` conf ≥ **0.90**.
   - Take nonempty Gole scored fields.
   - If still review and both Strobl+Gole `DENIED` → `DENIED`.
   - If still review and Gole `APPROVED` conf ≥ **0.90** → `APPROVED`.

Public train (official `evaluate.py`, locked): **137.30 / 150, CFA = 0**
(field 45.66, class 73.68, cal 17.96).

## Why this vs 142-claim rivals

- **#91 speculator19** (142.59 CV / 142.15 holdout) uses a learned referee over
  three pipelines and reports CFA on holdout. Strong favorite if it transfers;
  meta-overfit risk remains.
- **#73 midasavocado** (142.31) turns on public-label Engine B; A-only / frozen
  holdout reads ~135–138. Soft for private.
- **#85 bmdhodl** (137.23 CFA=0) is the nearest honest CFA=0 rival — we edge it
  at 137.30 without label-fit Engine B.
- Laundry (#52 150, #3 AK, #78 CFA=12) ignored.

Organic: no AK, no case-ID lists, no copied val preds. Gole is attributed MIT
and only feeds fields + locked CFA=0 class gates.

## Attribution

Moonshots/tyler (`mib/`); Strobl (`mib_pipeline/`); thegoleffect
(`clerks/goleffect/`). See `ATTRIBUTION.md` and `third_party_licenses/`.
