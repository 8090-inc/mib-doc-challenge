# MIB Doc Challenge — Technical Memo

## Approach

A deterministic document pipeline. No LLM, no VLM, no network:

```
visibility tagging → page typing → candidate generation → per-field resolution
   → features → 4-member classifier council → expected-value decision
   → isotonic-calibrated confidence
```

The runtime is PyMuPDF plus Tesseract/PP-OCR. scikit-learn is used only at build
time; the fitted models ship as JSON that ~80 lines of pure Python evaluate, so
the decision model is readable rather than a pickle.

**Evidence has tiers, and resolution is per field, not per page.** A packet
routinely has a clean intake form and a destroyed registry extract, so each
field independently takes the best source available to it, ordered by the field
manual's precedence: signed manual correction > adjudicator note > intake form >
biometric slip > sponsor attestation > fee receipt > registry extract. Two
sources are near-oracles and are treated as such — the adjudicator note's
`Finding:` matched the label 162/162, and the biometric slip's `Observed flags:`
matched 302/302. (The documents comma-separate flags while the labels
pipe-separate them; that mismatch is silent and costs the highest-weighted
field.)

**Eight of the nine scored fields are closed sets** — 12 species, 13 home
worlds, 10 purposes, 5 visa classes, 4 fee statuses, 8 flag atoms — so values
snap to a mined vocabulary with a tight edit-distance threshold rather than
being character-voted. This is what makes OCR output usable. `applicant_name` is
the exception: two tokens from a 144-token pool, used as a *prior* with a raw
fallback so an unseen name is not forced onto a wrong dictionary word.

**About one page in five is a full-page scan.** 1,956 pages in train (851
packets) are 1224×1584 JPEGs of intake forms — skewed, torn, degraded — with no
text layer beyond the page footer. OCR runs only on pages whose body text is
empty, which is why it costs 0.23 s/PDF against a 6 s budget rather than
dominating it. Recovering those pages is worth ~7 points; without them a third
of all evidence is invisible. Rendering is at 200 DPI: the scans are 144 DPI
native, so anything higher interpolates at extra cost for no extra information.

**Anti-injection is deterministic, and tags rather than deletes.** 216/1,000
train and 1,493/5,000 validation packets carry a hidden fake answer key in the
submission's exact field order, engineered against this rubric: the extraction
fields are mostly *correct* while the adjudication is flipped, usually to
APPROVED. Following it looks fine on extraction while harvesting −4 penalties.
`mib/visibility.py` tags spans by mechanism — off-CropBox, render mode 3/7,
near-zero alpha, low contrast against the *resolved* background, sub-legible
size, occlusion by a later opaque shape, hidden optional-content layers. Keeping
untrusted spans rather than dropping them is what distinguishes "unknown from
trusted evidence" from "supplied only by an injection"; 34/300 sampled packets
have all nine fields available *only* from the injection.

**The decision maximises expected score, not likelihood.** The payoff matrix is
transcribed from the challenge's own `evaluate.py` and asserted against it for
all nine (truth, prediction) pairs, so a rubric change fails the build. Two
consequences: at a 50/50 APPROVED/DENIED split DENIED wins (EV 4 vs 2), and with
no review mass APPROVED needs pA ≥ 0.60.

That bar is then raised deliberately. Approval is the only action that can score
negative, so its penalty is weighted ×2 when deciding (never when scoring),
lifting the threshold to 0.67. Measured out-of-fold across four CV seeds, this
costs 0.22 of 80 — smaller than the ±0.70 seed-to-seed spread, so
indistinguishable from noise — while cutting false approvals from 25 to 16.
`EVALUATION.md` calls false approval "the riskiest operational failure", makes
it tiebreaker #2, and puts "no catastrophic false-approval pattern" in the
minimum bar; trading a noise-level amount of expected score for a 36% reduction
is the right side of that bet.

**The council is four learners that fail differently** — two boosted ensembles,
two bagged forests. It beats every individual member and cuts catastrophic false
approvals from 41 to 25, because a member must convince the others before an
APPROVED sticks. Council disagreement is the strongest uncertainty signal
available (out-of-fold accuracy 0.73 unanimous vs 0.40 split) and feeds the
calibrator, never the decision. A fifth learner was measured across four CV
seeds and rejected: +0.09 points, +2 false approvals.

## Results

`tools/holdout_eval.py` splits the 1,000 labelled packets 800/200, rebuilds the
vocabulary, council, calibrator and field modes from the 800 **only**, and
scores the 200 with the official evaluator. Nothing derived from a held-out
packet touches any artifact used to score it.

