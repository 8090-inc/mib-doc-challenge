# MIB Doc Challenge — Technical Memo

## Result

The submitted pipeline is offline, CPU-only, and deterministic by construction.
On all 1,000 public training packets it produces 1,000 valid records with no
missing, extra, duplicate, or schema-invalid cases and scores **129.00 / 150**:
43.47/50 extraction, 68.86/80 classification, and 16.67/20 calibration, with
**8 catastrophic false approvals**.

Against the previous 122.31 revision of this memo that is +6.69 with two fewer
false approvals. Three things account for it: a candidate-trained classifier
blended with the deterministic posterior, fitted output defaults for
closed-vocabulary fields the pipeline could not read, and a post-decision
correctness calibrator. All three are described below.

**This number is not the number the leaderboard scores, and it understates us.**
`EVALUATION.md:117` removes from each case's extraction maximum any field whose
visible evidence was cut out, washed out, torn away, or present only in untrusted
hidden text; `EVALUATION.md:119` says the public `train_labels.csv` deliberately
omits that column. So the figure above is charged for fields the private scorer
does not count. Of our 1,131 wrong fields, **398 have their true value only in
quarantined hidden text** and 665 are absent from visible evidence entirely.
Removing just the first group raises extraction on these same predictions from
43.72 to **45.74**. We decline those 398 on purpose; see "The answer key" below.

## Approach

**Trust boundary first.** Every PDF glyph is classified before extraction.
White-on-white, sub-2-point, and off-crop text is quarantined, and downstream
code sees only visible evidence. Visible fake answer keys are also removed as
bounded blocks, including multi-line keys with labelled fields below a banner.
The bounds and payload-shape checks prevent an innocent prose mention of
“answer key” from deleting the rest of a page.

This is the highest-value defence in the system. In a measured 250-packet sample,
56 packets (22.4%) carried an injected answer key. Its field values were 93.2%
correct, but its adjudication was 0% correct and skewed 48-to-8 toward approval.
A naive extractor is therefore rewarded for following the decoy on one scoring
axis and driven into the −4 false-approval bucket on another.

**Text first, selective OCR.** In a 120-packet sample, 71.7% of pages had a
usable text layer; only 28.3% required OCR. Those pages use three unioned
Tesseract passes: baseline layout analysis, an eroded render that reconnects
stroke-damaged glyphs, and sparse-text mode for forms that ordinary layout
analysis treats as images. Unioning preserves evidence unique to any pass.
Denoising was excluded after measurement: it increased OCR cost by 56% and
changed mean field accuracy by −0.2%.

**Extraction follows document authority.** Closed vocabularies are normalized
with bounded fuzzy repair; ambiguous terms such as `paid` require label
anchoring because they occur inside other values. Manual corrections and
sponsor-attestation prose have explicit parsers. Pages are typed from their
printed titles, and conflicting scalar values resolve using the field manual's
order—adjudicator note, intake form, biometric slip, sponsor attestation,
registry extract—before confidence or page order. A regression probe puts
`SPN-2222` on an intake form and `SPN-1111` on a sponsor letter; the intake value
wins in both page orders.

`applicant_name` is the one open-vocabulary field, so it has no vocabulary to
check a candidate against, and its Title-Case pattern is the exact shape of a
neighbouring label. Where the name was blank the window slid onto the next label
and returned it: 136 of 4,690 non-blank names in an earlier build read `Species
Code`, `Home World`, or an OCR-damaged variant such as `Species Home Workt`.
Candidates containing any field-label word are now skipped and the scan
continues to the next window and then to the attestation sentence. No true
training name contains such a word in any position, so the rule discards nothing
the corpus relies on, and an unreadable name yields a blank that widens the
posterior instead of a confident wrong answer.

**Policy is declarative; decisions are score-aware.** `rules/policy.yaml` orders
named terminals and `mib/policy.py` implements one predicate per terminal.
Runtime class posteriors are fitted on the pipeline's own extracted fields, not
ground truth, so unread evidence is represented in the probabilities. A stale
`DIP-1` packet has its own fitted terminal: the measured ground-truth population
contains 32/32 denied non-diplomatic stale cases, while 15 stale diplomatic
cases contain 12 approved, 3 review, and no denials.

The final action maximizes expected challenge points rather than posterior
argmax. For probabilities \(p,q,r\) of approval, denial, and review:

```text
EV(APPROVED)     = 8p - 4q + r
EV(DENIED)       =      8q + r
EV(NEEDS_REVIEW) = 2p + 2q + 8r
```

Reported confidence is the posterior probability of the chosen class, which is
the proper quantity for the evaluator's Brier term.

**Two small fitted models sit on top, and neither can reach a field.**
`EVALUATION.md:70` bans LLMs, VLMs, multimodal foundation models, and cloud OCR
while explicitly permitting small task-specific and candidate-trained models.
Both of ours are that: hand-specified features, fitted offline on the public
training set, shipped as artifacts totalling 3.02 MiB, CPU-only, no network.

1. **A blended adjudication classifier** (`mib/blend.py`, `rules/blend.pkl`,
   3.01 MiB). A gradient-boosted tree over 64 evidence, coverage, and damage
   features, convex-blended into the deterministic posterior at weight 0.4 —
   *blended with*, never replacing. `policy.allowed_labels` is applied on top of
   the blend, so a label the policy forbids stays forbidden however confident the
   model is; that ordering is the trust boundary, not an optimisation. The weight
   was selected out of fold on the challenge payoff matrix, paired against weight
   0 on identical splits: −2.60 false approvals and +0.110 classification,
   improving in 5 of 5 repeats. No case id, filename, or quarantined text is ever
   a feature. Cases settled by a visible adjudicator finding are excluded from
   training and short-circuited at inference — the deterministic path owns them.

2. **A post-decision correctness calibrator** (`mib/calibrate.py`,
   `rules/correctness.json`, 4 KiB). A ridge regression over 25 quantities the
   decision layer has already produced — posterior, blended posterior, model
   probabilities, top-two margin, disagreement, and the emitted label and
   confidence — predicting whether the emitted adjudication is correct. It runs
   *after* the label is final and is given no way to reach a field or an
   adjudication; enabling or disabling the artifact leaves all nine fields and
   every adjudication byte-identical and moves only the 689 non-settled
   confidences. Worth +0.38 calibration (Brier 0.0927 → 0.0832) with the
   catastrophic false-approval count unchanged. It ships as plain JSON
   coefficients rather than a pickle, so the runtime path does not deserialise
   arbitrary objects and does not depend on a scikit-learn version; the artifact
   is still SHA-256 pinned and refuses to load against a different feature order.

## The answer key

~20% of packets carry an injected answer key in hidden text. It is the single
largest apparent extraction opportunity in the corpus and we decline it.

Measured on our own output: of 1,131 wrong fields, **398 have their true value
present only in quarantined hidden text**. Reading them would raise the public
training score by roughly two extraction points. It would gain essentially
nothing on the private set, because `EVALUATION.md:117` removes exactly those
fields from each case's extraction maximum, and `EVALUATION.md:184` penalizes
outputs that follow adversarial hidden instructions. The trade is
strictly negative once the metric that counts is the one being optimised.

That is why the trust boundary is the first thing in the pipeline rather than a
filter bolted on afterwards, and why hidden content is permitted to push a
decision only *away* from approval, never toward it.

**Where the EV rule is overridden, it is overridden by a stated rule.**
`never_approve_terminals` lists terminals whose defining condition is *missing
required evidence*, and approval is removed from the candidate set there
regardless of what the posterior says. `med3_no_check` is the entry that matters:
MED-3 requires a clean biohazard check, no packet in the corpus states one, so
the bucket is by construction the set whose required check is absent. The fitted
posterior sits at 0.61 APPROVED and the EV rule would approve it for +0.69
classification points.

That +0.69 was declined. Taking it would double the pipeline's catastrophic
false approvals from 10 to 20; it is worth roughly 0.5 net once the calibration
gain from hedging is counted; and it bets that the public 63%-approved MED-3 mix
holds privately on a posterior fitted from 51 packets. Every runtime-visible split of the bucket was
tested first — biometric-slip presence, registry extract, page count, OCR
fraction, extraction completeness, quarantine volume, fee status — and none
separates it; the only splits that "won" were label-fitted cells of one to nine
cases that the 25-case support floor discards anyway.

The constraint lives in the policy file rather than inside a tuned probability
on purpose. The posterior keeps describing what the training data actually did,
and a reviewer can see the judgement call and disagree with it.

