# Technical Memo — Private-first Moonshots/tyler fork

## Approach

This submission reuses the audited Calling Moonshots / tylergibbs1 visible-evidence
OCR runtime under MIT (see `ATTRIBUTION.md`). The rendered page is the trust
boundary; RapidOCR/PP-OCR reads visible text; deterministic rules plus a narrow
`insufficient_evidence` review resolver adjudicate.

## Private-transfer delta (only)

Upstream’s own memo ties catastrophic false approvals to score-optimal
`insufficient_evidence` → APPROVED bets. We keep their OCR/clerk intact and add:

1. `MIB_REVIEW_MARGIN=0.35` (default in `run.sh`) — require a small EV margin
   before the resolver may mint APPROVED.
2. `mib/private_edge.py` — one-way emitted-field demote (disqualifying risk,
   barred sponsor, soft embargo, unpaid, unknown fee / review flags). Never
   invents APPROVED.
3. `MIB_MIN_APPROVE_CONF=0.62` — soft demote of the weakest APPROVED bets.
   On public train: ~134.6 CFA=9 → ~133.5 CFA=3. Stays in the private-winning
   133–134 band while cutting CFA well below Moonshots' score-optimal ~12.

No trap lists, no answer-key channel, no copied validation predictions.

## Why this vs our prior Arjun stack

Unofficial private favored OCR-disciplined ~134-class systems over train-max
138. Copying the audited OCR clerk and only tightening CFA-sensitive approvals
is the fastest private-first move. Soft floor 0.62 lands ~133.5 CFA=3 —
in the winning band, with far fewer CFAs than Moonshots' score-optimal ~12.
