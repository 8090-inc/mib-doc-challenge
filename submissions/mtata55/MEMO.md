# MEMO — MIB case adjudication

## Result

Scored in the exact offline scoring sandbox (`--network none --read-only --cpus 4 --memory 8g`),
against the 1,000 public training labels:

| | score |
|---|---|
| **Total** | **111.58 / 150** |
| classification | 58.59 / 80 |
| extraction | 37.44 / 50 |
| calibration | 15.55 / 20 |
| **catastrophic false approvals** | **0** |

This is the deterministic score of the pinned image: the base digest and the `tesseract` version
are pinned (see Runtime), so a rebuild reproduces it exactly. (Before pinning, the extraction
component drifted ~0.2 across `tesseract` versions — hence the pin.) The **0 false approvals** is
guaranteed by how the rules are written, independent of OCR.

This local number is a pessimistic floor: it counts every destroyed field against us, while the
official evaluator forgives fields it marks `unrecoverable`. On a proxy of that forgiveness the
score lands around **120–124**; the true official number sits between the two.

## The one idea that drives everything

The scorer pays +8 for a correct decision, +2 for punting to NEEDS_REVIEW, +1 for a missed
review — but **−4 for approving a case that should have been denied**, and a single false approval
also trips a disqualifier (`scripts/evaluate.py:176`). Being wrong in one specific direction is
catastrophic; hedging is cheap. So the whole pipeline follows one policy: **deny only on evidence
that was right every single time in training, approve only a complete and clean packet, send
everything else to review.** Zero false approvals is the designed-in consequence, not a tuned
outcome.

Two hard rules fall out of this:

1. **Never approve a packet whose `risk_flags` we couldn't read.** That field only appears on one
   form (the B-13 slip, present in ~30% of packets). If the slip is missing, we don't know the
   risk — we are not entitled to assume "none". Assuming "none" is exactly what caused all 31
   false approvals in the first version of the policy.
2. **OCR is good enough to deny on, not good enough to approve on.** An OCR misread behind a
   denial costs −2 at worst, and our OCR-backed denials are right ~85% of the time. An OCR misread
   behind an approval can be the −4 catastrophe. So denials may rest on OCR'd text; approvals
   never do.

## How it works

- **Filtering planted text** (`pdftext.py`): the PDFs contain malicious content — invisible text,
  instructions hidden in barcodes, fake answer keys. We filter by *how text is presented*, never
  by what it says: drop text that is white-on-white, transparent, or positioned off the page, and
  drop the known barcode-instruction line and SAMPLE watermark by pattern. Barcode metadata is
  kept; barcode *instructions* are never treated as policy. A field that is unknown from trusted
  evidence and a field supplied only by planted text stay distinct — they are decided differently.
- **Ranking sources** (`evidence.py`): when two pages disagree about a field, the more trustworthy
  source wins, using a fixed ranking (visible stamp > intake form > fee receipt > biometric >
  sponsor letter > registry > embedded text > OCR). One exception: `applicant_name`, where we
  measured per-source accuracy on training and use that instead of the ranking.
- **Decision rules** (`policy.py`): every rule shipped only after being 100% correct on training:
  disqualifying flag → DENIED (186/186), embargoed home world (50/50), TRANSIT-7 visa (53/53),
  unpaid fee (50/50), stale non-DIP-1 arrival (36/36), revoked sponsor (41/41).
- **Confidence** (`calibrate.py`): a cross-validated lookup table from (decision route, reason) to
  historical accuracy. It scores 15.5/20; a trained logistic model did worse, so we kept the
  table. A test fails if any route maps to the wrong confidence bucket.
- **Robustness** (`pipeline.py`): if a single PDF crashes the pipeline, that case gets a fallback
  record instead of sinking the rest of the 5,000-case batch.

## Committing hedges to DENIED (+1.69 classification, 0 FA)

Moving a case from NEEDS_REVIEW to DENIED scores +6 if it was truly denied, −2 if truly approved,
−7 if review was the right call — and can **never** create a false approval. That −2 downside
(versus −4 for a wrong approval) means a deny rule only needs moderate precision to pay. Two rules
cleared the bar: OCR-backed denials now fire (16/19 = 84% truly denied), and an embargoed home
world denies even when the risk slip is missing (14/14 — recovering the manual's
`planetary_embargo` disqualification). Net effect: 30 correct denials gained, against 2 wrong
denials and 1 lost review.

## Recovering unreadable fields

Our extraction score trails the strongest submissions, so we mined the gap. The rule for this
work: **measure every candidate change inside the actual scoring container, never on the dev
machine.** That rule paid for itself (see negative results).

- **Fee-receipt math** (`pages.fee_geometry`): when the `fee_status` label is unreadable, derive
  it from the receipt itself: positive amount + no waiver code = paid (297/297 in training), zero
  amount + DIP-WAIVER code = waived (106/106). Recovered 22 fields, added 0 errors.
- **Fuzzy label matching** (`pages._fuzzy_label`): OCR sometimes drops one character from a field
  *label* ("ee Status" for "Fee Status"), so the exact lookup fails even though the value reads
  fine. We allow one character of error, only when the match is unambiguous and the label is long
  enough. Container-verified +0.15 total, one deny recovery, on the pinned build (`sponsor_id`
  wrong-count unchanged at 8). It can admit a few wrong `sponsor_id` values (the loose SPN-####
  pattern can match decoys), but those are bounded by design: OCR-sourced values sit behind the
  approval guard, so a misread can only cause a −2 wrong denial or a wrong field — never a −4 false
  approval. It works across tesseract versions because it tolerates *any* single-character garble
  rather than fixing one specific error.

## Things that didn't work — kept, because they are the point

- **Approving more aggressively loses points.** The best possible gain from speculative approvals
  is +1.0, and only after accepting 23 false approvals. A 6-rule model that approved more (~+2 on
  training) was reverted: it created 2 false approvals and its gain didn't survive
  cross-validation. We ship zero speculative approvals.
- **A dev-machine OCR tweak was a mirage.** Lowering the OCR confidence floor (45→40) gained +0.12
  on the dev machine and exactly +0.00 in the scoring container, while making the visa and fee
  fields worse — tesseract confidence values differ across versions and don't transfer. Reverted.
  This is why every later change was container-verified before shipping.
- **Retrying OCR at higher resolution (300 DPI)**: would fix 6 cases, but there is no reliable
  trigger for when to retry — the best trigger fires on 82% of pages. Not built.
- **Position-based OCR matching**: zero yield — the failures are character errors, not layout
  errors.
- **A looser fuzzy match** (matching on label prefixes): +0.16 on the dev machine, but it made
  `sponsor_id` worse (9 → 16 wrong) by matching decoy IDs, with no classification gain. Rejected.
- **The remaining gap is not recoverable by better reading.** ~300 cases carry a true
  `risk_flags` value (the heaviest field, weight 8) that appears in no rendered pixel — destroyed,
  or present only in planted text. No reader can recover those; genuinely recoverable parse bugs
  total ~4 field-instances. Calibration is at its ceiling too: ~40% of cases fall in one
  low-information bucket (~29% correct) and no available feature splits it further.

## Runtime (scoring sandbox)

| | value | limit |
|---|---|---|
| image size | 0.29 GiB | 4 GiB |
| per-PDF average | ~0.42 s | 6 s |
| 1,000-case train run | ~415 s | 30,000 s cap |
| read errors | 0 | — |
| model artifacts | none (rules + classical CV/OCR) | 250 MiB each |

The per-PDF figure is from an unloaded machine; under load it rises (measured up to ~2 s/PDF), so
a wall-clock governor watches the budget and degrades late cases to text-only extraction rather
than overrunning the 30,000 s cap. For reproducibility the build is **pinned**: the base image by
digest and `tesseract-ocr`/`tesseract-ocr-eng` by version (Debian trixie is stable, so those
versions are fixed), and `pymupdf` by version. Since the OCR build determines the fuzzy-recovery
results, an unpinned tesseract had made the extraction score drift ~0.2 across rebuilds; pinning
removes that. The zero-false-approval guarantee does not depend on the OCR build regardless.

## Note on method

Built with AI coding assistance (Claude). Every rule and threshold was decided by measurement
against the public labels, not by intuition — each one traces to a count in this memo, and the
failed experiments were kept here rather than hidden. The confidence-floor episode shows the
process working: a change that looked good on the dev machine was killed by container verification
before it could ship. The zero-false-approval policy, the verification discipline, and the
decisions about what *not* to ship are my own.
