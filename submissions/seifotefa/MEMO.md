# Technical Memo — MIB Doc Challenge

## Architecture

The code is a typed evidence engine rather than a procedural pipeline, in one
package whose dependencies run strictly one way. `raster.py`, `hidden.py` and
`sanitize.py` are the acquisition primitives; `reader.py` owns the two-rung
ingestion cascade over them; `decoder.py` maps pages through declarative
specifications into immutable observations; `lexicon.py` repairs
closed-vocabulary fields; `evidence.py` resolves candidate pools by trusted
source; `dates.py` supplies packet-receipt staleness; `policy.py` evaluates
ordered named rules; `confidence.py` holds the fitted calibration; and
`output.py` is the single schema boundary. Nothing below a stage can reach
back into it, which is what makes each stage testable in isolation.

One consequence worth naming: vocabularies are **ordered tuples with
lexicographic tie-breaking**, not sets. Held as sets, the nearest-neighbour
search resolves ties by iteration order, which Python derives from the
process hash seed — `XW-A` sits at edit distance 1 from both `XW-1` and
`XW-2` and resolved to each about half the time across seeds. Since
`visa_class` is both a scored field and a policy input (`TRANSIT-7` denies,
`DIP-1` is the sponsor and staleness exception), that made adjudication
itself hash-seed dependent and quietly broke the same-input/byte-identical
output guarantee the batch runner exists to provide. Ordering the
vocabularies removes the whole class of defect.

The ingestion cascade is not a single monolithic
extractor: `pdftotext -layout` (Rung 1, native text, ~86% of pages) with a
`pypdfium2`-rendered Tesseract OCR fallback (Rung 2) routed per page, not
per document — routing on "did this page classify into a known archetype,"
not "is the text empty," since an image-only page's native text is often
non-empty boilerplate with none of the real content in it.

Every page is classified into one of six fixed archetypes (intake form, fee
receipt, registry extract, biometric slip, sponsor letter, adjudicator
note), each with its own regex/anchor field extractor. Extracted candidates
from every archetype merge via a field-manual evidence-precedence order
(adjudicator note > intake form > biometric slip > sponsor letter >
registry extract), with `risk_flags` synthesized by unioning the biometric
slip's "Observed flags" line (99.7% exact match to truth when present),
`Registry Status: EMBARGO`, and adjudicator-note reason text — this is the
single highest-weighted extraction field (8/45 points) and no single source
carries it alone.

An explicit, named-predicate rules engine (`policy.py`) implements
`FIELD_MANUAL.md` literally, then applies the disqualifying/review risk
flags, revoked-sponsor and stale-arrival-date checks, defaulting to
`NEEDS_REVIEW` whenever evidence is missing rather than guessing clean. Each
decision returns a `reason` string, which doubles as the calibration key
(below).

## Undocumented policy inference

The field manual's own "Date Rules" section states arrivals more than 180
days before packet receipt are stale (denied), except DIP-1 with a valid
diplomatic note — but never names what "packet receipt" means
operationally, and no page archetype carries a visible received-date field.
Using each PDF's `creationDate` metadata as a receipt-date proxy and testing
across all 1,000 labeled training cases: **41/41 non-DIP-1 cases over the
180-day threshold are DENIED, and 13/13 DIP-1 cases over it are APPROVED** —
a clean split on both the rule and its stated exception, not a fitted
threshold. This was mined from a residual cluster of 54-60 "clean packet,
truth DENIED" cases the literal rules were getting wrong; the visa-class
denial-rate pattern (DIP-1 9.9%, XW-2 30.1%, MED-3 33.3%, XW-1 42.6% among
otherwise-clean packets) pointed directly at it.

A second signal, "Registry notice: sponsor standing requires additional
verification" on the sponsor letter (28/1000 docs, 23/28 = 82% truth
DENIED), wasn't deterministic enough to auto-deny but was too risky to
approve through given the asymmetric -4 catastrophic-false-approval penalty
— routed to `NEEDS_REVIEW` instead of hardcoded as a denial.

## Injection resistance

Two independent layers, because they catch different things. A **geometric
visibility filter** (`hidden.py`) inspects real PDF text-object
properties via pdfium's low-level API — fill color vs. background, alpha,
render mode, crop-box bounds — to find text invisible on the rendered page
regardless of wording; validated against 150 real training docs with zero
false positives before trusting it. A **keyword/imperative-language filter**
(`sanitize.py`) catches phrasing-based attacks the geometry layer can't see
by construction — confirmed necessary because one training document bakes a
fake "answer key" directly into raster *pixels* on an image-only page, which
is not a PDF text object at all. An adversarial test suite (17 tests) builds
poisoned PDFs fresh per test with `reportlab` — white-on-white text,
render-mode-3 invisible text, off-page text, encrypted/corrupt/zero-page/
300-page files — and asserts the pipeline never lets hidden content drive an
adjudication and never crashes on hostile input.

## Calibration

The scorer's calibration metric is mean Brier error against a binary
target (adjudication exactly correct or not) — a strictly proper scoring
rule minimized by reporting the true P(correct), not a document-quality
score. Rather than a hand-picked constant, confidence is a lookup table
keyed by the policy's own `reason` string, fit on dev (700 cases,
Bayesian-shrunk toward the overall weighted accuracy, pseudo-count k=8 so
small-sample reasons are not taken at face value).

The spread is what makes the feature worth having: `adjudicator_note` is
right on 195 of 195 dev cases, while `missing_arrival_date` is right on 25.6%
of 43 and `incomplete_evidence` — the largest bucket at 213 of 700 — on
32.4%. A single constant across a 1.000-to-0.256 range is badly wrong at both
ends.

A trap worth recording: this table must be re-fit whenever the policy
changes, because a stale one fails *silently*. The version this replaced had
been carried across intervening policy changes and was fit against a
materially different reason distribution (117 adjudicator-note cases against
today's 195, and an assumed overall accuracy of 0.607 against the measured
0.709). Adjudications stayed correct throughout; only the stated confidence
in them drifted, and Brier being strictly proper, understating correctness
costs exactly as overstating it does. Re-fitting moved dev calibration
15.62 -> 15.66 and holdout 15.46 -> 15.43 — a wash on score, which is the
point: the value is that the table now describes this policy. Holdout was
read once as a go/no-go and not iterated against.

## Honest failure-mode analysis

Final scores: **dev 117.78/150, holdout 112.95/150** (dev/holdout extraction
39.88/39.32, classification 62.24/58.20, calibration 15.66/15.43).
Catastrophic false approvals — the severely penalized outcome — are at
**0/700 dev and 1/300 holdout**, down from 39/700 and 20/300 at the first
working baseline.

The final OCR pass exposed a subtle safety failure: a disqualifying
`biohazard_red` panel read as `teoharard red`, failed closed-vocabulary
matching, and was accidentally interpreted as a confirmed empty flag set.
Separator normalization recovered that example, while the general fix treats
any non-empty but unrecognized panel as ambiguous rather than clean. This
removed the last dev catastrophic approval. The one remaining holdout
catastrophic case is unresolved and is not patched by case ID.

A real, submission-blocking bug was only found by testing at the actual
5,000-document scale: 7 records had calendar-invalid dates like
`"2026-33-07"` that a shape-only regex let through (OCR digit corruption),
never surfacing across 1,000 dev+holdout cases. Fixed and regression-tested
with the real failing values.

## What I'd do with another week

1. **A second undocumented-rule pass.** The staleness rule explained most
   but not all of the "clean packet, truth DENIED" residual; `MIB-000538`
   and similar cases need fresh feature-difference mining, the same
   methodology that found staleness.
2. **Rung 3 (targeted re-OCR).** Several OCR misses are single fields
   (a truncated arrival date, a garbled sponsor ID) inside an otherwise
   well-read page — a tight crop-and-re-OCR pass on just the failed field,
   with a character whitelist, would likely recover a meaningful share of
   the ~35% extraction miss rate that's currently written off to "OCR
   noise" without being re-attempted.
3. **A learned tie-breaker over the rules.** The calibration table already
   exposes exactly the feature (`reason`) a small CPU-only classifier would
   want; worth testing whether it beats rules-alone on holdout before ever
   shipping it, per the challenge's own guidance.
4. **Barcode/QR decoding.** 22 training docs mention barcodes; never
   decoded to confirm whether they ever carry real (non-injected) evidence.
