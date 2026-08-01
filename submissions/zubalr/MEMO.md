# MIB Doc Challenge: Technical Memo

## Result

| Section | Training set | Model-fold diagnostic |
| --- | ---: | ---: |
| Extraction | 45.31 / 50 | 45.31 / 50 |
| Classification | 74.45 / 80 | 68.82 / 80 |
| Calibration | 18.07 / 20 | 16.81 / 20 |
| Total | **137.83 / 150** | 130.62 / 150, SE 0.12 |
| Mean confidence Brier | 0.0482 | 0.0797 |
| Catastrophic false approvals | 12 | 20.6 |

The training-set column is the shipped Docker image scored on all 1,000 labeled
packets with the official evaluator. It is reproducible and in-sample: the model
was fitted on those rows, so it measures reproducibility rather than expected
performance.

The second column is a diagnostic on the classifier only, and it is worth being
precise about what it does not cover. The gradient-boosting model is refitted on
each training split, so no held-out packet contributes to the model scoring it.
The deterministic path calibration is not refitted: it is estimated once over
all 1,000 packets and then enters both the blend prior and the path features. A
held-out packet therefore influences its own prior, which makes this an
optimistic bound on held-out behaviour rather than a nested estimate. It is
reported because the gap against the in-sample column is informative about
model optimism, not as a prediction of the private score.

Extraction is identical in both columns because it does not depend on the model
at all.

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
single-line notes, and dense blocks require different OCR layouts. A second
local engine, RapidOCR, reads the same raster and contributes only when the
primary engine left a field unresolved. Its observations carry a lower trust
rank and cannot displace a primary reading. Repeated out-of-fold evaluation
allowed its printed values and fee evidence, but rejected its general policy
fields, risk flags, and panel state. A direct visible `Finding:` can act as a
final override only when the packet contains no injection signal; it remains
outside the model feature set and training partition. Field parsers apply
structural validation before any value enters the evidence set.

Most categorical fields have small, fixed vocabularies. OCR output is matched
with weighted edit distance that gives lower cost to common glyph confusions
such as `0/O`, `1/I`, and `5/S`. Values outside a safe threshold remain
unmatched instead of being forced onto a known token. For printed output the
match is applied per trust tier rather than once at the end, so raw debris at a
higher rank cannot hide a valid reading below it, and within a tier repeated
agreement decides before plausibility does.

Three parser gaps were found by auditing what the documents state against what
the pipeline recorded, rather than by searching for correlations in the labels.
A typed note's `Finding: ... Reason: ...` was matched one span at a time, so a
reason clause that wrapped onto the next line lost everything below the first;
reading the page as a single blob recovers it, and the recovered clause is
admitted only on packets with no injection signal, since a spoofed flag cannot
approve anything but can deny a clean packet. A compound flag token damaged by
OCR failed whole-token snapping, and merely relaxing that threshold is unsafe --
`planetary_registry` page furniture snaps straight onto `planetary_embargo` --
so a relaxed match must additionally preserve its terminal component, the part
naming the thing observed, which keeps `sor_mismatch` while rejecting the
collision. Finally, the typed receipt path parsed the `Amount` field and
discarded it while the scanned path had always derived a fee status from the
same two numbers; both paths now share one function, since two implementations
of "what does this receipt mean" is exactly how they came to disagree. Together
these add 23 correct risk flags with no false additions, correct 21 fee
transcriptions with no regressions, and make 19 packets newly exact.

The fee correction is confined to printed output. Letting the same geometry
reach the policy `Record` measured -0.073 on the held-out diagnostic: a fee that
was `unknown` for want of evidence would start unlocking approvals, which is the
conservative hedge the sentinel separation below exists to protect.

Two further resolvers run on the printed side only, after the `Record` is
closed. The first uses corroboration rather than precedence. Resolution picks a
single best value per trust tier, which is the right rule for a contradiction
and blind to agreement: a sponsor letter's applicant independently read on a
scan, a sponsor id both engines found on different physical pages, or a name
repeated across scan reads is stronger evidence than whichever value won its
tier. The second reads individual recognition boxes. The fallback engine detects
text regions and recognises each crop separately, then joins them into lines so
the ordinary `Label: value` parsers can work; that join is also lossy, because a
clean crop beside a row of speckle becomes a line no parser accepts. Keeping the
per-box confidence and geometry allows a field to be recovered from the box
alone, gated on high recognition confidence, a label within a bounded edit
distance, and agreement among every box that qualifies.

Both resolvers are barred from policy by construction rather than by
convention: they run after the `Record` exists and write only to the printed
dictionary, and the test suite asserts that the `Record` and the feature vector
are byte-identical with and without them. Corroboration for a recognition box
must come from the primary engine, so the fallback engine cannot promote its own
reading over a primary one through this path.

Applicant identity has a separate output-only repair for the documented
multiple-applicant trap. When there is no manual correction and the packet has
one unambiguous visible `Registry Name`, that identity is printed instead of a
conflicting intake name. The rule changes no policy field or adjudication.

Sponsor placeholders receive the same output-only treatment after every packet
has been assembled. An unresolved placeholder is replaced with the most common
valid sponsor ID observed in the current corpus. The corpus value never enters
the policy record, so it cannot change revocation handling or adjudication.

