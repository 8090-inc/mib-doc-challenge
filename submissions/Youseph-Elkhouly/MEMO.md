# Technical Memo — MIB Doc Challenge

## Architecture

The pipeline is a two-rung ingestion cascade, not a single monolithic
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

An explicit, named-predicate rules engine (`rules.py`) implements
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
visibility filter** (`visibility.py`) inspects real PDF text-object
properties via pdfium's low-level API — fill color vs. background, alpha,
render mode, crop-box bounds — to find text invisible on the rendered page
regardless of wording; validated against 150 real training docs with zero
false positives before trusting it. A **keyword/imperative-language filter**
(`injection.py`) catches phrasing-based attacks the geometry layer can't see
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
keyed by the rules engine's own `reason` string, fit on dev (700 cases,
Bayesian-shrunk toward the overall weighted accuracy, pseudo-count k=8 for
small-sample reasons). This mattered a lot: `incomplete_evidence` alone is
37% of all dev cases and its true accuracy is 29.1%, but a flat tier had
been assigning it 0.48 — badly overconfident for over a third of the
dataset. Per-reason accuracy ranges 16.0% (`missing_arrival_date`) to 100%
(`adjudicator_note`, matching a Manual Adjudicator Note's near-perfect
reliability, 162/162 full corpus). On holdout, the reliability curve tracks
the diagonal closely for most buckets (e.g. the 0.9-1.0 bucket: mean
confidence 0.960, empirical accuracy 1.000); one small-sample bucket (n=17)
is off and is reported honestly below rather than tuned against holdout to
smooth over.

## Honest failure-mode analysis

Final scores: **dev 107.75/150, holdout 101.85/150** (extraction ~37/50,
classification ~51-56/80, calibration ~14-15/20). Catastrophic false
approvals — the one severely-penalized outcome — are at **1/700 dev, 3/300
holdout**, down from 39/700 and 20/300 at the first working baseline; every
remaining case is individually diagnosed, not a systemic pattern:
- Two are the same undocumented-rule residual not explained by the staleness
  rule (e.g. `MIB-000538`, gap only 72 days — a second policy pattern that
  wasn't identified this round).
- One (`MIB-000865`) is a case where the intake form's *own visible,
  legible, unambiguous* text disagrees with the truth label — confirmed by
  direct visual rendering, not an extraction bug. No rule-based fix found;
  flagged as a genuinely hard residual.
- One (`MIB-000127`) is a fully image-only packet with one page whose OCR
  couldn't recover enough to decide.

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
