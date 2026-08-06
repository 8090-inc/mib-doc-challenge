# Technical Memo — private-seatbelt triple graft

## Approach

Triple-clerk graft with fail-closed private seatbelts:

1. **Moonshots / tyler** — fields + base adjudication.
2. **Strobl** — demote DENIED always / REVIEW ≤0.913; promote APPROVED ≥0.90.
3. **thegoleffect (MIT)** — `fee_status` only; dual-DENIED demote; promote ≥0.90
   **only if Strobl is not DENIED**; DENIED ≥0.90 vetoes keep-APPROVED unless
   Strobl also APPROVED.

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
| Label-fit Engine B / learned referee | Refused |
| CFA on train | **0** |

## Competitive read

- #91 ~142 holdout: still public favorite if stack transfers.
- #73 142 with Engine B: soft if B dies.
- #85 ~137.23 CFA=0: we match their train band with stricter seatbelts.
- Laundry ignored.

## Attribution

Moonshots/tyler; Strobl `mib_pipeline/`; thegoleffect `clerks/goleffect/`.
See `ATTRIBUTION.md`.
