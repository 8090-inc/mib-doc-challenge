# Submission

- GitHub username: `arjunkshah12345-hash`
- Public solution repository: https://github.com/arjunkshah12345-hash/mib-doc-solution
- Mandatory Dockerfile: https://github.com/arjunkshah12345-hash/mib-doc-solution/blob/main/Dockerfile

Ship build **v42.5** (transfer-first / private-win): best-in-field extraction
plus tyler-parity emitted policy (Finding stamp wins; non-DIP hardship-only
waived; DIP-1 waived restored). Solution tip:
https://github.com/arjunkshah12345-hash/mib-doc-solution/commit/9a51b7172fe26ce85af9565d5daceffdd82b0b58

Demote-pass train (official evaluator on public labels):

| Section | Score |
|---------|------:|
| Extraction | 46.41 / 50 |
| Classification | 71.61 / 80 |
| Calibration | 17.27 / 20 |
| **Total** | **135.29 / 150** |
| Catastrophic false approvals | **0** |

Leads published rival extraction (goleffect 45.8 / zubalr 44.2 / tyler 43.8)
while staying in the private-safe classification band (no MED-3/XW-1 LC trap
overfit from v41’s 138.086 peak).

Validation predictions: **5,000 / 5,000**, official validator clean
(0 missing case IDs). Predictions SHA-256:

`5e46844c7c5dbde3b1bfc749c5aa930f7c8859ca89708fdf74c09c96ce446571`

This entry counts only when this PR targets the official `main` branch **and**
the submission form is completed:

https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform
