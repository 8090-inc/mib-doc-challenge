# Submission

- GitHub username: `arjunkshah12345-hash`
- Public solution repository: https://github.com/arjunkshah12345-hash/mib-doc-solution
- Mandatory Dockerfile: https://github.com/arjunkshah12345-hash/mib-doc-solution/blob/main/Dockerfile

Ship build **v42.7** (private-first freeze): CFA=0 clerk, Finding wins, holdout-
validated DIP-WAIVER+$0, **answer-key transcription OFF** in Docker, hi-res OCR
on. Solution tip:
https://github.com/arjunkshah12345-hash/mib-doc-solution/commit/bed0b8b0e703fd73806f311632a1b8f2caf0eca5

Demote-pass train (official evaluator on public labels):

| Section | Score |
|---------|------:|
| Extraction | 46.41 / 50 |
| Classification | 72.51 / 80 |
| Calibration | 17.45 / 20 |
| **Total** | **136.36 / 150** |
| Catastrophic false approvals | **0** |

Private focus: AK off removes the train-only planted-key channel (Abhishek-class
cliff). Holdout (200) preferred DIP-WAIVER+$0 over hardship-only at CFA 0.
Tyler’s new OCR audit reports ~134.72 — we optimize transfer, not train-max.

Validation predictions: **5,000 / 5,000**, official validator clean
(0 missing case IDs). Predictions SHA-256:

`7698e2cce397eb3c52d93f8606c369fec913a4d1dc24fbe5b9a28db867848090`

This entry counts only when this PR targets the official `main` branch **and**
the submission form is completed:

https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform
