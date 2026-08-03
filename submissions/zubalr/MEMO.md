# MIB Doc Challenge: Technical Memo

## Result

| Section | Training set | Model-fold diagnostic |
| --- | ---: | ---: |
| Extraction | 45.37 / 50 | 45.37 / 50 |
| Classification | 74.45 / 80 | 68.82 / 80 |
| Calibration | 18.07 / 20 | 16.81 / 20 |
| Total | **137.89 / 150** | 130.62 / 150 |
| Catastrophic false approvals | 12 | 20.6 |

The first column is the shipped image scored on all 1,000 labeled packets by the
official evaluator. It is in-sample and measures reproducibility, not expected
performance. The second refits the classifier on each split but not the path
calibration, which is estimated once over all packets and then enters both the
blend prior and the path features, so it is an optimistic bound rather than a
nested estimate. Extraction is identical in both because it uses no model.

## Reading the evaluator

Three choices follow from the scoring code rather than the prose. Every packet
must emit a record, because a missing one forfeits its own denominator, so
failures emit a schema-valid fallback. A blank field scores exactly as a wrong
one, since an empty flag set normalises to `none`, so unresolved fields take
conservative defaults that are held apart from policy evidence and can never
justify an approval. Adjudication maximises expected value against the payoff
matrix, where the asymmetric penalty on a false approval makes NEEDS_REVIEW the
right hedge more often than intuition suggests.

A fourth follows from a clause the public labels cannot exercise: the evaluator
removes a field from a case's extraction maximum when its visible evidence was
destroyed or survives only in untrusted hidden text. Of the values this pipeline
gets wrong, two are recoverable from legitimate visible text; every other one is
absent from the document or present only inside a planted key. The residual is
therefore almost entirely fields that a scoring pass holding that column does not
count, which is why no further effort went into transcribing destroyed regions.

## Approach

Every observation carries its page type, source type, visibility, extraction
method, and trust rank, and resolution follows the field manual's precedence
order. Pages without a reliable text layer are rendered and read locally with
Tesseract across several page segmentation modes. Two further local engine
generations read the same raster and contribute only where the primary engine
left a field empty, at a lower trust rank that cannot displace a primary reading.

Closed vocabularies use a weighted edit distance discounting common glyph
confusions such as `0/O`; values outside a safe threshold stay unmatched rather
than forced onto a known token.

The strongest structural decision is that transcription and policy are separate
permissions. Several repairs, including corroboration across trust tiers,
per-box recovery from the second engine, the multiple-applicant identity rule,
sponsor placeholder resolution, and a registry embargo rule that depends on the
applicant's world, run only after the policy `Record` is closed and write only to
printed output. The test suite asserts the `Record` and the feature vector are
byte-identical with and without them. This matters because the failure that
turns a denial into an approval is exactly a transcription convenience reaching
policy, and a rule inferred from labels may not hold on a corpus from another
era.

## Adversarial content

Hidden content is classified from PDF structure, not keywords: render mode,
opacity, foreground colour against the page background, and position relative to
the visible crop. The white threshold sits below pure white because near-white
is used to evade exact-white checks. Barcode payloads and prompt-like directives
are recorded as document-quality signals and quarantined; the separation
survives OCR, since rendering a page does not make hidden text visible.

The planted keys are not merely untrusted, they are inverted, and that is
measured rather than assumed. Across every training packet whose hidden key
states an adjudication, it disagrees with the truth in all of them, and usually
claims an approval where the truth is a denial. Transcribing those keys does not
gain nothing; it inherits the most expensive error the payoff matrix defines.
Their field values are more tempting because they agree with truth on the public
split, but they name precisely the fields whose visible evidence was destroyed,
which is the set the extraction maximum drops.

## Adjudication

Deterministic rules settle high-confidence evidence: an explicit adjudicator
finding, a disqualifying flag, the transit-class rule. Missing evidence is
represented explicitly rather than as a clean result. Remaining cases go to a
calibrated gradient-boosting classifier over document evidence, coverage, page
structure, OCR quality, damage, and temporal margin, blended with the path
prior. It never receives a case ID, filename, or hidden content. One boundary
stays deterministic after inference: the model cannot approve a packet whose
risk page exists but could not be read, which out of fold gained 0.30 points and
cut false approvals from 26.8 to about 20. A global confidence threshold was
tried and scored worse on every path.

## Generalization

The closed vocabularies produced zero new values across the 5,000 unseen
packets, which is the assumption vocabulary snapping rests on. Fallback rates
moved under half a point on every field and mean confidence by 0.005.

## Failure modes

Unreadable risk panels dominate. `risk_flags` is wrong on 167 of 1,000 packets,
153 of them cases where nothing could be read. It carries weight 8 and feeds the
decision path, so a miss costs several times its face value. That loss is not
recoverable: none of the missing flags appears in legitimate visible text, most
appear nowhere in the file, and the rest only inside a planted key. Conditioning
on an unreadable biometric gives 22.5% flag incidence against a 22.3% base rate,
so failing to read carries no information, and the pipeline does not treat
absence as evidence of a clean record.

The twelve false approvals are uncertainty, not overconfidence. Ten are packets
whose disqualifying flag sits on an unreadable panel, and all twelve are emitted
at confidence between 0.52 and 0.68. Buying the count down was priced out of
fold: demotion removes them at roughly 0.07 to 0.15 total points each, and since
classification score is itself the first tie breaker, spending it to improve the
second is self-defeating.

## What another week would buy

Risk-panel image recovery is the only lever with points behind it, and it needs a
model specialised to damaged panels rather than another general OCR pass, since
the panels defeating three engines are degraded past yielding a page title. Then
a systematic audit for sentinel collisions, after one in `fee_status` proved
worth about a point. And a labelled corpus from a different generation, the only
way to test whether the calibration holds off this one.

## Reproducibility

Fully offline with pinned dependencies. Measured under the submission
constraints: 1,000 packets in 39m09s (2.35 s/PDF) and 5,000 in 4h07m
(2.96 s/PDF), inside the 6 s budget and the 8h20m limit. Two independent runs
over the same packets produced byte-identical output. The adjudicator must be
fitted on evidence extracted inside the image, because the container's Tesseract
and the host's do not read damaged scans identically. Further engineering detail
is in `APPENDIX.md` in the solution repository.
