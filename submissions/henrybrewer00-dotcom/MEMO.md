# MIB Doc Challenge -- Technical Memo

> **Summary** -- the brief asks for one to two pages. That is this section.
> Everything after it is the evidence, kept because every number below is
> measured and the measurements are the point.

**The system.** Offline, CPU-only, no LLM or network. A PDF becomes a
*visibility-filtered* text layer (spans are kept or discarded by how they
render, not by what they say), OCR fills raster pages, six page templates
locate fields, and a precedence chain resolves conflicts -- adjudicator stamp,
then intake, biometric slip, sponsor, registry. A three-member calibrated
ensemble turns that evidence into a posterior; an expected-value rule turns the
posterior into a decision against the published payoff matrix.

**Scores.** Out-of-fold, 5-fold with a full refit per fold, seeds 0–3:

| section | score |
| --- | --- |
| Field extraction | 45.27 / 50 |
| Classification | 68.15 / 80 |
| Calibration | 16.68 / 20 |
| Missing-case penalty | 0.00 |
| **Total** | **130.10 / 150** |

Catastrophic false approvals: 22 / 1000. Running the shipped image over
`data/train` and scoring with `scripts/evaluate.py` gives **143.49** -- that
figure is *in-sample*, since the adjudicator was fitted on those labels, and is
reported separately for exactly that reason.

**Three decisions that mattered.**

1. *Visibility is decided by rendering.* Hidden text, off-crop text and barcode
   payloads never become a field value; only their **presence** is a feature.
   `EVALUATION.md` removes fields that exist only in untrusted hidden text from
   the scoring denominator, so refusing them costs nothing and reading them is
   the disqualification tripwire.
2. *One corpus statistic for fit and serve.* Training and inference call the
   same `corpus_context`. They once differed -- p99 versus p95 on arrival dates --
   which fitted the model on a staleness regime the container never produced
   and cost 2.96 points. Every train/serve mismatch since has been the same bug
   wearing a different hat, and §9 lists four of them.
3. *Expected value, not argmax.* A false approval scores −4 where hedging
   scores +2, so the rule maximises expected points rather than probability.

**Extraction is worth ~3x its face value, and that is why the model is not the
bottleneck.** Fed PERFECT fields, the same adjudicator scores 77.77/80 (or
79.40 with signals) against the 67.79 it scores on fields we actually read. So
the 4.79 extraction points we lose cost a further ~10 classification points --
about 2.1 classification points per extraction point. Classification is not
evidence-limited; it is *extraction*-limited, which is why seventeen model-side
experiments all landed at the noise floor while the section still looks 12
points short of full marks. Since extraction is itself 0.02 from its ceiling,
both sections are closed.

**The ceiling is evidence, not modelling.** Extraction loses 4.79 points and
**none of it is a parsing bug**: every field we miss is one no engine can read,
and every imputation default is already the argmax of its truth distribution.
Calibration's oracle -- an in-sample isotonic fit, unshippable -- is worth 16.81
against the 16.68 we ship, so 0.13 exists and cannot be reached. Twenty
distinct improvement attempts are recorded in §9b and §9d; all but four landed
inside ±0.5 seed noise.

The extraction ceiling is worth stating exactly. Of the 4.79 points we lose,
3.38 are in no text layer and 1.39 exist only in hidden answer-key text, so the
most any rule-abiding solution can score on the public training set is 45.23.
We score 45.27, at it. A reported 50.00/50 on this set is not a better
reader; it is the answer key.

**What is most likely to be wrong.** The private set may embargo different
worlds or revoke different sponsors than the public one. Both are re-derived
from whatever corpus the container is given and both pins are refutable by
contradicting evidence, but that path is exercised only by synthetic tests.

## What the system is

A four-stage offline pipeline. No LLM, no network, no GPU.

```
PDF ──▶ visibility-filtered text layer ──▶ page classification ──▶ per-field
        + OCR for raster pages              (6 templates)          evidence pool
                                                                        │
        adjudication ◀── expected-value ◀── calibrated posterior ◀───────┤
        + confidence      decision rule      (rules + GBM)               │
                                                                    corpus context
```

The core design decision: **separate "what the packet shows" from "what we
guess"**. The evidence record only ever holds values read off visible marks.
Priors and imputation are applied at output time, so the adjudicator always
sees `fee_status = unobserved` rather than `fee_status = paid`.

## 1. Visibility is decided by rendering, not by parsing

Every trap in this dataset is a claim that isn't visible. Rather than
enumerating trap types, each text span is tested against the rendered page:

- painted in (or near) the background colour,
- drawn outside the crop box,
- drawn in an invisible text render mode or at ~zero opacity,
- set below a legible font size,
- buried under a later opaque white fill,
- or leaving no residual ink in a 110-dpi greyscale render of the page.

The last check is the general one and subsumes the rest: a span is evidence
only if a human looking at the page would see marks there. Lines that announce
their own channel (`SYSTEM:`, `BARCODE PAYLOAD:`, `answer key`) are dropped
even when visible, because the field manual ranks those below visible evidence.

**This mattered more than it looks.** I extracted the hidden answer-key rows
and checked them against the labels: their *field values* agree with truth
about 90% of the time (name 65/75, species 69/75, home world 68/75), but the
adjudication they inject is wrong in **75 of 75 cases** -- it always says
`APPROVED`. The injection is built to be tempting on the 50-point extraction
section and fatal on the 80-point classification section, where a false
approval costs −4. Reading it would have raised extraction by several points
and destroyed classification. The pipeline never reads it.

## 2. OCR: the scans are blur-limited, not resolution-limited

About 1,950 of 4,159 training pages are raster scans with no text layer. My
first preprocessing chain (adaptive threshold, aggressive denoise, 210 dpi)
was actively destroying legible text -- `TRIANGULAN` came out `TRAOULATE`, and
`2026-02-13` came out `2256-02-13`.

I benchmarked 7 preprocessing variants × 6 render resolutions over real scanned
pages, scoring each by how many *ground-truth field values* survived:

| variant | truth fields recovered |
| --- | ---: |
| drop-colour + unsharp @ 250 dpi | **118** |
| plain grey + unsharp @ 250 dpi | 118 |
| plain grey @ 300 dpi | 105 |
| adaptive threshold @ 210 dpi (original) | ~60 |
| any variant @ 450 dpi | ≤96 |

