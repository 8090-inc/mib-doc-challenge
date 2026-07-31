# Submission — arjunkshah12345-hash

## Solution
- Repo: https://github.com/arjunkshah12345-hash/mib-doc-solution
- Tip: `1315b4d` (v43.2 Moonshots/tyler fork + private edges)
- Runtime: `run.sh` → `scripts/predict.py` with `MIB_REVIEW_MODEL=1`, `MIB_REVIEW_MARGIN=0.35`, `MIB_MIN_APPROVE_CONF=0.62`, `mib/private_edge.py` demote-only

## Public train (official evaluate.py)
- **133.47 / 150**
- **CFA = 3**
- Field 45.47 / Class 70.79 / Cal 17.21

## Validation predictions
- File: `predictions.jsonl` (5000 rows, MIB-100001…MIB-105000)
- SHA-256: `ebfbe5e25fa2dad08a89083a63b5fd502b2c42800daa90917284616889eeb03f`
- Same private edges as runtime (emitted demote + approve conf floor 0.62)
- Adj mix: APPROVED 958 / DENIED 1918 / NEEDS_REVIEW 2124
- Unique applicant names: 4220
- Zero APPROVED with catastrophic risk flags; zero APPROVED below conf 0.62

## Integrity
- No answer-key channel, no trap lists, no copied rival validation predictions
