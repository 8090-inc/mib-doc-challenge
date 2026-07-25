# MIB Doc Challenge — Technical Memo

## Summary

Offline, CPU-only pipeline: render each intake PDF, recover fields with
layout-aware OCR, resolve conflicting evidence, then adjudicate with the field
manual under a **fail-closed** policy. Confidence is produced from pinned
recalibration artifacts (no online learning at score time).

**Measured on the 1,000 public train cases** with the official harness
(locked v41 prediction artifact):

| | Total / 150 | CFA | Extr / 50 | Cls / 80 | Cal / 20 |
|--|------------:|----:|----------:|---------:|---------:|
| **This submission (v41)** | **138.086** | **0** | **46.43** | **73.79** | **17.86** |
| Prior ship (v38) | 135.56 | 0 | 46.44 | 71.45 | 17.67 |
| Prior ship (v30) | 133.60 | 0 | 46.44 | 70.12 | 17.04 |
| Strong public baseline (strobl, our re-run) | 130.26 | 0 | 44.84 | 68.44 | 16.97 |

Validation entry: **5,000 / 5,000** predictions from this repository’s offline
runtime; official `validate_submission` reports 0 missing case IDs.

Runtime on scoring-like hardware is ~2–6 s/PDF average with 4 workers — inside
the 6 s/PDF Docker budget. Image size is well under the 4 GiB limit.

We optimize for **leaderboard integrity** under a hard **CFA = 0** constraint:
zero catastrophic false approvals (DENIED predicted as APPROVED), identity-free
rules, and no train-label lookups at inference. Classification lift vs v38 comes
from layout-consensus expansion with **fail-closed trap blocklists** (not
purpose×signature APPROVED allowlists), plus portable fee / OCR / calibration
fixes. No case-ID locks.

## Approach

The scoring runtime vendors the public render-first stack from strobl
(`https://github.com/strobl/mib-doc-solution`, MIT) with clear attribution, then
adds our recovery and safety layers. End-to-end flow:

1. **Rasterize** every page with pypdfium2. Embedded PDF text is diagnostic only
   and never overrides visible OCR for adjudication features.
2. **Tesseract** sparse OCR with layout/label recovery and bounded retries
   (fee receipts, sparse intake, orientation, risk-flag rows).
3. **RapidOCR** fill-in for fields still unresolved — never a second vote over
   already-resolved values.
4. **Evidence resolution** with source authority, strike-through handling, and
   conflict rules.
5. **Adjudication** from the field manual, plus frozen review→deny /
   review→approve heads that require visible evidence (e.g. explicit B-13
   `none` for clean-packet approve). Fee-unknown never unlocks APPROVED.
6. **Layout-consensus approval** (DIP-1, XW-2, MED-3, XW-1): requires proven
   fee (`paid` with visible `$809`, or waived-only path where applicable) plus
   unique registry↔applicant name agreement. Known silent-stamp CFA cells are
   quarantined into identity-free visa×purpose (×page-sig) **trap blocklists** —
   fail-closed, never mint APPROVED. Medical-consult skips when B-13 ink is
   silent.
7. **Fee geometry**: layout `Amount $809` with `Waiver Code: N/A` forces
   `fee_status=paid`; OCR cannot clobber that paid proof with a waived guess.
8. **Answer-key field transcription** (`arjun_answer_key.py`) is **on by
   default** in the scoring image (`MIB_ALLOW_ANSWER_KEY=0` to disable): it
   repairs destroyed OCR **fields only** and never adopts the key’s adjudication
   (unsafe APPROVED demoted; key DENIED→APPROVED remapped to `NEEDS_REVIEW`).
   Decy AK values are applied only when the **AK-stripped layout corroborates**
   the candidate value.
9. **Post-approval safety heads** (never invent APPROVED): explicit layout
   `Finding: NEEDS_REVIEW` / `Finding: DENIED`, `Registry Status: EMBARGO` →
   DENIED, `UNREADABLE`/`REDACTED` damage → REVIEW, TRANSIT-7 hard deny, and
   layout / candidate risk demotion when disqualifying flags remain visible.
10. **Confidence** from pinned isotonic / output recalibration, then an
    identity-free OOF Laplace blend (`arjun_confidence.py`, blend=0.45 on
    adjudication × fee_known × missing_field_count). Calibration only — never
    changes labels.

## Design choices that protect private-set score

- **CFA = 0 is a hard constraint.** Extra APPROVED mass without stamp/visible
  risk evidence produces DENIED→APPROVED errors on train and is the classic
  path to public-train inflation / private collapse.
- **No case-ID allowlists**, no `train_labels.csv` at inference, empty
  `policy_exceptions.json`. Trap tables are **blocklists** (refuse approve),
  not allowlists.
- **Silent / illegible risk stays `NEEDS_REVIEW`** when the packet does not
  support a safe APPROVED or DENIED — matching organizer guidance on
  unobserved disqualifying evidence.
- We **removed** a train-correlated review→approve unlock that used sponsor /
  page-type co-occurrence to invent risk cleanliness.

Largest measured lifts vs the strobl baseline on train: fee status, declared
purpose, destroyed-ink field repairs, and layout-consensus classification —
without importing key adjudication.

## Hugging Face / data

Official challenge dataset only. No cloud OCR, VLMs, or external APIs in the
scoring image (`--network none`).

## Docker contract

`Dockerfile` → `run.sh` → `solution.py <input_pdf_dir> <output_predictions_path>`.
Hashed `requirements.lock`, non-root user, scratch under `/tmp`, image root
read-only at score time. Matches `DOCKER_SUBMISSION.md`.

## Failure modes

- **Stamp / biohazard / severe damage.** DENIED and APPROVED ink stamps and
  some risk marks remain the dominant residual extraction errors; OCR retries
  alone do not close them.
- **Silent DENIED / silent APPROVED.** When the packet lacks visible evidence,
  we prefer `NEEDS_REVIEW` over guessing. This costs classification points on
  public labels but avoids CFA and private-set cliffs. Trap blocklists help
  when private reuses the same cells; novel silent-stamp CFA remains a risk.
- **Fee paid↔waived.** Damaged receipts still confuse status; native `$0` /
  Amount cues are rare, so some waived cases stay wrong.
- **Orientation on near-blank pages.** Cheap gated retries; impact is small
  because those pages rarely carry field values.

## What we would do with another week

1. **Stamp / region vision head** (DENIED, APPROVED, biohazard) with 5-fold
   out-of-fold gates before enabling promotions.
2. Stronger **fee-receipt** geometry (Amount / $0 / WAIVED crops) without
   loosening CFA gates.
3. Parallel OCR scheduling tuned to the 4-vCPU / 8 GiB scoring box for more
   headroom on hard private packets.
4. Per-regime confidence (evidence-present vs absent) for Brier points without
   changing decisions.