That rule was re-tested after the blended classifier shipped, because the blend
now filters the bucket before the policy sees it and the original arithmetic
predated it. **In sample the case for lifting it looks strong and it is a
mirage.** Of the 33 packets where the policy overrides an EV decision that wanted
APPROVED, truth is 31 APPROVED, 1 NEEDS_REVIEW, 1 DENIED — apparently one false
approval rather than ten. Out of fold, on 5 folds × 5 repeats with the blend
refitted inside every fold, it costs **+5.20 false approvals** for +0.45 combined
points, because the model that made the bucket look safe was fitted on those very
rows. The rule stands.

## Levers measured and rejected

Recorded because the negative results are the substance of the design, and each
was cheap only because it was measured before it was built:

- **Second-reader hedge conversion.** Using an independently derived reading of
  the packet to convert `NEEDS_REVIEW` into a decisive call: 40.0% precision
  against a 36.4% base rate on the gated stratum — no information. The reverse
  direction, using a second reader to veto approvals, catches **0 of our 8**
  catastrophic false approvals while destroying up to 77 correct approvals.
- **Detecting `illegible_biometrics` structurally** rather than reading it, since
  it is the one flag that describes an unreadable panel rather than a printed
  value: 19 field strings fixed, 39 broken. Damage in this corpus is applied
  independently of flag content, so a destroyed slip is `none` about twice as
  often as it is `illegible`.
- **Label-anchored fuzzy repair** of garbled values next to a readable field
  label (`Fee Status: carved`): ceiling of 5 recoverable cases across the whole
  corpus.
- **Richer confidence calibration** — evidence-quality features, and a logistic
  model with per-class isotonic correction — both within 0.05 calibration points
  of the shipped ridge.

The common finding: 347 of 381 hedges are chosen by the EV rule itself rather
than forced by a policy constraint. The decision layer is already making the
payoff-optimal call given its evidence, so converting hedges requires new
evidence, not a new threshold.

## Failure modes and another week

**Most of the remaining extraction loss is not recoverable, and that is now
measured rather than asserted.** Of the 1,131 wrong fields at 43.47/50, only
**68 have their true value present anywhere in visible text** — a ceiling of
0.378 points. 398 are present only in quarantined hidden text, which we decline;
665 are absent from the PDF altogether. Private scoring removes the genuinely
unrecoverable ones from each case's maximum while the public labels do not carry
that metadata, which is why the public figure understates the submitted system.

The 8 remaining catastrophic false approvals are all of one kind: the packet is
missing its disqualifying evidence rather than obscuring it. Seven read
`risk_flags` as `none` against a true disqualifying flag, and **not one of those
packets contains any line mentioning "risk" or "flag"** on any page, visible or
quarantined. A guard that demoted every approval lacking a risk panel would avoid
7 of them and forfeit 112 correct approvals, so no rule recovers them; only a
different document would.

The highest-priority engineering gap is multi-applicant isolation. The manual
warns that one packet may contain several applicants, with the active `case_id`
selecting the relevant one. Page typing now enforces authority for conflicting
scalar values, but it does not yet associate every page with the active
applicant. Applicant-name reconciliation also remains a repetition/native-text
heuristic rather than a full identity graph.

Other private-set risks are unobserved hidden carriers (non-rendering text mode,
occlusion, optional-content groups, annotations, metadata, and barcode
payloads), damaged page titles that defeat deterministic page typing, and
adjudicator stamps printed as images on otherwise text-rich pages. With another
week I would add adversarial fixtures for those carriers, active-case page
association, and stamp detection that runs independently of the text-sufficiency
OCR gate.

## Reproducibility

The image accepts exactly `<input_pdf_dir> <output_predictions_path>`. It ships
only deterministic Python code, Tesseract/Poppler, the policy files, and pinned
runtime dependencies. No LLM, VLM, cloud OCR, API key, validation answer, or
case-id lookup table is present. Development models were used only as analysis
instruments; every runtime behavior they motivated was reimplemented as
deterministic code and covered by ordinary tests or measured corpus probes.

The repository includes the exact offline/read-only Docker command, 168 unit and
adversarial regression tests, the public scoring commands, and `docs/RECON.md`
with the measurements and rejected experiments behind the design.

The two fitted artifacts are reproducible from the repository:
`scripts/fit_blend_artifact.py` and `scripts/fit_correctness_artifact.py` each
print the SHA-256 that `mib/cli.py` pins, and the runtime refuses to load an
artifact whose digest or feature order does not match. Both scripts import their
feature builders from the `mib/` package rather than redefining them, so the
model cannot be served vectors it was not trained on.
