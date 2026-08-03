# Technical Memo — Evidence-Provenance Intake Pipeline

## Result

Offline, CPU-only, deterministic. Scored with the organizers' `evaluate.py`
through `run_docker_submission.py` under the published contract.

| | Training set | Out of fold |
| --- | ---: | ---: |
| Field extraction | 43.27 / 50 | 43.26 / 50 |
| Classification | 63.12 / 80 | — |
| Calibration | 15.91 / 20 | — |
| **Total** | **122.30 / 150** | **120.56 / 150** |
| Catastrophic false approvals | 0 | 0 |

The out-of-fold column is the number I would bet on. Each held-out packet is
scored by a calibration table fitted without it, across five folds. The
training column is in-sample and optimistic; I report both because the gap is
the part most easily mistaken for progress. That gap is 1.74 points here,
which is the useful thing to compare against a number tuned on public labels.

Runtime under 2 s/PDF locally and ~4 s/PDF in-container including image build
and engine warm-up, against a 6 s budget, image 0.21 GiB against 4 GiB,
1000/1000 structurally valid rows, no missing, extra, duplicate or invalid
records. The 5,000-packet validation set runs clean under the same contract.

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

**Two engines, two trust envelopes.** A third of the raster pages embed ~144 DPI
JPEGs whose strokes run three times too thick for their glyph size: characters
merge into blobs that segment-then-classify OCR cannot separate at any
resolution. PP-OCR's CNN recognizes whole lines without segmentation and reads
many of these pages — 'FeeStatus:paid' where Tesseract returned only the page
footer. Its noisy reads of open-form values snap into wrong-but-valid strings,
though (wrong applicant names doubled in the first integration), so
second-engine text feeds only closed-vocabulary fields, where snapping filters
noise. The engine's models ship inside the wheel and were verified to load with
networking disabled.

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
to 1 for 0.8 classification points, and the two fixes below took the last of
them out.

**A DIP waiver is not a hardship waiver.** The field manual accepts a waived fee
only for `DIP-1` or a visible hardship waiver. The waiver detector credited
`DIP-WAIVER` as satisfying the second clause, which suppressed
`fee_waived_unjustified` on non-diplomatic visas and let a waived XW-2 reach the
clean path at 0.84 confidence. Every one of the 76 credited waivers on a
non-`DIP-1` visa in training is a `DIP-WAIVER`; not one is a genuine hardship
waiver. Removing the credit costs 0.06 out-of-fold points and removes a
catastrophic approval.

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

**`risk_page_absent` is a deliberate loss.** 87 packets reach review on this
path; 56 are truly APPROVED and we route all of them to review. No available
signal separates them from the 11 denials whose disqualifying flags sit on the
absent page, and approving the group would create those 11 false approvals for
1.30 classification points. Organizer guidance on issues #4 and #5 states
that NEEDS_REVIEW is the intended answer when missing risk evidence is
outcome-determinative. This is a decision, not an oversight.

**Calibration is bounded by accuracy, not by technique.** Reported confidence
matches observed accuracy at every level (0.3 → 0.26, 0.6 → 0.60, 0.9 → 0.95),
and measured Brier already beats the perfect-calibration floor for this accuracy.
There is no calibration headroom to recover; the section score rises only when
classification does.

**Approval-certifying gates were searched for and rejected.** 191 truly
approved packets sit on non-approving paths - the entire distance to the
field's strongest honest out-of-fold score. A systematic search over ~2,000
visible-evidence conjunctions, with rules fixed in advance (zero denials in
any fold, minimum coverage), surfaced 23 denial-free gates. Nearly all were
what chance predicts at that search size. The one principled gate - DIP-1
with the risk panel actually read and clean, 91% approved - still lost more
calibration than it gained in classification, so nothing shipped. The
negative result stands: with the evidence this pipeline extracts, those
approvals are not safely recoverable, and the hedging that costs them is
correct rather than timid.

**Decoy values vindicate refusing to guess.** Among packets whose field is
blank but whose label is visible, some visibly state a value that contradicts
the truth ('Visa Class: XW-1' where the case is XW-2). A greedier extractor
would emit those as confident wrong fields - the exact input that feeds a
false approval. The blanks were the better outcome.

**A parser that assumed word order approved a packet its own adjudicator had
denied.** MIB-000519 carries a Manual Adjudicator Note reading `Finding:
DENIED / Reason: Revoked sponsor: SPN-2718.` The page is legible and was
classified correctly as a manual note, but OCR of the damaged raster returns
each line's words reversed — `DENIED Finding:` for `Finding: DENIED`,
`Adjudicator Manual Note` for `Manual Adjudicator Note` — and the finding
regex required the label before the verdict. The note was therefore invisible,
the packet fell through to the clean path, and it was approved at 0.84
against a manual DENIED. Accepting the verdict on either side of its label
recovers it as `manual_denied` at 0.99. The lesson generalises past this
regex: any parser keyed on token order is one damaged page away from silently
discarding the highest-precedence evidence in the packet.

**Hypotheses I got wrong.** Three, each reverted when measurement disagreed.
(1) Wrong applicant names attributed to the multi-applicant packet trap: a
scan of all 1,000 packets found 2 mentioning a foreign case id, both
placeholders; the code was reverted rather than kept as harmless — a mangled
case id would have excluded legitimate pages. The real cause was tie-breaking
by page position, which let an unclassified page outrank a biometric slip.
(2) Ranking candidates by document authority ahead of cross-page agreement:
it silently replaced 61 correct names with names from other pages, a
regression the aggregate score masked until a per-case diff exposed it.
(3) An OCR confusion model estimated from page-footer known plaintext — the
footers supply free aligned truth on damaged rasters — correctly identified
this generator's damage cluster (thin vertical glyphs: e, i, l, r), but
adding the measured pairs did not survive out-of-fold measurement. The tool
and the finding remain in the repository; the change does not.

**A hypothesis I got wrong twice, in opposite directions.** I had recorded
horizontal strip displacement as measured and disproven: realignment recovered
1,713 body characters against 2,672 untouched, 21 pages worse and 1 better,
and the full-width rules were continuous in the original — which they would
not be had the page really been cut and slid. That disproof was itself wrong.
Each rule is ~6px tall and sits entirely inside one strip, so it is
structurally incapable of revealing displacement *between* strips; the check
could not have detected the effect it ruled out. What settles it is a
structure tall enough to span a boundary. On MIB-000006 page 2 the SAMPLE
DENIAL watermark is cut across rows 704–708 with the lower half displaced
-88px at 0.92 correlation, and realigning makes the watermark, the ruled grid,
the stamps and an embedded portrait photograph all coherent at once. A
photograph does not reassemble by coincidence. The original estimator was also
broken independently — it correlated rows with `np.roll`, which is circular,
so content leaving one edge matched itself at the other.

The corrected version fits one robust line (`DIST_L1`) to the page's left
margin and snaps every row to it, giving each row an absolute target rather
than accumulating relative shifts down the page, and handling skew for free.
Applied to every raster page it is still a disaster — 10,717 body characters
down to 5,265 — because it rescues pages that read as nothing and shears pages
that read fine. Gated behind the same anchor test as the other rungs, with the
realigned read kept only when it scores better, it recovers +43 form anchors
over 152 pages and rejects itself on 101 of 151 attempts. It also runs the
whole cache *faster* (2.0 s/PDF against 3.1), because pages that recover their
anchors early stop paying for the expensive rungs below.

**Measured and not shipped, this round.** A learned confidence model over
thirteen evidence-quality features, fitted five-fold out of fold, improved
Brier from 0.10067 to 0.09597 — 0.19 calibration points, not worth a new model
artifact of unknown transfer. And a from-scratch glyph-keypoint OCR engine,
gated to fire only where both existing engines fail, changed extraction on
zero of the packets it fired on while adding 2.2 s to a packet already at
8.2 s; its architecture assumes each glyph is an individually localisable
object, which is precisely what fused strokes destroy.

**Constrained recognition was validated and still not shipped.** Pixel
analysis of the corpus rasters shows why OCR fails them at any resolution:
~144 DPI embedded JPEGs whose stroke width nears a third of x-height, merging
adjacent glyphs into word-shaped blobs with nothing to segment. The
check-reader remedy - correlate rendered, equally-degraded candidates against
the cell - measured 8/40 recovered, 0 wrong on fee cells OCR had failed. It
still reverted under the standing criteria: corpus-wide coverage was ~6 cells,
and precision did not transfer to vocabularies whose candidates share a
silhouette - the first smoke test matched DIP-1 against an XW-1 cell, a
policy-critical wrong answer, and long-word fields lost their zero-wrong
property. The recognizer remains in the repository with its numbers.

**The container is part of the system.** After adding the second engine, the
rebuilt image produced structurally valid output for 25 packets in 3.3 seconds
— the only tell that OCR never ran. Its opencv dependency needed libGL, absent
from slim images; the import failed, and the same per-page error isolation
that protects a batch from one corrupt PDF swallowed the failure silently.
Local measurements were all valid; only the offline contract test exposed it.
Robustness features hide infrastructure failures, so the contract test is not
optional.

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
4. Build the approve-or-review twin of the existing resolver. The hedge pool is
   where the remaining points are and I can now size it exactly: 159 packets on
   five evidence-gap paths, 105 of them truly approvable, worth +2.69
   classification points if approved outright — and 17 catastrophic false
   approvals if approved outright. I tested thirteen features for a rule that
   separates those 17; all but two sit at the 11% pool base rate, and the best
   filter still buys one catastrophic approval per 0.15 points recovered. A
   learned model consulted approve-or-review, trained out of fold with a
   precision threshold well clear of the 50% break-even, is the only version of
   this I would trust — and it is a week's work with proper validation, not an
   afternoon's threshold change.

## Provenance

No LLM, VLM or network access at runtime. No hardcoded case answers, no filename
dependencies, no validation lookup tables, no use of the hidden answer-key
channel. Design ideas adapted from public MIT-licensed solutions are credited in
`ATTRIBUTION.md`; the implementation is my own.
