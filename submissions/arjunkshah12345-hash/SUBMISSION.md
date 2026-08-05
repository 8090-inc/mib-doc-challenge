# Submission — arjunkshah12345-hash

## Solution
- Repo: https://github.com/arjunkshah12345-hash/mib-doc-solution
- Tip: `38cbfcc` — Moonshots/tyler OCR + Strobl graft (demote ≤0.913 + promote ≥0.90)
- Runtime: `run.sh` → `solution.py` (dual pipeline)

## Public train (official evaluate.py)
- **136.71 / 150**
- **CFA = 0**
- Field 45.48 / Class 73.32 / Cal 17.91

## Validation predictions
- File: `predictions.jsonl` (5000 rows, MIB-100001…MIB-105000)
- SHA-256: `9758db2471362b6f9858b98122cc108d067b6fdf4be2057accb6bdfad169d480`
- Produced by offline graft of Moonshots val + Strobl val (demote@0.913 + promote@0.90)

## Integrity
- No answer-key channel, no trap lists, no copied rival validation predictions
- Promote only when Strobl high-conf APPROVED overrides hybrid NEEDS_REVIEW (≥0.90)
