# MIB Doc Challenge: Technical Memo

## Result

| Section | Training set | Out of fold |
| --- | ---: | ---: |
| Extraction | 44.16 / 50 | 44.15 / 50 |
| Classification | 72.69 / 80 | 67.88 / 80 |
| Calibration | 17.07 / 20 | 16.50 / 20 |
| Total | **133.93 / 150** | **128.53 / 150, SE 0.16** |
| Mean confidence Brier | 0.0732 | 0.0874 |

The training-set column is the shipped Docker image scored on all 1,000 labeled
packets with the official evaluator. It is reproducible and in-sample: the model
was fitted on those rows.

The out-of-fold column is the estimate for unseen packets. Every held-out
prediction comes from a model that did not train on that packet, averaged over
ten fold assignments. The gap between the columns is in-sample optimism, so the
larger total should not be read as an expected score. Extraction is nearly
identical under both, as it does not depend on the model.

## Scoring behaviour

Three choices follow from reading the evaluator rather than the prose. Every
packet must produce a record, because a missing one forfeits its extraction and
classification denominator; failures therefore emit a schema-valid fallback.
Blank fields score no better than wrong ones, so unresolved fields take
conservative defaults that are held separate from policy evidence, and a guessed
field can never justify an approval.

Adjudication maximises expected value against the published payoff matrix. For
class probabilities `a`, `d`, `r`:

```text
APPROVED:      8a - 4d + r
DENIED:        8d + r
NEEDS_REVIEW:  2a + 2d + 8r
```

The asymmetric penalty on a false approval makes NEEDS_REVIEW the correct hedge
more often than intuition suggests. Reported confidence is the probability of
the chosen action.

## Evidence extraction

PDF processing starts with PyMuPDF span extraction. Every observation records
its page type, source type, visibility, extraction method, and trust rank.
Resolution follows the source precedence in the field manual.

Pages without a reliable text layer are rendered and processed locally with
Tesseract. Multiple page segmentation modes are merged because sparse forms,
single-line notes, and dense blocks require different OCR layouts. Field
parsers then apply structural validation before a value can enter the evidence
set.

Most categorical fields have small, fixed vocabularies. OCR output is matched
with weighted edit distance that gives lower cost to common glyph confusions
such as `0/O`, `1/I`, and `5/S`. Values outside a safe threshold remain
unmatched instead of being forced onto a known token.

## Adversarial content

Hidden content is classified from PDF structure rather than keywords: text
rendering mode, opacity, foreground and background colours, and position
relative to the visible crop.

The pipeline also separates visible evidence from visible instructions. Barcode
payloads and prompt-like directives never become field evidence or policy
commands; their presence is recorded as a document-quality signal and their
contents are quarantined. The separation survives OCR, since rendering a page
does not make hidden text visible and instructional payloads remain excluded by
source rules.

## Adjudication

High-confidence policy evidence is handled deterministically. Examples include
an explicit adjudicator finding, a disqualifying risk flag, and a transit-class
rule. Missing or unreadable evidence is represented explicitly rather than
treated as a clean result.

Cases without a decisive rule use a calibrated histogram gradient-boosting
classifier. Its inputs describe extracted evidence, coverage, page structure,
OCR quality, document damage, temporal margins, and the deterministic path
prior. It does not receive a case ID, filename, or hidden answer content.

The classifier is blended with the deterministic path distribution, retaining
the policy prior's stability while letting the model separate cases that share a
coarse path. If the artifact cannot be loaded, the deterministic policy remains
a working fallback.

Training excludes cases settled by an adjudicator note, since those never reach
model inference. Both the estimator and the blend weight are selected on the
challenge's own objective over held-out predictions, using a
one-standard-error rule.

## Generalization checks

The validation corpus is unlabeled, so behaviour was compared across corpora
rather than scored. Schema validation confirms one output per input with no
missing cases.

The closed vocabularies produced **zero new values** on the unseen corpus, which
is the assumption vocabulary snapping rests on. Applicant names behaved as
expected, with many unseen full names but stable component tokens, which is why
names are matched token-wise. Fallback rates moved under half a percentage point
on every field and mean confidence by 0.005; the adjudication mix shifts toward
DENIED, consistent with the validation set carrying more damaged packets.

## Failure modes

**Unreadable risk panels dominate the residual error.** `risk_flags` is wrong on
211 of 1,000 training packets, and 173 of those are cases where the panel could
not be read at all and the pipeline emitted nothing. It is the highest-leverage
field in the corpus: weight 8 in extraction, and an input to the decision path,
so a miss costs roughly five times its face value.

That loss is not recoverable from the packets. The most commonly missed flag,
`illegible_biometrics` (103 cases), is also the most plausibly derivable, since
it ought to follow from failing to read the biometrics. It does not: conditioning
on an unreadable biometric confidence gives 22.5% incidence against a 22.3% base
rate, so the failure to read carries no information about whether the flag is
set. Absence of a readable page is not evidence of a clean record, and the
pipeline does not treat it as one.

**Sentinel collisions are a recurring hazard.** `fee_status` had a value,
`unknown`, that was also the internal marker for "no trusted evidence". The two
were indistinguishable downstream, so a receipt that plainly stated `unknown`
was overwritten with a guess. Separating them was worth about a point. Other
fields use the same sentinel convention and have not been audited as closely.

**Adjudicator notes on badly degraded scans.** A signed note settles a case
outright and is correct on all 355 packets where one is read. Roughly thirty
further pages are probably notes but survive no combination of rotation, crop,
contrast or deskew tried; those packets fall through to the model.

**The model handles the genuinely ambiguous remainder.** 645 packets reach it
and it is 75.8% accurate on them. Its confidences are already better than a
constant predictor, so the residual there is bounded by evidence rather than by
calibration.

## What another week would buy

**Targeted recovery of note pages.** The largest identified pool of readable but
unread evidence. A page-template classifier used as a *trigger* for region-level
OCR, rather than as a verdict source, is the approach I would pursue; a
whole-page classifier reached high recall in prototyping but is not something I
would let decide an adjudication.

**A systematic audit for sentinel collisions.** The `fee_status` case was found
by accident and was one of the larger single gains in the project. The same
pattern plausibly exists in other fields, and the audit is cheap relative to its
payoff.

**Risk-panel image recovery.** By far the highest-value target, worth several
points if solved, and the reason the current ceiling sits where it does. It
needs image-level work on damaged scans rather than better parsing, which is why
it was not attempted inside the available time.

**Calibration conditioned on more than the decision path.** Confidence currently
keys on which policy path fired. Extraction quality and damage signals are
available and unused there.

## Reproducibility

The runtime is fully offline with pinned dependencies: PyMuPDF, Tesseract, NumPy
and scikit-learn. No LLM, VLM, cloud OCR service, network request, or API key is
used. The 5,000 validation packets ran in 2h55m on 4 vCPU, 2.11s per PDF against
a 6s budget.

`tools/check_env.py` asserts that the training and runtime scikit-learn versions
match, since a cross-version model unpickles with a warning rather than an error
and still produces plausible output. `tools/verify_image.py` confirms the built
image contains the current source and policy artifacts. The test suite covers
visibility classification, OCR parsing, vocabulary matching, schema validation,
and end-to-end output generation.
