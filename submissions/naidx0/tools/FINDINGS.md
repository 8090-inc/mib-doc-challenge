# Measurement notes

Results from the replay harness (`harness.py` + the tools beside it), which
re-runs extraction, canonicalization and adjudication over cached OCR.  Kept
because the negative results are the useful part: each one closes off a line of
work that looks obviously promising from the outside.

Baseline: **123.05 / 150** on the full 1,000-case training set (classification
64.70, extraction 42.43, calibration 15.92, 2 catastrophic false approvals).

## What the search actually bought

| change | total | catastrophic |
|---|---|---|
| flag rescue at threshold 62 (as first written) | 122.51 | 2 |
| threshold swept to 66 — wins 5/5 held-out folds | 122.87 | 2 |
| drop the redundant revoked+DIP-1+illegible short-circuit | **123.05** | 2 |

The first row is the lesson: the rescue was added on the strength of a single
convincing example (a B-13 risk panel that OCR'd as
`"Coserved Yaga: | ing':'e_fiomet'se"`, scoring 57 against
`illegible_biometrics` and 37 against the next flag) and it *cost* half a point
until it was swept.  A plausible mechanism is not a measurement.

## Settings that were already optimal

Swept and left alone: `STALE_DAYS` (flat from 165 to 210 — robust, not
knife-edge), `FLAG_RESCUE_MARGIN` and `FLAG_RESCUE_MINLEN` (no effect at
threshold 66), `_PURPOSE_MIN_RATIO` (no effect from 50 to 70),
`_REVOKED_MODE` (`trusted` costs 0.40 against `ocr`).

## The over-review trade, priced

158 true approvals are routed to NEEDS_REVIEW.  Each is worth +6 raw if
rescued and −6 if the packet was really a denial, so the question is whether
any bucket can be split.  Measured on the full corpus:

| variant | total | catastrophic |
|---|---|---|
| baseline | 123.05 | 2 |
| both zero-denial buckets → APPROVED | **123.31** | **2** |
| `unverified_clean` → APPROVED | 123.21 | 8 |
| `med3_no_biometric` → APPROVED | 123.15 | 10 |
| `_GATE=all` (no evidence gate at all) | 123.19 | 8 |

Every aggressive variant is *dominated*: flipping whole review buckets to
APPROVED gains less than the safe change and multiplies false approvals,
because the Brier penalty on the newly-wrong confident approvals eats the
classification gain.  The conservative posture is not costing points here.

`unverified_clean` is the clearest case.  It holds 37 true approvals against
only 4 true denials, but all four are packets whose disqualifying flag
(`memory_tampering`, `planetary_embargo`, `biohazard_red`) sits on a B-13 slip
that is **not in the packet at all** — every other field reads cleanly and
matches the truth, and no computed signal separates them from the 37.  With
n=4 any apparent split would be chance.  The bucket cannot be split on the
available evidence, so it stays in review.

## Where the extraction points actually are

Per-field loss, measured on the record the pipeline *emits* (i.e. after the
scavenge and modal-fee fallback layers), not on the resolved fields:

| field | weight | accuracy | points lost |
|---|---|---|---|
| risk_flags | 8 | 0.72 | 2.49 |
| sponsor_id | 5 | 0.80 | 1.11 |
| visa_class | 5 | 0.83 | 0.94 |
| fee_status | 4 | 0.81 | 0.84 |
| applicant_name | 5 | 0.86 | 0.78 |
| arrival_date | 4 | 0.84 | 0.71 |
| declared_purpose | 3 | 0.79 | 0.70 |
| home_world | 5 | 0.88 | 0.67 |
| species_code | 6 | 0.98 | 0.13 |

Scoring the resolved fields instead of the emitted record understates
extraction by ~1 point and makes `fee_status` look like a 1.91-point hole when
the existing fallback already covers most of it (57% -> 81% once measured
correctly).  Any harness that skips `_build_record` will send you chasing a
problem that is already solved.

## risk_flags is not an OCR problem

Breaking down every case where our flag set differs from the truth:

| cause | share |
|---|---|
| packet contains no B-13 biometric slip at all | **82%** |
| B-13 present, text contains nothing resembling the flag | 10% |
| B-13 present, degraded text near-matches the flag (rescuable) | 7% |

So the dominant cause is that the evidence is not in the document.  Confirmed
from the other direction: where a B-13 *is* present our emitted distribution
tracks the truth closely (`none` 57.6% vs 56.8%); where it is absent we emit
`none` 91% of the time against a true rate of 50.5%.

`none` is nonetheless still the single most likely value for those packets, so
the current default is already the best available constant guess and there is
no free win from changing it.

## Deriving the flags does not pay

Several flag names describe conditions the pipeline already detects internally
for review routing, so emitting them into the output field looks like free
points.  Measured precision against the truth:

| flag | internal signal | fires | precision | recall |
|---|---|---|---|---|
| rescinded_denial | `note_rescinded` | 4 | **1.000** | 0.571 |
| identity_conflict | `_name_conflict` | 9 | 0.333 | 0.214 |
| illegible_biometrics | `illegible_page or uncertain_flags` | 70 | 0.314 | 0.449 |
| sponsor_mismatch | `_sponsor_conflict` | 2 | **0.000** | 0.000 |

Because the field is scored as an exact set match, a flag emitted wrongly
*breaks a case that was previously correct*.  At precision 0.31-0.33 the last
three lose more than they gain, and `sponsor_mismatch` never once agreed with
the truth.  Only `rescinded_denial` is clean enough to emit, and it is worth
about 1% of cases.

Correlating the truth against every boolean the pipeline computes found no
predictor of `illegible_biometrics` above 0.44 against a 0.20 base rate --
i.e. "the slip was unreadable" is genuinely not what that flag records.

## Calibration is close to its floor

For a rule that fires on a group with true accuracy `p`, emitting confidence
`c` costs `(c-p)^2 + p(1-p)` per case, so the optimum is `c = p` and the
`p(1-p)` term cannot be removed without changing the decisions themselves.
Refitting every rule to its measured accuracy and testing on 5 held-out folds
scored *worse* than the current hand-tuned table at every shrink strength
(k=0..100).  The existing constants are already at or near the optimum; the
remaining calibration gap is mostly irreducible noise, not mis-set numbers.

## Method notes

- Any candidate that wins on the full corpus is re-scored on 5 held-out folds
  before adoption -- picking the best of ten settings on one corpus is itself a
  way to overfit, and on 1000 cases noise alone will produce a winner.
- Catastrophic false approvals are reported next to every score, so a setting
  cannot buy points by approving true denials unnoticed.
- Measure on all 1000 cases, never a subset.  A 145-case edge-case sample once
  showed a clean run while the full set had 22 catastrophic false approvals.