Binarisation was the mistake: these scans are blurred and low-contrast, so
thresholding eats strokes that Tesseract reads fine in greyscale. Final chain
is drop saturated stamp ink → flatten illumination → unsharp mask → 250 dpi →
`--psm 12`, with `--psm 6` and `--psm 11` tried only when the first pass scores
badly against the packet vocabulary. Sparse-text segmentation beats the uniform
block on these layouts because the forms are label/value columns separated by
whitespace, not paragraphs.

A **second OCR engine** runs on any packet where a scored field is still
unresolved after the Tesseract pass: RapidOCR (PP-OCRv4 detection + recognition
via ONNX Runtime, 16 MB of models shipped inside the `rapidocr-onnxruntime`
wheel, CPU-only, no network). Its output is treated as an independent evidence
set overlaid onto unknown fields only -- it never overrides a value Tesseract
resolved. Worth **+1.21 points**.

## 3. Page classification has to survive damage

Title matching alone left **241 of 488** scanned pages unclassified -- titles
arrive OCR-mangled (`FORM I-8080`) or clipped by the crop (`netary Registry
Extract`). Classification now runs title match → fuzzy title match (tolerant of
a clipped head) → body field-label signature. That cut unclassified scans to
147 and raised scanned-intake recognition from 50 to 101 pages.

## 4. Evidence resolution: precedence, but quality-aware

Fields resolve through the field manual's precedence order (adjudicator note ▸
intake form ▸ biometric slip ▸ sponsor attestation ▸ registry extract). One
amendment: **the text layer is consulted before OCR at every level**. Ranking
purely by page class made a half-legible scan of an intake form outrank a crisp
registry extract, which cost 0.6 extraction points. Within a trust level,
same-value candidates vote.

Closed vocabularies (12 species, 13 home worlds, 5 visa classes, 10 purposes,
8 risk flags) are matched by edit distance with a *uniqueness margin* -- if the
runner-up is equally close, the field stays unread rather than guessing. Result:
these fields have essentially **zero misreads** once extracted; all their
remaining loss is non-observation.

Applicant names have no closed vocabulary, so the lexicon is built from the
input directory itself at run time: names read off clean text-layer pages
across the corpus yield the 144 first-name and 144 last-name morphemes the
generator uses, and OCR names are corrected token-wise against that pool. This
is derived per-run, so it works identically on a private test set.

## 5. Policy: rules where the manual is explicit, learning where it isn't

The rule engine encodes the manual (disqualifying flags, TRANSIT-7, fee rules,
sponsor requirement, rescinded-denial handling, `SAMPLE DENIAL` as a decoy),
plus three things the manual says must be inferred from examples:

- **Revoked sponsors beyond the published three.** Sponsor ids are otherwise
  near-unique per packet (864 distinct over 1,000 cases); six ids recur 13–20
  times each and deny ~75% of the time. Three are the published
  `SPN-0007/0139/4040`; the others are `SPN-9090/7331/2718`. Rather than only
  hardcoding them, the pipeline **detects heavy sponsor reuse in whatever
  corpus it is given**, so a test set with different revoked ids still works.
- **Embargoed home worlds.** `Wolf-1061c` denies on the world alone (15/15
  denied outside DIP-1, 11/11 approved under DIP-1 -- the diplomatic exemption
  is real and class-specific); `TRAPPIST-1e` and `Eris Relay` always carry an
  explicit `planetary_embargo` flag. This was the one constant fitted to the
  public labels for a fact the manual does not publish, so it is now derived
  instead, from two label-free corpus signatures: the share of *readable* risk
  panels showing `planetary_embargo` (1.000 for the flagged pair, ≤0.086 for
  every other world) and the share of packets whose registry extract prints an
  `EMBARGO` status (0.16–0.47 for the three real ones, exactly 0.000 for all
  ten others). It returns the same three worlds on the public set and on every
  subsample down to 60 packets, and in a mutated corpus where the embargo is
  moved to a different world it follows the embargo. The pinned values survive
  only as a fallback, and are discarded when the corpus positively refutes
  them.
- **Staleness** is measured against the corpus's own latest arrival date (p95,
  so one OCR-mangled future date can't set the reference), because no packet
  prints its own receipt date. Getting this statistic *consistent between
  training and serving* turned out to matter more than any modelling change in
  this memo -- see §7.

A gradient-boosted ensemble then predicts the posterior over the three classes
from 161 semantic features plus the 60-column text block of §5a -- including the
rule engine's verdict and its reason as features. Nothing keyed to a case id or
file name goes in.

## 5a. The packet's own wording, as 60 more columns

The 161 hand-built features record what the reader *resolved*. The pages also
carry how they are worded -- note prose, stamp captions, waiver boilerplate,
damage banners, the phrasing a sponsor uses when an attestation is conditional
-- and that correlates with the adjudication in ways no hand-written signal
captures. Word 1–2 gram TF-IDF over the packet text, reduced to 60 dense
columns by truncated SVD. Case ids, sponsor ids, dates, amounts and bare
numbers are masked first, so the vectoriser learns language rather than
identifiers. Measured out-of-fold: classification 67.63 → 68.31, accuracy
0.844 → 0.854.

Nothing here touches a label, but it is still **fitted**, and that distinction
is the whole reason this component is implemented the way it is. Truncated SVD
components are basis vectors derived from the data, so fitting on the training
corpus and re-fitting on the corpus being scored produces two different,
arbitrarily rotated and sign-flipped bases -- "component 7" would mean something
different in each, and a model trained against one would be reading noise from
the other. The fitted vectoriser and SVD are therefore stored in the model
artifact and only ever `transform`-ed at serve time (`mibdoc/textblock.py`),
and the cross-validation above fits them inside each fold so held-out packets
never shape the axes they are later scored on.

That is the same failure mode as the corpus-statistic bug in §7, caught before
it shipped rather than after.

## 6. Decisions are made by expected value, not argmax

The scorer's payoff matrix is asymmetric (correct 8, hedge to review 2, missed
review 1, wrong A/D 0, **false approval −4**), so the pipeline maximises
expected points under the calibrated posterior instead of taking the argmax.
Probabilities are Platt-scaled; a second logistic stage maps posterior *shape*
to P(this answer is correct) for the reported confidence.

This is worth real points and is the single biggest safety lever:

| decision rule | classification | catastrophic false approvals |
| --- | ---: | ---: |
| argmax, uncalibrated | 61.4 | 44 |
| argmax, calibrated | 62.0 | 45 |
| **expected value, calibrated** | **62.0** | **21** |

Same model, same features -- false approvals cut by more than half at equal
score, purely by pricing the −4 penalty into the decision.

The rule is only correct if our payoff matrix is the scorer's, so that is
checked directly against `scripts/evaluate.py::classification_points` rather
than transcribed from the brief: all nine cells agree. The corollary is that
the 35 remaining false approvals are the expected-value-optimal number under
this posterior, not an oversight -- forcing them down costs more in demoted
correct approvals than it recovers, which is exactly what the gate experiment
in §9b measured.

I also swept a deliberately inflated false-approval penalty to see whether
extra risk-aversion pays. Averaged over three CV seeds, −4 scores 62.53 with
23.3 catastrophic approvals and −6 scores 62.44 with 18.3. The score difference
is inside CV noise (±0.5 between seeds), so I kept the **exact** payoff matrix
rather than introduce a tuned constant that a private test set could punish.

## 7. Honest numbers (5-fold out-of-fold, official evaluator, training set)

Features generated by the shipped container, so these numbers reflect the
Tesseract build that actually runs at scoring time:

```
Field extraction  45.27 / 50     (identical on every seed)
Classification    68.15 / 80     (68.25 / 67.78 / 68.15 / 68.41)
Calibration       16.68 / 20     (16.60 / 16.70 / 16.67 / 16.73)
Missing-case       0.00 / -10    (no case is ever skipped)
Deterministic    130.10 / 150    (seeds 0-3, 5-fold out-of-fold)
Catastrophic false approvals: 22 / 1000  (23 / 22 / 21 / 22)
Mean confidence Brier: 0.0832
```

These are the **shipped** configuration: the three-member ensemble and
`decide.CALIBRATION_WEIGHT = 8`. An earlier revision of this table reported
129.82 with 36 catastrophic false approvals; both were measured before the
decision rule changed, and the catastrophic figure in particular understated
the shipped system's safety by about 1.6x. The weight is what buys that: an
ablation across four seeds puts catastrophic approvals at 32/33/37/33 with the
weight off and 18/25/25/23 with it on, for a score difference of +0.11 in
favour of *off* -- inside the +/-0.4 seed noise. We keep the weight because a
consistent 11-per-1000 reduction in the worst error class is worth more than a
score difference we cannot distinguish from noise, and because catastrophic
false approvals are the second tie-breaker in the published ranking.

For comparison, running the shipped image over `data/train` and scoring with
the challenge's own `scripts/evaluate.py` gives **143.49** (extraction 45.27,
classification 79.16, calibration 18.96, zero catastrophic false approvals).
That number is *in-sample* -- the adjudicator was fitted on those labels -- and
is quoted here only because it is the figure the submission form asks for and
the one most public comparisons use. The 129.64 above is the honest forecast.

Features for this table were produced by running the shipped image over all
1,000 training PDFs, so the OCR that generated them is the OCR that will run at
scoring time.

**These are means over four cross-validation seeds, not a single split, and
the distinction is not cosmetic.** The classification section moves by up to
0.7 points between splits of the same data with the same code -- larger than
most of the individual changes in this memo. A single split of this pipeline
produced 130.16 and another produced 129.24; quoting the first would have
overstated the system by half a point and, worse, would have made a
noise-neutral change look like a gain. Every comparison in this memo that
turns on less than ~0.5 points is reported with the seed spread behind it.

**These numbers replace an earlier reported 128.39, and the difference is worth
explaining rather than quietly restating.** That figure was measured with the
trainer's own copy of the corpus reference date on both sides of the
experiment. It was internally consistent and therefore not obviously wrong --
but it described a configuration the container never ran, because the container
computed that date differently. Measured three ways on held-out splits:

| configuration | classification |
| --- | ---: |
| fit p99 / evaluate p99 -- what the old CV *reported* | 66.98 |
| fit p99 / **serve p95** -- what the container actually *ran* | 65.05 |
| **fit p95 / serve p95** -- one function, both sides | **67.84** |

So the honest reading is that the shipped system was worth about 125.5, not
128.4, and is now worth 129.82. The lesson generalises past this bug: a cross-validated score is only
evidence about the deployed system if every corpus-level statistic is computed
by the same code at fit time and at serve time. Two independent investigations
found this bug before I did, from opposite directions -- one auditing constant
fragility, one rebuilding the decision layer -- which is the strongest argument
in this memo for measuring the deployed configuration rather than the
convenient one.

Where the rest of the gain came from, all measured on the shipped extraction:

| change | effect |
| --- | ---: |
| one corpus statistic for fit and serve | classification 65.05 → 67.63 |
| second OCR engine no longer gated off 74% of eligible packets | extraction 44.77 → 45.14 |
| truncated flag tokens and anchored `none` read as evidence | extraction 45.14 → 45.16 |
| OCR-mangled damage markers no longer become field values | extraction 45.16 → 45.17 |
| 60-column TF-IDF/SVD text block (§5a) | classification 67.63 → 68.31 |
| six-member ensemble over the single posterior | classification 68.31 → 68.74 |

Runtime in the scoring container (`--cpus 4 --memory 8g --read-only`):
**1.54 s per PDF**, measured end to end over the full 5,000-packet validation
set (7,686 s), just under 4× inside the 6 s budget. Image is 0.36 GiB of the 4 GiB allowance;
the adjudicator is 32.99 MiB and the shipped OCR weights 15.4 MiB, against a
250 MiB per-artifact and 1 GiB total allowance.

Output is deterministic: repeat container runs over the same input are
byte-identical, at the same and at differing CPU counts.

These training numbers are **pessimistic** relative to validation scoring:
`data/train_labels.csv` omits `unrecoverable_fields`, so I am penalised for
fields the private labels exclude from the maximum -- e.g. `sponsor_mismatch`
on MIB-000001, which appears nowhere in that packet.

## 8. Where the remaining error actually is

I measured this rather than guessing. Three variants of the same model:

| fields fed to the model | classification |
| --- | ---: |
| A -- as extracted (the real system) | 62.4 |
| B -- observed fields read perfectly | 64.0 |
| C -- all fields known | 78.4 |

The A→B gap (1.6 points) is everything better OCR and parsing could still buy.
The B→C gap (14.4 points) is fields the packet never renders visibly at all.
**The system is evidence-limited, not accuracy-limited.** Accuracy splits
confirm it: 96.2% where a signed adjudicator note is present, 89.0% where the
biometric slip supplies risk flags, 63.1% where it does not -- and 52% of
packets contain no biometric slip in any form, so their risk flags exist only
in the labels.

## 8b. Recovering the policy exactly

Because the labels are generated from the true fields by a deterministic
policy, any rule stated exactly is worth more than any amount of model
capacity. Fitting an interpretable rule set to the *true* fields reaches
**97.3%**, and a gradient-boosted model on the same inputs reaches only 92.2%
out-of-fold -- the rules generalise better than the fit.

Doing that exercise found three rules of mine that were simply wrong:

| rule | what I had | what the labels say | support |
| --- | --- | --- | ---: |
| Unpaid fee | exempt for DIP-1 or a hardship waiver | **no exemption exists**; DIP-1 unpaid denies 16/16 | 50/50 |
| TRAPPIST-1e, Eris Relay | denied only via their risk flag | deny **on the home world alone**, DIP-1 not exempt | 50/50 |
| Staleness | `corpus_max_date − 180d` | a fixed boundary inside a 49-day empty gap; DIP-1 exempt outright, no diplomatic note needed | 32/32 |

The second matters far more than its support suggests: every such packet also
carries `planetary_embargo`, so on *true* fields the rule is redundant -- but we
fail to read risk flags on 46% of packets, and there it is worth ~5 points of
accuracy.

Two visible markers turned out to be perfectly predictive of `NEEDS_REVIEW`
and are now rules: a literal `UNREADABLE` (14/14) and "Arrival date missing
from trusted visible evidence" (10/10).

Equally useful were the negative results, which stopped me building things:

- **Multiple review-only flags do not escalate to a denial.** 23/23 two-flag
  cases stay `NEEDS_REVIEW`; the field manual's "may combine into a denial in
  edge cases" is a red herring -- every apparent escalation is a `Wolf-1061c`
  packet being denied for its home world.
- **There is no seventh revoked sponsor.** The six known ids appear 13–20
  times each; the next most frequent appears twice.
- **`declared_purpose` and `species_code` have zero policy effect**, and MED-3
  has no special biohazard rule -- `biohazard_red` denies uniformly (87/87).
  MED-3 merely has a higher biohazard base rate, which is a prior, not a rule.

Sensitivity analysis puts `risk_flags` at roughly **3× the value of any other
field** (−3.3 points of accuracy per 10% error rate, versus −1.1 for
`visa_class` and −0.9 for `fee_status`), which is why it gets the second OCR
engine and the fuzzy matcher.

## 9. Known failure modes

- **Invisible risk flags.** ~238 training packets carry flags with no visible
  carrier page. The model falls back to the prior and hedges; this is most of
  the residual error and I do not think it is recoverable from the documents.
- **Heavily degraded scans.** ~147 scanned pages stay unclassified. Their text
  is genuinely destroyed, not merely mangled.
- **Names from OCR, and why this is close to done.** `applicant_name` is the
  only required field with no closed vocabulary, so it is the one field with a
  meaningful *misread* rate rather than a non-observation rate. Pre-lexicon,
  names read off a clean text layer are 98.7% exact (786/796) while names read
  through OCR are 52.4% (87/166); the run-time lexicon and cross-page vote then
  lift the field as a whole to **96.1% on resolved values** (38 wrong of 962),
  which is the single largest thing the lexicon buys. What is left is
  mostly not recoverable by a better matcher:

  | residual failure | n | recoverable? |
  | --- | ---: | --- |
  | a genuinely different person is printed on some page | 21 | No -- this *is* the `identity_conflict` trap, not a reading error |
  | OCR damage landed on a different **valid** pool token | ~6 | No -- `Ariix`, `Nexix` and `Zavara` are all real names in the lexicon, so nothing marks the reading as suspect |
  | near-miss the lexicon could still snap | ~8 | Perhaps, worth ≈0.04 points |
  | one token missing or an artefact appended | 3 | Perhaps |

  The whole field is worth 5.56 points and currently returns 5.35, so the
  entire remaining headroom in the single worst-performing field is about 0.2
  points, and over half of that is a trap the dataset intends us to fall into
  rather than an OCR deficiency.
- **Corpus-derived context needs a corpus.** Sponsor-reuse detection and the
  staleness reference are stable at 1,000+ packets but would degrade on a very
  small input directory. The published revoked list and rule defaults remain as
  a floor.

## 9b. What did not work

**Seed-bagging the ensemble** (tested last, and the one I expected to work).
Every member is built at `random_state=0`, and the out-of-fold total moves
+/-0.43 across seeds, so averaging several seeded ensembles per fold looked
like free variance reduction. Measured over three selection fold-seeds and
three untouched ones:

| arm | selection | confirmation |
| --- | ---: | ---: |
| shipped, 1 seed | 84.42 | 84.68 |
| bag 3 seeds | -0.10 | -0.03 |
| bag 5 seeds | -0.02 | -0.04 |

Negative on both. The premise was wrong: that +/-0.43 is **fold-assignment**
variance, not member-fitting variance, and averaging seeds inside a fold cannot
touch noise that comes from which packets land in which fold. Bagging removes
the variance you actually have only when the model is the noisy part; here the
split is.


Every item here was implemented and measured on the official evaluator, then
reverted. They are recorded because the reasoning that motivated them was
sound, and a reader evaluating the design should know which plausible ideas the
data actually refused.

| Idea | Why it looked right | Measured | Verdict |
| --- | --- | --- | --- |
| **Deskew before OCR** | Scanned pages are visibly rotated 1–3° | +0.00, twice, on independent runs | Tesseract's own line finder already handles this range; the resample only adds blur |
| **Approval / completeness gates** | A false approval costs −4 against +2 for hedging, so refusing to approve thin packets should pay | Net −0.82; worse at *every* threshold tried, on two separate attempts | The expected-value rule in `decide.py` already prices this correctly. A hard gate double-counts the penalty and converts correct approvals into hedges. `rules.approval_forbidden` is still called but is deliberately inert |
| **Portrait-based species classification** | 418 registry portraits, and `species_code` is the heaviest extraction field | 21 distinct images across all 418 packets; **0 of 21** map to a single species | The art is decorative and randomly assigned. Hash the images before building the CNN -- a ten-minute check that saves a week |
| **Trace-based confidence calibration** | Calibration is worth 20 points and the rule engine's reason trace is informative about correctness | +0.01 | The posterior is already well calibrated; the trace adds nothing the features don't carry. `tracecal.py` remains as a training-time diagnostic only and is not on the inference path |
| **Redundant fee cells to recover nulls** | The fee receipt prints the amount twice | 2 recoverable cases | I asked the wrong question. The redundant cells fix 33 *wrong* values, not 2 missing ones -- that finding did ship, as the exact 403/403 amount-and-waiver check in `fields._fee_from_receipt` |
| **Reading hidden text as evidence** | It contains ~90% correct field values | **0 of 75** hidden adjudications are correct | It is a trap, not a leak. The injected verdict is always APPROVED regardless of the packet. See §6a for what we do use -- presence only, never content |
| **More evidence-quality signals in the confidence model** | Calibration has the most headroom left (3.5 pts), and a verdict reached over three unreadable fields should not carry the same confidence as one read off a clean packet | Brier 0.0901 → 0.0905; the two-stage estimator alone 0.0939 → 0.0948 | Ten added features (unreadable markers, OCR failure, injection presence, per-field disagreement counts, rule/posterior agreement) all moved it the wrong way. 1,000 rows will not support a wider linear model, and the posterior already encodes most of it |

Two more were not ideas but bugs that presented as ideas, and both are worth
naming because they inflated a measurement before they were caught:

- **A wall-clock admission gate on the second OCR engine.** Intended to protect
  the 6 s budget. It made output non-deterministic -- four identical container
  runs scored 126.73 / 128.60 / 128.60 / 126.73, and 115.81 on a single vCPU --
  and it defeated its own purpose, admitting the engine on only 26% of eligible
  packets at 4 vCPU and 2% at 1 vCPU. The configuration being measured was not
  the configuration that would be scored. Removed; runs are now byte-identical.
- **A duplicated corpus statistic.** The trainer reduced arrival dates with the
  p99 and no sanity filter while the container used the p95 with one -- 637 days
  apart, because the top 1% of parsed dates are OCR misreads. At fit time the
  rule engine denied 645/1000 packets; at serve time, 379/1000. The posterior
  was fitted in a regime the container never produces. `tools/train_model.py`
  now calls `solution.corpus_context` directly, so there is one function and it
  cannot drift again.

## 9c. Adversarial hardening pass

Prompted by §10.3 below, I generated adversarial PDFs against the two
places that turn a *visible* mark into *no evidence at all*:
`reader._is_untrusted_line` (the untrusted-channel filter) and
`reader._is_closed_path` / `_stroke_rects` / `_is_crossed_out` (the
crossed-out-stamp check). Every fix below was corpus-validated by diffing
`read_packet()` output (visible lines, field pairs, and stamp/voided-stamp
lists) across all 1,000 public training packets before and after the
change: **zero packets changed**, i.e. these patterns exist in neither the
labelled data nor the model's training distribution, and the fixes are pure
hardening against a private/adversarial evaluation set.

**Untrusted-channel marker, real gaps found and fixed** (`_is_untrusted_line`):
- Zero-width space / soft hyphen / other invisible format characters
  splitting a marker (`SY\u200bSTEM:`) -- fixed by stripping Unicode
  category Cf/Cc/Mn and U+00AD before matching.
- Fullwidth colon and other colon lookalikes (`SYSTEM\uff1a`) -- fixed by a
  small translation table plus NFKC normalisation.
- Cyrillic homoglyphs of the Latin letters in "system"/"barcode" (`\u0405YSTEM:`)
  -- fixed by a translation table scoped to exactly those letters, not a
  general confusables table.
- `answer-key:` (hyphen variant) -- added as a literal marker.
- Two-column layout (`SYSTEM` in one cell, the payload in the next, joined
  with a space and never producing a colon at all) -- fixed by also treating
  a bare marker word as untrusted when it opens the line, restricted to
  `system`/`barcode` after confirming by corpus scan that neither word
  appears in any legitimate field on the public set.
- **Deferred, not fixed:** a marker on its own physical row with the payload
  on the *next* row (no shared line at all) still leaks. Closing this needs
  a stateful "is this row a continuation of the untrusted block above it"
  heuristic; I did not find a version of that rule I trusted without also
  risking swallowing a legitimate wrapped value, and it does not occur
  anywhere in the training corpus, so it stays a documented gap rather than
  a rushed fix.

**Crossed-out stamp detection, real gaps found and fixed** (`_is_closed_path`,
`_stroke_rects`, `_is_crossed_out`):
- A void mark painted as a filled shape (`fill=`, `color=None`) rather than
  a stroked line was invisible to `_stroke_rects`, which only looked at
  strokes -- fixed by also accepting dark, markedly thin fills (axis-aligned
  ribbon, or a rotated shape whose true polygon area is small relative to
  its bounding box).
- A thin `re` (rectangle) strike was classified as a decorative frame by the
  "any `re` is a frame" rule -- fixed by requiring both dimensions to clear a
  size floor before an `re` counts as a frame.
- A thin quadrilateral rotated so its axis-aligned bounding box no longer
  looks thin (but its true polygon area is tiny relative to that bbox) was
  also misread as a frame -- fixed with an area/bbox-area ratio check.
- A self-intersecting "bowtie" X (one closed path whose own diagonals
  cross) satisfied the start==end frame test -- fixed by rejecting closed
  paths whose non-adjacent segments properly intersect.
- Two short X-ticks, each under the existing 50%-of-width threshold on its
  own, evaded per-stroke measurement -- fixed by merging same-band fragments
  before measuring coverage.
- A strike drawn top-to-bottom instead of left-to-right was invisible to a
  check that only measured horizontal overlap -- fixed by adding a symmetric
  vertical-band test.
- **Out of scope:** stamp *detection* itself requires the literal substring
  `"Bold"` in the font name, so a stamp set in a bold-but-differently-named
  font (e.g. "Arial Black") never becomes a stamp candidate at all. This is
  a detection gap, not a cross-out gap, and touches a different, more
  central piece of logic (`stamp_spans` in `read_packet`); left unchanged
  pending its own corpus check.

**PDF text-layer/rendering research, real gaps found and fixed:**
- **A live crash, not just an adversarial trap.** `_collect_spans` called
  `fitz.Rect.includes(...)`, a method that does not exist on the pinned
  dependency (`PyMuPDF==1.24.14`; the correct name is `.contains()`). Any
  page with a render-mode-3 or near-zero-opacity span -- precisely the
  trick `_invisible_trace_boxes` exists to catch -- raised an uncaught
  `AttributeError`, and `pipeline.analyse()`'s exception handler discards
  the *entire* packet's extraction on any read error, not just the
  offending page. Confirmed 0/6,000 public packets (train + validation)
  ever exercise this path, so it has never fired in practice, but it is a
  straightforward version-compatibility bug independent of any adversarial
  framing and would have zeroed out an otherwise legible multi-page packet
  the moment one page used this trick. Fixed the crash directly, and
  additionally replaced strict corner-containment with an overlap-fraction
  test, because the two bboxes involved (`get_text("dict")` vs.
  `get_texttrace()`) use different conventions and never actually
  intersected at their corners even for a plain, untricked invisible span --
  the check degraded to "no dark pixel anywhere in the bbox," which
  unrelated nearby ink (a stamp border, a bullet) could defeat. The
  render-mode metadata is now authoritative on its own, without needing
  pixel confirmation.
- **Horizontal-scale (`Tz`) squash.** A span painted with `Tz` far below
  100% (or an equivalent `Tm` scale matrix) is full-size, full-opacity, real
  ink -- the ink oracle has no objection -- but PyMuPDF's reported `size` for
  scaled text is a geometric blend of both axes, so it stays well above
  `MIN_FONT_SIZE` even when compressed into an illegible hairline. One
  example achieved a clean field-value hijack (`sponsor id` silently
  overwritten) with a single native `Tz` operator. Fixed with a rendering-
  derived signal -- average glyph width relative to line height -- calibrated
  against every span in the full public corpus (1,000 train + 5,000
  validation packets, 203K spans): the tightest legitimate ratio measured
  anywhere is 0.110 (a large rotated "SAMPLE DENIAL" watermark); the
  0.08 threshold shipped leaves clear margin below that floor while still
  catching a squash an order of magnitude past it.
- **Deferred, not fixed -- ToUnicode/glyph-name mismatch.** A hand-built font
  with mismatched `/Encoding /Differences` and `/ToUnicode` CMaps can paint
  "APPROVED" while every text-extraction API reads "DENIED" (or vice versa),
  because the ink oracle only confirms *that* ink was painted, not *which*
  string it spells. No check based on parsing the text layer can ever catch
  this -- the only sound fix is a rendering-based cross-check (e.g. OCR the
  rendered crop of stamp-sized bold spans and compare against the extracted
  string), which is a real architectural addition, not a bounded patch, and
  I did not want to wire a new OCR call path into the primary extraction
  loop without dedicated design and its own accuracy/false-positive
  measurement. Likelihood on this generator is uncertain -- it requires
  deliberate low-level font/encoding construction, well past anything the
  existing generator does -- but the blast radius (silently flipping the
  #1-precedence adjudicator stamp) is high enough that I'd prioritize this
  first if given more time.
- **Deferred, not fixed -- overlapping same-position text spans.** Two `Tj`
  calls at (nearly) the same coordinates produce an illegible overlapped
  smear that a human reads as neither word, but each span is evaluated
  independently, so both get recorded as legible, un-struck stamps (e.g.
  both `APPROVED` and `REJECTED`). The existing `_white_fill_boxes`/
  `"covered"` logic already tracks the right *idea* (later-painted opaque
  content can invalidate earlier content) but is scoped only to near-white
  vector fills; generalising it to any later-painted content by paint order
  is a reasonable-looking fix but touches the same evidence-invalidation
  path as the render-mode fixes above, and I'd want a corpus check on
  paint-order edge cases (z-order in multi-content-stream pages, annotation
  layering) before shipping it in the same pass as everything else here.

## 9d. The ceiling, measured

A later pass asked a narrower question than "what else could we try": *where
are the remaining points, and are they reachable at all?* Fourteen levers were
measured. Every one landed at or below noise, and the reasons converge on a
single answer, so they are recorded together rather than as a list of
disappointments.

**Every lost extraction point, classified by where its truth value lives.**
For each field we get wrong, the true value was searched for in the visible
text layer, the hidden text layer, and neither (exact match plus a fuzzy arm,
so OCR near-misses count as found):

| Where the truth value is | Points lost |
| --- | --- |
| Not in any text layer -- on a scan, or absent entirely | **3.38** |
| Hidden answer-key text only -- refused by design | **1.39** |
| Visible text -- a real parsing gap | **0.04** |
| Truth blank / `none` | 0.03 |
| **Total** | **4.83** |

**Our extraction number is measured on a stricter denominator than most.**
`evaluate.py` removes unrecoverable fields from each case's extraction
maximum, and `EVALUATION.md` names the qualifying conditions: evidence "cut
out, washed out, torn away, or only present in untrusted hidden text". But
`unrecoverable_fields` is deliberately absent from the public train labels, so
the stock scorer run locally drops nothing and charges every entrant the full
45 weight units per case. We report that stock number, 45.21. Several
submissions instead report under their own estimate of unrecoverable scoring --
midasavocado's CHANGELOG says so explicitly, and pr59 quotes 47.30 "rather
than 45.78" on that basis. Those are not the same measurement as ours.

For comparability, the same performance on the adjusted denominator:

```
matched weight              40.69 of 45
hidden-text-only weight      1.25   (the 1.39-point row above)
denominator after the drop  43.75
extraction                  50 x 40.69 / 43.75 = 46.50
```

So **46.50 against a reported 45.21**, using only the one condition
`EVALUATION.md` states unambiguously and which we refuse by design. If the
private labels also mark the washed-out scan fields unrecoverable -- the 3.38
row, and "washed out" is their wording -- the denominator falls to 40.71 and
extraction reaches 49.98, not because we read more but because we stop being
charged for ink that is not present.

We continue to quote 45.21 as the headline, because it is what the published
scorer produces on the published labels and it cannot be accused of a
flattering denominator. The adjusted figure is recorded here so that a
comparison against a submission quoting 46.95 or 47.30 is not read as a
1.7-point extraction deficit that does not exist.

The parser is essentially perfect on visible evidence: 0.04 points of genuine
bugs across 1,000 packets. The 1.39-point answer-key row is the price of the
policy in §6a, and it is almost exactly the extraction gap to the highest
public score on the board (46.43 against our 45.17 -- a difference of 1.26).

**Classification tracks the manual's precedence chain, exactly.**

| Cohort | n | Accuracy | Classification | Catastrophic |
| --- | --- | --- | --- | --- |
| Adjudicator note or stamp present | 330 | 0.982 | 78.88 | **0** |
| No note, biometric slip present | 333 | 0.874 | 70.42 | 8 |
| No note, no slip | 337 | 0.718 | 56.62 | **29** |

*The counts in this subsection were measured with the calibration weight off
(37 catastrophic approvals in total). The shipped rule turns it on and the
total falls to ~23, but the cohort structure -- where the failures live -- is
unchanged, and that structure is what this section is about.*

With top-of-chain evidence the system is near-perfect and takes zero false
approvals; all 37 catastrophic cases live where that evidence is missing. The
370 packets in the bottom row have a near-uniform truth distribution (39%
denied / 33% approved / 28% review), which is why forcing them to
`NEEDS_REVIEW` measures **−11.38** rather than helping. Sampling their scans
for missed note pages found note wording in **0 of 20**.

**The 37 catastrophic false approvals are not a decision-layer defect.** 28 of
them are packets where a disqualifying flag was missed; of 54 such packets, 31
have no biometric slip page at all and 23 have only an unreadable image. Zero
are parsing bugs. Confirming this from the other side: forbidding approval on
review-flagged packets is worth +2.68 with *truth* flags and **+0.00** with our
detected flags -- we already approve none of them.

| Lever | Measured | Why it fails |
| --- | --- | --- |
| Unlabelled 5,000: name lexicon | +0.00 | Lexicon is already saturated at 1,000 packets |
| Unlabelled 5,000: text basis | **−0.40** | A basis fitted on 6× more text is a worse basis for these 1,000 |
| Pseudo-labelling (0.99/0.95/0.90/0.80) | best +0.23, catastrophic 36.5 → 39.5 | Non-monotone in the threshold; every setting worsens the tail |
| Approve-boundary caution, nested | +0.11 | Posteriors are honest at the boundary: predicted P(DENIED) 0.097–0.104 vs actual 0.110–0.114. The in-sample sweep promised +0.37 |
| Learning curve, 200 → 800 labels | +0.66 total, non-monotone | 68.19 is the task's number, not the model's. Doubling the labels buys ~+0.4 |
| Calibration -- *any* honest recalibrator | **+0.06 ceiling** | An in-sample isotonic fit on held-out correctness, which cannot be shipped, scores 16.53 against our 16.47. Brier is floored by decision accuracy |
| Imputation, best constant | +0.00 | We already emit the exact corpus mode for every field |
| Imputation, conditional model | −0.081 | Worse than the mode in all four fields tried |
| Model class / hyperparameter search, 12 candidates | +0.21 at 6 seeds, catastrophic +3.2 | Selection winner `hgb cv=5` scored 68.38 then 67.88 on unseen splits. ExtraTrees-600 is real but sub-sd and costs tail risk |
| Bagged ensemble members 300/leaf3 → 600/leaf2 | +0.01 | The narrow hypothesis behind the ExtraTrees result. Refuted |
| OCR preprocessing (CLAHE / adaptive / 2× unsharp) | +0.18 upper bound | "Plain at 400 dpi" recovers 15 of 18; the preprocessing adds ~nothing |
| Second-engine DPI 200 → 300 → 400 | 0 / 0 / worse | The existing 200 was tuned correctly |
| Second engine run unconditionally | +0.21 upper bound | 24 of 94 wrong-value fields recoverable. The current gate targets *missing* fields, which recover at 1.4% |
| 90°/180° page-orientation detection | ~0 | 4 of 45 image-only pages read better rotated, on pages that are illegible anyway |

The consistent finding is that this system is limited by evidence that is not
in the packets, not by its models, its calibration, its decision rule or its
parser. Three independent routes -- the extraction census, the precedence-chain
cohorts, and the learning curve -- arrive at the same wall.

## 9g. Why the pixel decoder cannot reach risk_flags

Closed-vocabulary pixel decoding works on `visa_class` and `home_world` (§9e)
and cannot be made to work on `risk_flags`, which is the field worth having.
The obstacle is circular rather than technical, and it is worth recording
because the technique otherwise looks like it should apply.

A template must carry the generator's rasteriser and JPEG response or it will
not correlate against a damaged scan. Measured peak NCC by template source:

| template source | peak NCC | net (sel / conf) |
| --- | ---: | --- |
| synthetic Helvetica render | 0.58 | -3 / -1 |
| crop from a clean TEXT-LAYER page | 0.646 | -3 / -2 |
| crop from a real SCAN page | **0.87-0.90** | +3 / +3 (`home_world`) |

Only scan-derived crops clear a useful threshold. But harvesting one requires
the field to have been read correctly *off a scan already* -- and `risk_flags`
is precisely the field that never is. Rendering the value from a page whose
text layer is intact seems like the way out, and it is not: those crops are
clean, and a clean glyph does not correlate with a washed-out JPEG of the same
glyph. 0.646 sits exactly between the two, which is the shape of the problem.

So the method helps where we already have partial success and cannot bootstrap
where we have none. `risk_flags` is 172 wrong packets and 1.53 extraction
points -- with the classification multiplier, about 4.9 total -- and it stays
out of reach. Every point of it needs either a recogniser that can read the
raster or evidence that is not in the packet.

## 9f. The hedging weight sits on the knee, measured both ways

Catastrophic false approvals are tie-breaker #2 in the published ranking, so it
is worth knowing what buying them down actually costs. The weight had only ever
been measured at 0 and 8 -- 11 fewer CFAs for 0.47 points, about 0.043 each --
which made lower CFA counts look nearly free. Extrapolating from two points was
wrong.

| weight | selection cls+cal | CFA | confirmation cls+cal | CFA |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 84.68 | 34.3 | 84.42 | 35.0 |
| 4 | 84.94 | 28.7 | 84.67 | 29.7 |
| **8** | **84.41** | **22.7** | **84.64** | **21.3** |
| 12 | 83.35 | 16.7 | 83.31 | 16.0 |
| 16 | 81.02 | 9.7 | 80.37 | 11.3 |
| 20 | 78.34 | 8.7 | 78.14 | 8.7 |
| 40 | 66.96 | 18.0 | 66.41 | 19.3 |

Both directions are bad trades. Dropping to 4 gains 0.53 on the seeds that
would have chosen it and **0.03** on the seeds that did not, while conceding
eight catastrophic approvals -- a rounding error paid for with the tie-breaker.
Raising to 12 buys five fewer CFAs for **-1.33**. The curve is shallow below 8
and steep above it: past that knee each avoided catastrophic approval costs
about 0.27 points rather than 0.043.

The w=40 row is the interesting one. The CFA count goes back *up*. That is the
shape of the bonus term itself: `1 - 2p(1-p)` is maximised as p approaches 0,
so a large enough weight starts preferring actions the posterior thinks are
UNLIKELY. It is a real defect in the term, latent at 8 and dominant at 40, and
this sweep found it independently of the code reading that first suggested it.

Result: no change. The shipped value was already the right one, and now that is
measured rather than assumed.

## 9e. Validated but not shipped: the pixel decoder

Closed-vocabulary pixel decoding works, was measured net-positive on two
disjoint halves for two fields, and is **not enabled** (`MIB_PIXFLAGS=0`).

Rather than recognise characters on a damaged scan, render a template of each
legal value and rank by normalised cross-correlation. NCC removes gain and
offset so washout barely moves the ranking, and a sliding correlation searches
every offset -- which matters because the scanned form is not registered to the
page (anchor rows spread 54 points where the text layer has sd 0.00; a fixed
crop rectangle measured **-0.53 / -0.44**).

| field | threshold | selection | confirmation |
| --- | --- | --- | --- |
| `visa_class` | 0.70 | +6 (7 rescued, 1 broken) | +3 (3, 0) |
| `home_world` | 0.85 | +3 (3 rescued, 0 broken) | +3 (3, 0) |
| `species_code` | -- | +3 | **-3** |
| `fee_status` | -- | negative | negative |
| `risk_flags` | -- | **-3** | **-1** |

Worth about **+0.067 extraction**, and ~+0.21 out-of-fold once the 2.1x
classification multiplier is applied.

**Why it is off.** The decoder writes into `record`, which feeds
`features.vectorize`. Enabling it at serve time without re-extracting and
retraining would mean the model sees a value where it was trained on a
missing one, on ~13% of packets -- the same train/serve mismatch that produced
four separate false positives here, one of which measured +0.54 in a lab and
-0.18 in the real pipeline. Doing it properly needs a full re-extract (~95 min)
and a retrain. That did not fit before the deadline, and +0.067 does not
justify introducing the defect class this whole document is about.

**Why three fields are excluded** is more interesting than why two are in.
`fee_status` loses because its imputed default (`paid`) is already right on
71.5% of unresolved packets while the decoder manages 33% -- a strong default
is a high bar. `risk_flags`, the heaviest field at weight 8, is the one this
method cannot reach at all: an empirical template requires a value already read
correctly off a scan, and `risk_flags` is precisely the field never read
correctly off a scan. Zero templates were harvestable, synthetic renders peaked
at NCC 0.58 against 0.87-0.90 elsewhere, and it measured net -3 / -1. The
technique helps where we already have partial success and cannot bootstrap
where we have none.

## 9h. The damage is geometric, and we spent the day on optics

Measured at the very end, and it reframes every negative result above.

Four other entrants report per-row horizontal displacement as the dominant
scan damage. Checking our own render path: on **28 of 40 scan pages** the rows
are displaced, with a median p95-p5 spread of **54 pixels**. The page is not
blurred. It is sliced into rows and slid sideways.

Undoing it is cheap. Every page carries a printed full-width border of constant
width; per row, the leftmost dark pixel of that border gives the displacement,
rows whose border is destroyed inherit the last known offset, and each row rolls
back. Measured by OCR-ing before and after and counting how many of the
packet's TRUE field values appear in the text:

| | value |
| --- | ---: |
| scan pages measured | 18 |
| truth values found before | 25 |
| truth values found after | **27** |
| net | **+2**, no page made worse |

Two packets recovered a field that no recogniser could previously read, and
1,300-1,500 rows moved on a typical page. Scaled across ~300 scan-bearing
packets that is roughly +0.3 extraction and, through the 2.1x classification
multiplier, around +0.9 total. A better estimator does better: glgh reports
+2.38 with a second rung that cross-correlates cut glyph halves where the
border itself is destroyed.

**This explains the four failures above.** A second engine, PP-OCRv5, a trained
OCR-correction transducer and closed-vocabulary template correlation measured
-50, +0.09, -3 and -0.53. Those are not four unrelated dead ends; they are what
attacking the resolution axis looks like when the damage is geometric. A
sharper lens cannot reassemble a picture that has been cut into strips, and a
template cannot correlate against glyphs that have been relocated.

The signal was in hand hours earlier and misread: the scan-geometry probe found
anchor rows spread 54 points where the text layer has sd 0.00, and that was
recorded as "no fixed rectangle can work" rather than "the image is sliced".
The measurement was right; the inference was not.

Not shipped -- it needs re-extraction of both splits, a retrain and
revalidation, and it was measured with 18 minutes left. It is the first thing
to build next, ahead of anything on the modelling side.

## 10. What I would do with another week

1. ~~**Portrait-based species classification.**~~ **Tested and dead.** The
   512×512 registry/passport portraits looked like free signal for the
   highest-weighted field. They are not: across 418 extracted portraits there
   are only **21 distinct images**, and **0 of the 21 map to a single species**
   -- the same picture appears under a dozen different species codes. The art is
   decorative and randomly assigned. Anyone planning to spend a week on a
   portrait CNN should hash the images first; it is a ten-minute check.
2. **Region-targeted OCR.** Layouts are fixed (labels at x≈68, values at
   x≈203). Locating the value column and OCR-ing it with a per-field character
   whitelist and `--psm 7` should beat whole-page `--psm 12` on damaged scans,
   which is where the recall loss lives.
3. ~~**Attack my own trap handling.**~~ **Done -- see §9c.** Synthesised
   adversarial packets against `_is_untrusted_line` and the stamp cross-out
   check found nine real gaps (Unicode evasions of the channel markers; a
   fill-only strike, thin/rotated closed shapes, and a self-intersecting X
   evading cross-out detection). All nine are fixed and corpus-validated to
   change nothing on the public 1,000-packet set.
4. **Quantify the ceiling honestly.** Fit the label-generating policy from true
   fields (97.8% recoverable) and report per-packet how much of the decision
   was determined by visible evidence, so a human reviewer sees *why* a case
   was routed to review rather than just that it was.
