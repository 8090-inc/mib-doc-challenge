# Submission

- GitHub username: `arjunkshah12345-hash`
- Public solution repository: https://github.com/arjunkshah12345-hash/mib-doc-solution
- Mandatory Dockerfile: https://github.com/arjunkshah12345-hash/mib-doc-solution/blob/main/Dockerfile

Ship build **v42.6** (tyler clerk + edge): emitted-policy guardrail, Finding
stamp wins, DIP redacted-name keep, visible DIP-WAIVER+$0 fee receipts,
widened hi-res risk OCR, Docker `MIB_ENABLE_HIRES_OCR=1`. Solution tip:
https://github.com/arjunkshah12345-hash/mib-doc-solution/commit/31692c71f1758dc933c44a5a957dcfe719376d0d

Demote-pass train (official evaluator on public labels):

| Section | Score |
|---------|------:|
| Extraction | 46.41 / 50 |
| Classification | 72.51 / 80 |
| Calibration | 17.45 / 20 |
| **Total** | **136.36 / 150** |
| Catastrophic false approvals | **0** |

Above tylergibbs1’s published full-data ~134.52 while keeping CFA=0 and leading
extraction. No MED-3/XW-1 LC trap overfit from v41’s 138.086 peak.

Validation predictions: **5,000 / 5,000**, official validator clean
(0 missing case IDs). Predictions SHA-256:

`7698e2cce397eb3c52d93f8606c369fec913a4d1dc24fbe5b9a28db867848090`

This entry counts only when this PR targets the official `main` branch **and**
the submission form is completed:

https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform
