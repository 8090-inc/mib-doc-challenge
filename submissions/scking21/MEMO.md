# MIB Doc Challenge — Technical Memo

**Score on the 1,000-case public training set: 119.33 / 150** — extraction 41.70/50,
classification 62.36/80, calibration 15.27/20, 14 catastrophic false approvals.
0.82 s/PDF over the full 5,000-case validation set against a 6 s budget (4,082 s
of the 30,000 s allowance); 0.86 GiB image against a 4 GiB cap; two runs
byte-identical.

The submitted `predictions.jsonl` covers all 5,000 validation cases with no
missing ids. Its adjudication mix (41% NEEDS_REVIEW, 39% DENIED, 20% APPROVED)
matches the training mix to within a point, and mean reported confidence, 0.719,
equals training accuracy — the pipeline is behaving the same way on unseen data
as on the set it was built against.

## Approach

The pipeline is five stages, deliberately classical throughout. No LLM or VLM runs
at inference time.

**1. Ingest with a trust boundary.** Every glyph is classified visible or
quarantined at parse time — white-on-white, sub-2pt, or outside the page crop —
and downstream code only ever sees visible text. This is the highest-value
component in the build. Measured over 250 training packets, 22.4% carry an
injected answer key whose *field values are 93.2% correct* but whose
*adjudication is 0% correct*, skewed 48 APPROVED to 8 DENIED. The bait and the
punishment sit on different scoring axes: trusting hidden text is rewarded on
extraction and walks into the −4 bucket on roughly a fifth of the corpus.

Answer keys are also stripped from *visible* text. FIELD_MANUAL.md lists "fake
answer keys" separately from "hidden white text", so a key is untrusted whether or
not it is rendered. Every training injection happens to be hidden; nothing
guarantees that privately. The visible pattern is deliberately narrower than the
hidden one — it excludes `(approve|deny) this case`, because a legitimate signed
adjudicator note (the manual's rank-1 evidence) could plausibly read "Approve this
case", and redacting that would manufacture false denials.

The visible-key defence is **line-scoped, and that is a known gap**: redaction
drops the visual line carrying the marker, so a multi-line key — an `ANSWER KEY`
header with labelled fields beneath it — survives with only its header removed.
Worse, `Finding:` on a surviving line is currently accepted as rank-1 adjudicator
evidence without requiring adjudicator-note context. Every training injection is
hidden-text and therefore quarantined upstream, so this costs nothing measurable
here, but it is a real exposure on a private set that renders its decoys.

**2. OCR only where needed, in three unioned passes.** 71.7% of pages carry a
usable text layer, so OCR is gated behind a sufficiency check — 1.22 pages per
packet instead of 4.30. Three passes are unioned because each is strictly better
on some pages: the baseline `--psm 3`; a pass on an eroded render, which
reconnects stroke-eroded glyphs (it recovered `Fee Status: paid` on a receipt
where the baseline read only the header); and a sparse `--psm 11` pass, because
psm 3's layout analysis discards a speckled form as a picture block. That last
pass alone recovered the disqualifying `biohazard_red` flag on a packet the
pipeline had been falsely approving.

**3. Extraction, strategy chosen per field.** Distinctive closed enums are scanned
across the whole page; ambiguous vocabularies (`fee_status`, `declared_purpose`)
require label anchoring, because "paid" is a substring of "unpaid". Values are
snapped to vocabulary with fuzzy matching so OCR damage is repaired rather than
dropped. Labels are fuzzy-matched too, but only as a fallback, since OCR mangles
labels as readily as values (`Applicant:` reads as `icant:`).

Two structures in the corpus needed explicit handling. A **manual correction note**
(`Manual correction: applicant is Soldane Ludane`) appears on 136 of 1,000 packets
and supersedes the form field it names — the manual ranks a signed note first,
above intake form fields at rank 2. And the **sponsor attestation letter** states
the applicant in prose with no label at all (`attests that <name> is expected`),
which is safe to match only because the value is pinned on both sides by template
text.

**4. Policy as a declarative cascade.** `rules/policy.yaml` orders ~11 named
terminals (`clean`, `med3_no_check`, `embargoed_dip`, `fee_waived_nondip`, …);
`mib/policy.py` holds one predicate per terminal. Keeping the ordering declarative
made the policy auditable against FIELD_MANUAL.md line by line.

**5. Expected-value decision layer.** Argmax is the wrong rule under this rubric.
Writing p, q, r for P(APPROVED), P(DENIED), P(NEEDS_REVIEW):

```
EV(APPROVED) = 8p − 4q + r      EV(DENIED) = 8q + r      EV(NEEDS_REVIEW) = 2p + 2q + 8r
```

Class posteriors are fitted per terminal, conditioned on how much decisive
evidence was actually recovered — that conditioning is what stops the rule
approving packets it merely failed to read. Confidence is reported as the
posterior mass on the chosen class, which is the Brier-optimal report; an earlier
build multiplied it by an evidence factor, and removing that gained 1.07
calibration points. Two fitted recalibrations were tried on top and both lost
under 5-fold CV, so the posterior is reported unmodified.

## Failure modes

**The headline extraction gap is mostly not recoverable.** Every miss was triaged
by where the truth value actually lives. Measured at an earlier checkpoint of
40.56/50, the 9.44 points then outstanding split as:

| | points | |
|---|---|---|
| visible, we misread it | 1.82 | the only real target |
| present only in quarantined text | 2.68 | recovering these means following an injection |
| absent from the page entirely | 4.93 | EVALUATION.md drops many of these from the case maximum |

That triage is what directed the rest of the work — extraction has since moved to
41.70, so roughly two thirds of the genuinely recoverable pool has been taken, and
two fields (`home_world`, `species_code`) had **zero** recoverable misses to begin
with. Chasing the headline number instead would have meant optimising against
evidence that is either forbidden or absent.

So the local extraction score is a **lower bound**: `train_labels.csv` omits the
admin `unrecoverable_fields` column, and the evaluator charges for fields the real
scorer excludes. One packet carries `fee_status=paid` in truth with no fee receipt
page at all.

**Over-hedging is the largest classification loss, and it is close to
irreducible.** 157 cases hedge to NEEDS_REVIEW when truth is APPROVED or DENIED —
9.42 of 80 points, versus 1.68 for the 14 false approvals. The −4 penalty draws
the eye, but hedging costs five and a half times more. The EV rule is optimal
*given the posterior*, though, so the only lever is sharper conditioning, and six
schemes were tested under identical 5-fold CV. Every one that meaningfully cut
hedging bought it with false approvals (a confidence floor gained 0.44 points for
+10 FAs; adding OCR-load *lost* 0.96 points and added 12). Every FA-neutral scheme
gained ≤0.18 points against a fold-to-fold standard deviation of 1.61 — an order
of magnitude inside the noise. Further, roughly a third are
`arrival_date_missing`, where FIELD_MANUAL.md:73 *prescribes* NEEDS_REVIEW;
hedging there is compliance, not error.

**The 14 residual false approvals are dominated by unreadable evidence.** For 9 of
10 flagged cases the truth flag appears in neither visible nor quarantined text.
One case carries it in hidden text only, where the manual forbids trusting it —
using it would be following the injection.

**Known weak spots.** Damaged-label recovery is heuristic and tuned on one corpus.
The free-text name reconciliation assumes OCR variants of one name cluster more
tightly than two different people on the same packet, which held here but is not
guaranteed. Erosion repair helps speckled pages and hurts tight glyph pairs, which
is why passes are unioned rather than substituted.

## With another week

1. **Multi-applicant packets.** FIELD_MANUAL.md warns a packet can contain pages
   for more than one applicant and the active `case_id` decides which. Nothing in
   the pipeline enforces that today; field resolution votes across all pages
   regardless of whose page it is. This is the clearest correctness gap.
2. **Page-type classification.** Every page is currently treated as an
   undifferentiated bag of labels. Classifying pages (intake form / biometric slip
   / sponsor attestation / registry extract / adjudicator note) would let field
   resolution follow the manual's precedence order explicitly instead of by vote,
   and would fix (1) as a side effect.
3. **Better use of the damage markers.** The corpus prints explicit markers
   (`[NAME CUT OUT]`, `[DATE WASHED OUT]`). Detecting them would let the pipeline
   distinguish "unreadable" from "absent" and report calibrated uncertainty rather
   than an empty field.
4. **Cross-page evidence conflict.** Where two pages disagree on a decisive field,
   the resolution is a confidence vote. It should be the manual's precedence list.

## Notes on method and tooling

Development used local and free-tier hosted models as **analysis instruments
only** — reading rendered pages to find what the deterministic OCR was missing,
and triaging failures. Two false approvals were located that way, and one was
fixed by a purely deterministic OCR change as a result. **No model of any kind
runs in the submitted pipeline**, which is offline, CPU-only, and free of network
calls; EVALUATION.md:70 forbids it and the runtime is clean. No validation answers
are hardcoded, no lookup tables are keyed to case ids, and no absolute paths
appear in the runtime path. Case ids that appear in source comments record which
packet motivated a measurement; no behaviour depends on them.

Every number in this memo is measured on the public training set with the
challenge's own `scripts/evaluate.py`, not estimated.
