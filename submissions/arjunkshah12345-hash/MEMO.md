# Technical Memo — private-seatbelt triple graft

## Approach

Triple-clerk graft with fail-closed private seatbelts:

1. **Moonshots / tyler** — fields + base adjudication.
2. **Strobl** — demote DENIED always / REVIEW ≤0.913; promote APPROVED ≥0.90.
3. **thegoleffect (MIT)** — `fee_status` only; dual-DENIED demote; promote ≥0.90
   **only if Strobl is not DENIED**; DENIED ≥0.90 vetoes keep-APPROVED unless
   Strobl also APPROVED.
4. **Field-manual demote** (`apply_emitted_demote`) after graft — never emit
   APPROVED with unpaid/unknown fee, barred sponsor, soft-embargo world,
   TRANSIT-7, or review-only flags. Train-neutral on the locked set; removes
   clerk-leaked Approvals that are private CFA bombs.

Public train (official `evaluate.py`): **137.23 / 150, CFA = 0**
(field 45.66, class 73.62, cal 17.95).

## Private seatbelts (why we won't repeat the last bite)

| Risk that bit us / rivals before | What we do now |
|----------------------------------|----------------|
| AK / purpose×sig unlocks | Refused |
| Ungated approve laundry / Gole≥0.85 | Refused (CFA=3 measured) |
| Blind full Gole field overwrite (211↑/166↓) | Removed — fee only (49↑/9↓) |
| Gole APPROVED over Strobl DENIED | **Vetoed** (CFA hole closed) |
| Keep APPROVED when Gole DENIED + Strobl≠AP | **Vetoed** (0 train flips; val insurance) |
| APPROVED with unpaid / unknown / barred / embargo | **Demoted** (field manual; 0 train flips) |
| Label-fit Engine B / learned referee | Refused |
| CFA on train | **0** |

## Competitive read

- Match ~137 CFA=0 band with stricter seatbelts than laundry stacks.
- Final rank is Docker on private test — seatbelts over vanity train.

## Attribution

Moonshots/tyler; Strobl `mib_pipeline/`; thegoleffect `clerks/goleffect/`.
See `ATTRIBUTION.md`.
