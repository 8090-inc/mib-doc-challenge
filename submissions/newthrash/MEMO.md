# Technical Memo — Evidence-Provenance Intake Pipeline

## Result

Offline, CPU-only, deterministic. Scored with the organizers' `evaluate.py`
through `run_docker_submission.py` under the published contract.

| | Training set | Out of fold |
| --- | ---: | ---: |
| Field extraction | 41.63 / 50 | 41.63 / 50 |
| Classification | 60.93 / 80 | — |
| Calibration | 15.89 / 20 | — |
| **Total** | **118.44 / 150** | **116.82 / 150** |
| Catastrophic false approvals | 1 | 1 |

The out-of-fold column is the number I would bet on. Each held-out packet is
scored by a calibration table fitted without it, across five folds. The
training column is in-sample and optimistic; I report both because the gap is
the part most easily mistaken for progress.

Runtime 0.95 s/PDF against a 6 s budget, image 0.15 GiB against 4 GiB, 1000/1000
structurally valid rows, no missing, extra, duplicate or invalid records.

## Approach

**The rendered page is the trust boundary.** Native PDF text is extracted span
by span and kept only where a human reviewer would see it: inside the crop box,
above a minimum size, with real luminance contrast against white. White-on-white
answer keys, off-crop decoys and invisible render modes are dropped at ingestion
and recorded as a document-quality signal. They can never populate a field or
reach a decision — not by policy, but because they are gone before any parser
runs.

**Half the pages carry a usable text layer and half are raster.** Native text is
exact and free where present; OCR (Tesseract, PSM 3 primary) covers the rest with
a bounded escalation ladder — contrast stretch, then a 300 DPI pass, then a
rotation probe — each rung gated on whether form anchors were actually recovered,
so clean pages pay one pass.

**Adjudicator stamps are vector graphics, not ink.** `page.get_drawings()` reads
them exactly: no rasterization, no threshold to tune. On public training data a
green stamp is APPROVED 17/17 and a blue stamp NEEDS_REVIEW 21/21, covering 20%
of packets at 91% precision. Red is 83%, the shortfall being the documented
rescinded-denial trap, so a stamp crossed by a cancellation stroke is not a live
verdict and disagreeing stamps resolve to a contested path rather than a winner.

**Nearly every field is closed-vocabulary**, which turns extraction into
classification. Readings are snapped with a glyph-confusion-weighted edit
distance that refuses ambiguous matches. Refusing is the point: `home_world`,
`species_code` and `declared_purpose` have zero incorrect readings across 1,000
packets. Two snapping rules are deliberately asymmetric — a damaged `unpaid` can
never resolve to `paid`, because that single confusion converts a denial into an
approval; and a visa class resolves from its suffix digit (2, 3 and 7 are unique
keys) but still requires its letters where digit 1 is shared, since a wrongly
inferred `DIP-1` would grant a sponsor exemption never earned.

**Policy is a named decision path, an empirical distribution, and an
expected-value choice.** `decision_path` maps trusted evidence to one of ~25
states; each carries an outcome distribution fitted out-of-fold on *extracted*
records — not gold fields, which would be a train/serve mismatch; the decision
maximizes expected value under the evaluator's payoff matrix, and the reported
confidence is P(this decision is correct), exactly what the Brier term scores.

**Approvals are fail-closed.** Raw expected value is optimal against a known
distribution; ours is a sample estimate whose errors are not symmetric. An
approval must clear the denial mass by 1.5x, and paths that exist *because*
evidence was missing cannot approve at all. This was not theoretical: when the
calibration table was first fitted honestly, evidence-poor paths began approving
and catastrophic false approvals went from 0 to 18. The margin brought them back
to 1 for 0.8 classification points.

**Guessing is separated from evidence.** Fields with no trusted reading are
filled with a per-field empirical prior *after* adjudication and *after* the
one-way guardrail has inspected the evidence-backed row. A filled slot cannot
support a decision or suppress a demotion. Both properties are regression-tested.

## Designed to transfer

The private set decides the ranking, so constants mined from public labels are a
liability. Wherever possible the pipeline derives them from the corpus it is
scoring:

- **Revoked sponsors** are frequency outliers — genuine sponsors are near-unique
  while revoked ids recur at 6–40x the 99th percentile. The three published ids
  and three more are recovered without a lookup table.
- **The staleness epoch** comes from the corpus arrival-date distribution, not a
  hardcoded date.
- **Embargoes are read, not matched.** `Registry Status: EMBARGO REVIEW` is 93%
  DENIED and appears for three different home worlds; a mined world list was
  already wrong on training data and would fail silently on unseen worlds.
- **Stamps** are read from drawing operators, so there is no pixel threshold to
  overfit.

## Failure modes

**Extraction is at its evidence ceiling, not its engineering ceiling.** Most
remaining misses are blanks because the page does not exist: of ~410 packets
whose fee status cannot be read, 98% contain no fee receipt at all. These are the
fields `EVALUATION.md` describes as genuinely unrecoverable.

**`risk_page_absent` (108 packets) is a deliberate loss.** 63 are truly APPROVED
and we route them to review. No available signal separates them from the 17
denials whose disqualifying flags sit on the absent page, and approving the group
would create 10–17 false approvals. Organizer guidance on issues #4 and #5 states
that NEEDS_REVIEW is the intended answer when missing risk evidence is
outcome-determinative. This is a decision, not an oversight.

**Calibration is bounded by accuracy, not by technique.** Reported confidence
matches observed accuracy at every level (0.3 → 0.26, 0.6 → 0.60, 0.9 → 0.95),
and measured Brier already beats the perfect-calibration floor for this accuracy.
There is no calibration headroom to recover; the section score rises only when
classification does.

**Known regression.** Ranking candidates by document precedence improved four
fields and moved `applicant_name` from 113 to 125 wrong readings. Net positive
and shipped, but not yet understood.

**A hypothesis I got wrong.** I attributed wrong applicant names to the
multi-applicant packet trap and implemented case-scoped page filtering. A scan of
all 1,000 packets found 2 mentioning a foreign case id, both placeholders. The
code was reverted rather than kept as harmless — a mangled case id would have
excluded legitimate pages. The real cause was tie-breaking by page position,
which let an unclassified page outrank a biometric slip.

## With another week

1. Resolve the applicant-name regression, then extend page-type precedence to
   conflict *detection* — a disagreement between intake form and sponsor letter
   is evidence for `identity_conflict`, which we currently only read rather than
   infer.
2. Estimate the OCR confusion matrix from the corpus itself. Digital pages supply
   thousands of aligned (native text, OCR output) pairs for free; that error
   model would replace my hand-picked confusable list and improve every snap.
3. Use the case id printed in every page footer as known plaintext to measure
   per-page OCR quality directly, rather than trusting Tesseract's self-report,
   and weight conflicting evidence by it.
4. Drive the last catastrophic false approval to zero.

## Provenance

No LLM, VLM or network access at runtime. No hardcoded case answers, no filename
dependencies, no validation lookup tables, no use of the hidden answer-key
channel. Design ideas adapted from public MIT-licensed solutions are credited in
`ATTRIBUTION.md`; the implementation is my own.
