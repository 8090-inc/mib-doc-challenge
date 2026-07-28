# Technical Memo — MIB Doc Challenge

**Solution repository:** https://github.com/kirtandesai/mib-doc-solution · **Local train score: 124.0/150**
(extraction 43.0/50, classification 65.2/80, calibration 15.8/20, 15
catastrophic false approvals in 1,000 cases, 0 missing cases, well inside
the 6 s/PDF runtime budget on 4 vCPU).

## Approach

The pipeline is organized around one idea: **evidence provenance decides
everything**. Three layers:

**1. Trust layer.** Text spans are classified visible/hidden by rendering
properties (color luminance, font size, position) — never by content. The
challenge plants the same attack in three inks — white-text "answer keys"
(188/1000 train packets; the injected adjudication is wrong 188/188, a
designed kill-switch), *visibly printed* answer-key lines, and barcode
instruction payloads — and all three are neutralized by one rule:
instructions are never evidence, at any visibility. We found and rejected
the inverse exploit (always-wrong ⇒ invert): it depends on hidden content
and would not generalize. Injection presence only marks the text layer
untrusted, forcing OCR of the visible pixels.

**2. Evidence extraction as a diagnosis loop.** Pages whose visible text
layer is near-empty are scans: rendered and read by Tesseract with a
benchmarked configuration (deskew + PSM 3 won a 5-variant benchmark scored
against truth tokens; hand-rolled binarization lost to Tesseract's own
Otsu). A retry cascade (contrast stretch → PSM 6 → 180° rotation) ranks
attempts by *recognizable document words*, not characters — an upside-down
page out-chars the truth but can never out-word it. Beyond page OCR, the
extractors are structural-fuzzy recoveries validated corpus-wide before
shipping: garbled finding lines ("Pining: GED 7" → Finding: DENIED, with
separator loss tolerated), templated Reason lines deciding destroyed
findings (22/22 correct on train), garbled flag lines ("bichaxard_yed" →
biohazard_red, margin-gated against the closed flag vocabulary),
colon-less labels accepted only when the value passes its field cleaner,
cross-source word-slot name voting anchored to the form identity (46
fixes / 1 break), corpus-window year repair using shape-confusion priors
(8↔6, 0↔6; unique-candidate-only, ambiguity refuses), and closed-vocabulary
snapping with unique-prefix truncation matching. Damage is evidence:
markers like "[RISK PANEL MISSING]" mean *unknown*, never *clean*, and a
damaged value at one source falls through to a clean copy at the next.

**3. Policy + decision theory.** Hand rules implement the public field
manual plus structure inferred from labels (a decision tree over label
fields recovered the skeleton; each rule then validated individually —
staleness >180 days denies at 36/36 with the DIP-1 exemption, `waived`
behaves exactly like `paid`). The staleness reference derives from the
input corpus itself (95th percentile of arrivals; `max()` was poisoned by
OCR-garbled years). Every adjudication exits through a named rule path; a
fitted table maps each (path, decision) to the decision maximizing
expected evaluator points under the published payoff matrix — subordinate
to an operational-risk cap: no hedge may flip into APPROVED while its
bucket carries >10% denied mass (pure EV argmax once manufactured 11 false
approvals for a 0.15-point edge; the cap reversed it and scored higher via
calibration). Confidence is the path's measured accuracy, shrunk on small
buckets — calibration is honest by construction. The −4
false-approval asymmetry is treated as the operational risk statement it
is: 15/1000 catastrophic false approvals, achieved by evidence rules, not
blanket hedging. All label-derived knowledge lives in `policy.py` /
`policy_paths.py` with documented supporting evidence — policy-level
generalizations only, nothing keyed to a case, file, or dataset date.

## Process: build, then look, then fix — twenty-three times

The score history (EXPERIMENTS.md) is a sequence of small verified fixes
found by reading actual failing pages, not by tuning aggregates: a
damage-marker that silently blocked readable lower-tier values; "[NAME CUT
OUT]" shipping as an applicant name; upside-down pages defeating a
char-count quality gate; a fit script observing its own overrides (feedback
loop); whole-line matching that failed every slightly-garbled header. Each
fix was probed against labels before integration, and integration results
overruled probes when they disagreed — two techniques that passed probes
were reverted after integration testing (header-crop fee recovery went
score-flat with +2 false approvals and 6× runtime; revoked-list
corroboration traded 5 false denials for 6 lost true denials).

## Failure modes (measured, not guessed)

Fifteen further hypotheses were probed and rejected with corpus-wide
numbers (EXPERIMENTS.md): deep OCR on washed receipts (23% recovery, 71%
accuracy — the ink is absent, not faint), cross-field priors (the
generator randomizes combinations), color/stamp signatures (histograms
identical), sub-splits of the ambiguous-fee bucket (every split within
±0.1 EV). The remaining local error concentrates in two path families
(`fee_unknown` ~216 cases, `clean_approve` ~152) where labels follow
ground truth that is provably absent from the page — the challenge's
designed gradient for punishing guessers. We decline to train models on
those residuals: with no measurable signal, a model would memorize
generator artifacts, which is what the anti-gaming audit exists to catch.
Known imperfections are documented rather than hidden: 15 phantom
`illegible_biometrics` from the missing-slip inference (net-positive
against its true positives), and review-only flags grounded outside
visible evidence (`memory_tampering`, most `sponsor_mismatch`) are
unrecoverable by design.

## Blind-review experiment

After iterating in one context for days, we spawned three fresh-context
reviewer agents with no access to our conclusions — only the code, the
failing documents, and truth — and asked open-endedly for everything they
would change. In one day this yielded +6.6 points and three confirmed
bugs our in-context iteration had missed: a corpus-learnable revoked-
sponsor pool with a DIP-1 exemption (frequency anomaly, detector 6/6;
+2.9), footer words inside the OCR quality gate plus missing 90°/270°
rotations (+1.1), the applicant-name vocabulary being a closed, saturated
12×12 morpheme grammar (+0.5), letter-over-form visa precedence (12/12),
and a page-order-dependent merge bug (now covered by a shuffle regression
test). Their negative findings independently reproduced our earlier
rejections without contamination.

## Disclosed design choices

Two choices a reviewer should see explicitly. (1) *Reported-field
fallbacks:* when a field is unreadable, the output reports the input
batch's modal value; the adjudicator runs on the evidence record and
provably never consumes imputed values (decision outputs bit-identical in
the ablation). Wrong reported fields score identically to placeholders by
evaluator design; decisions rest on evidence only. (2) *The declined
answer-key exploit:* the hidden injections' fields are 90–98% accurate
(the poison is a fixed decoy record; decoy-filtered fields are near-exact)
while their adjudication is wrong 188/188. We measured all of this and use
none of it — not even the "always-wrong" inversion — because hidden
content is not evidence and the private set controls that channel.

## With another week

(1) Per-word OCR confidence threaded end-to-end — the upgrade most likely
to raise derived-flag precision (identity/sponsor mismatch) past the
shipping bar and sharpen per-case confidence beyond per-path accuracy.
(2) A render-diff visibility check (rasterize with and without each text
object) replacing the luminance heuristic — robust to dark backgrounds and
colored-text injections. (3) A spatial word-box parser as a second pass —
insurance against private-test layout variants that break line-order
parsing. (4) A finding-line word-image classifier for the last ~3
unreadable adjudicator notes.