One inference is deliberately confined to the printed side. The registry prints
a single embargo status and whether it means a planetary embargo turns out to
depend on the applicant's world, which the field manual does not state and only
the labels reveal. A rule read off the labels will not necessarily hold on a
corpus generated from another era, and the failure mode matters: withholding a
disqualifying flag is what turns a denial into an approval. So the world rule
shapes the transcription and the policy record keeps the flag unconditionally.
That placement is worth 0.07 extraction points; letting the same rule reach the
record gave back twice that in classification and calibration.

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
classifier. Its inputs describe extracted evidence, aggregate coverage, page
structure, OCR quality, document damage, temporal margins, and the deterministic
path prior. Redundant path one-hots and sparse field/flag indicators are
excluded after repeated held-out ablation favored the smaller representation.
It does not receive a case ID, filename, or hidden answer content.

The classifier is blended with the deterministic path distribution, retaining
the policy prior's stability while letting the model separate cases that share a
coarse path. If the artifact cannot be loaded, the deterministic policy remains
a working fallback.

One boundary remains deterministic after model inference: the model cannot
approve a packet whose risk page exists but could not be read. It selects the
better of DENIED and NEEDS_REVIEW under the same payoff matrix. Out of fold this
raised the total by 0.30 points and reduced catastrophic false approvals from
26.8 to about 20. No global confidence threshold was added: the same rule
applied to every path scored worse.

Training excludes cases settled by an adjudicator note, since those never reach
model inference. Both the estimator and the blend weight are selected on the
challenge's own objective over held-out predictions, using a
one-standard-error rule.

That rule ranks candidates on a 100-point proxy over the 644 packets the model
actually sees, which cannot observe extraction, the 356 note-settled packets, or
the catastrophic-false-approval count. Inside one standard error it therefore
has nothing left to say, and a rerun can swap the estimator on a margin of about
0.1 points. The final pair was chosen instead by repeated out-of-fold scoring on
the full 150-point objective, where it leads the alternatives tried and is
pinned so a refit cannot quietly re-roll it.

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
Typed intake/registry name disagreements occur in 2.1% of training packets and
1.64% of validation packets, so the identity repair does not expand on the
unseen corpus.

## Failure modes

**Unreadable risk panels dominate the residual error.** `risk_flags` is wrong on
167 of 1,000 training packets, and 153 of those are cases where the panel could
not be read at all and the pipeline emitted nothing. It is the highest-leverage
field in the corpus: weight 8 in extraction, and an input to the decision path,
so a miss costs roughly five times its face value.

Emitting nothing is not an abstention. The evaluator compares normalised flag
sets, and an empty set normalises to `none` -- the same value a genuinely clean
packet produces. A blank is therefore an active claim that the packet carries no
flags, which is why it is scored, and why the residual above is a real loss
rather than a gap in coverage.

That loss is not recoverable from the packets. The most commonly missed flag,
`illegible_biometrics` (102 cases), is also the most plausibly derivable, since
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
outright and is correct on all 356 packets where the primary engine reads one.
The lower-trust engine recovers two more direct findings on injection-free
packets. Roughly thirty further pages are probably notes but survive no
combination of rotation, crop, contrast or deskew tried; those packets fall
through to the model.

**The model handles the genuinely ambiguous remainder.** 644 packets reach it.
Its held-out score exceeds the deterministic path baseline, and its confidences
are better than a constant predictor. The residual is therefore more constrained
by missing evidence than by the final calibration layer.

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
needs a specialized image model for damaged panels rather than another general
OCR pass. The independent fallback engine recovers ordinary fields well but
adds almost no missing risk flags.

**Cross-corpus calibration validation.** The classifier uses extraction quality
and damage features, but only labeled public packets are available for checking
its probabilities. A labeled corpus from a different generation would give the
best evidence for whether further calibration is warranted.

## Reproducibility

The runtime is fully offline with pinned dependencies: PyMuPDF, Tesseract,
RapidOCR, NumPy, and scikit-learn. No LLM, VLM, cloud OCR service, network
request, or API key is used. Both figures below are measured, not projected,
under the submission constraints (`--network none --cpus 4 --memory 8g
--read-only --tmpfs /tmp`): the 1,000 public packets ran in 39m09s, 2.35s per
PDF, and the 5,000 validation packets in 3h49m, 2.76s per PDF. Both are inside
the 6s per-PDF budget, and the validation total sits against an 8h20m limit.

The adjudicator must be fitted on evidence extracted **inside the image**. The
container's Tesseract and the host's do not read damaged scans identically --
across the public corpus they disagree on 84 arrival dates and enough else to
move 30 adjudications -- so a model trained on host-extracted features meets a
shifted distribution at inference. Doing this the wrong way round costs about
1.9 points and produces no error, only a lower score: extraction still looks
correct, while classification and the false-approval count quietly degrade.
`tools/build_cache.py` is therefore run through the built image, not the host
interpreter.

`tools/check_env.py` asserts that the training and runtime scikit-learn versions
match, since a cross-version model unpickles with a warning rather than an error
and still produces plausible output. `tools/verify_image.py` confirms the built
image contains the current source and policy artifacts. The test suite covers
visibility classification, OCR parsing, vocabulary matching, schema validation,
and end-to-end output generation.