| seed | Total (floor) | Total (adjusted) | Classification /80 | Extraction adj. /50 |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 119.03 | 127.81 | 64.50 | 49.35 |
| 1 | 114.80 | 124.44 | 60.45 | 49.40 |
| 2 | **112.73** | **122.43** | 58.75 | 49.17 |
| 3 | 118.65 | 126.64 | 61.95 | 49.35 |
| **mean** | **116.30** | **125.33** | **61.41** | **49.32** |

Two columns because the public labels omit `unrecoverable_fields`. The **floor**
charges for every field whose evidence was physically destroyed — 2,952 of 9,000
field-instances, `fee_status` alone 54%. The **adjusted** column removes them the
way `EVALUATION.md` says scoring does, using "the truth value leaves no trace in
visible text" as the proxy. The real number sits between, likely near the top,
since the grader excludes by construction rather than by proxy.

Validation: 5,000/5,000 records valid, 0 missing, `validate_submission.py` exit
0. Docker verified in CI on a native linux/amd64 runner: image 0.81 GiB (cap 4),
model artifacts 15.4 MiB (cap 1 GiB), runs under `--network none --read-only`,
byte-identical across two runs.

## Failure modes

- **Everything is mined from 1,000 packets.** Vocabularies, the revoked-sponsor
  list, flag inventory, name tokens and field modes all come from the public
  split. Concretely: **a revoked sponsor absent from training is treated as
  legitimate and its packets may be approved.** Revocation is inferred from a
  frequency signature (legitimate sponsors appear once or twice; revoked ones
  13–20× and skew ~75% denied), which recovered all three documented IDs plus
  three more. On a private set with different IDs the signature still works if
  they recur, and fails silently if they do not.

- **OCR is load-bearing and imperfect.** Its character errors are real —
  `SPN-47085` for `SPN-4705`, `planetary_eynbarg ve : es` for
  `planetary_embargo`. Closed-set snapping absorbs most of that, which is why
  the enum fields survive; `applicant_name` has only a token prior behind it and
  is the least reliable field in the record. Some heavily torn scans yield
  nothing usable.

- **Layout coupling is reduced, not eliminated.** The structured parsers key off
  the generator's wording and geometry. A vocabulary scan backstops them by
  recognising closed-set values on sight at lowest precedence, and tests cover
  reworded sponsor letters, unbolded tables, four correction phrasings and pure
  prose. `applicant_name` has no such backstop.

- **Residual information ceiling.** Where evidence survives, the pipeline is
  near-exact (adjusted extraction 49.3/50, and 1.000 accuracy on packets with an
  adjudicator note). Remaining classification loss is concentrated in packets
  whose evidence is genuinely destroyed, where the EV rule hedges to
  NEEDS_REVIEW — correct, but capped.

- **Staleness reference is inferred.** No packet prints a receipt date, so the
  180-day rule is measured against the latest arrival date visible in the batch
  being processed (`mib/reference.py`), trimmed for outliers and restricted to
  trusted text so a hidden date cannot shift it. Both public splits derive
  2026-07-12; a corpus from a different window tracks that window instead.

- **Mode imputation is applied at the output boundary only.** An unrecoverable
  closed-set field falls back to its mined modal value, worth +2.49 extraction
  and never negative under exact-match scoring. It runs strictly after the
  decision: `fee_status == "unknown"` implies NEEDS_REVIEW on 44/44 packets, and
  imputing `paid` upstream would erase that rule and manufacture false
  approvals. A test asserts the separation.

## What another week buys

1. **Better OCR on the worst scans.** Deskew is naive and there is no dewarping
   or per-region adaptive thresholding. The pages OCR currently fails on are the
   same partial-evidence packets holding nearly all remaining classification
   loss, so this is the highest-value work by a wide margin.
2. **A name-specific recogniser.** `applicant_name` is the only open field and
   the weakest under OCR. A small character model constrained to the observed
   31-glyph alphabet would beat generic OCR plus dictionary snapping.
3. **Predict which fields are unrecoverable** and route those cases to
   NEEDS_REVIEW deliberately rather than incidentally.
4. **Tighten the holdout.** Four seeds at n=200 give a ±4 spread; repeated
   stratified holdouts with artifacts rebuilt per fold would resolve changes
   smaller than ~3 points, which currently I cannot distinguish from noise.
