# MIB Doc Challenge — Technical Memo

## Result

The submitted pipeline is offline, CPU-only, and deterministic by construction.
On all 1,000 public training packets it produced 1,000 valid records with no
missing, extra, duplicate, or schema-invalid cases and scored **122.31 / 150**:
41.70/50 extraction, 64.72/80 classification, and 15.89/20 calibration. It made
**10 catastrophic false approvals**. Two independent full runs are byte-identical.

Against the previous 119.33 checkpoint that is +2.98 total with four *fewer*
false approvals — the gain is in classification (+2.36) and calibration (+0.62),
with extraction flat. The improvement is not a better-tuned posterior. It comes
from declining points the fitted probabilities offered: the largest single change
forbids approval at one terminal, which costs classification points and buys back
more in avoided −4 penalties and in calibration.

## Approach

**Trust boundary first.** Every PDF glyph is classified before extraction.
White-on-white, sub-2-point, and off-crop text is quarantined, and downstream
code sees only visible evidence. Visible fake answer keys are also removed as
bounded blocks, including multi-line keys with labelled fields below a banner.
The bounds and payload-shape checks prevent an innocent prose mention of
“answer key” from deleting the rest of a page.

This is the highest-value defence in the system. In a measured 250-packet sample,
56 packets (22.4%) carried an injected answer key. Its field values were 93.2%
correct, but its adjudication was 0% correct and skewed 48-to-8 toward approval.
A naive extractor is therefore rewarded for following the decoy on one scoring
axis and driven into the −4 false-approval bucket on another.

**Text first, selective OCR.** In a 120-packet sample, 71.7% of pages had a
usable text layer; only 28.3% required OCR. Those pages use three unioned
Tesseract passes: baseline layout analysis, an eroded render that reconnects
stroke-damaged glyphs, and sparse-text mode for forms that ordinary layout
analysis treats as images. Unioning preserves evidence unique to any pass.
Denoising was excluded after measurement: it increased OCR cost by 56% and
changed mean field accuracy by −0.2%.

**Extraction follows document authority.** Closed vocabularies are normalized
with bounded fuzzy repair; ambiguous terms such as `paid` require label
anchoring because they occur inside other values. Manual corrections and
sponsor-attestation prose have explicit parsers. Pages are typed from their
printed titles, and conflicting scalar values resolve using the field manual's
order—adjudicator note, intake form, biometric slip, sponsor attestation,
registry extract—before confidence or page order. A regression probe puts
`SPN-2222` on an intake form and `SPN-1111` on a sponsor letter; the intake value
wins in both page orders.

`applicant_name` is the one open-vocabulary field, so it has no vocabulary to
check a candidate against, and its Title-Case pattern is the exact shape of a
neighbouring label. Where the name was blank the window slid onto the next label
and returned it: 136 of 4,690 non-blank names in an earlier build read `Species
Code`, `Home World`, or an OCR-damaged variant such as `Species Home Workt`.
Candidates containing any field-label word are now skipped and the scan
continues to the next window and then to the attestation sentence. No true
training name contains such a word in any position, so the rule discards nothing
the corpus relies on, and an unreadable name yields a blank that widens the
posterior instead of a confident wrong answer.

**Policy is declarative; decisions are score-aware.** `rules/policy.yaml` orders
named terminals and `mib/policy.py` implements one predicate per terminal.
Runtime class posteriors are fitted on the pipeline's own extracted fields, not
ground truth, so unread evidence is represented in the probabilities. A stale
`DIP-1` packet has its own fitted terminal: the measured ground-truth population
contains 32/32 denied non-diplomatic stale cases, while 15 stale diplomatic
cases contain 12 approved, 3 review, and no denials.

The final action maximizes expected challenge points rather than posterior
argmax. For probabilities \(p,q,r\) of approval, denial, and review:

```text
EV(APPROVED)     = 8p - 4q + r
EV(DENIED)       =      8q + r
EV(NEEDS_REVIEW) = 2p + 2q + 8r
```

Reported confidence is the posterior probability of the chosen class, which is
the proper quantity for the evaluator's Brier term.

**Where the EV rule is overridden, it is overridden by a stated rule.**
`never_approve_terminals` lists terminals whose defining condition is *missing
required evidence*, and approval is removed from the candidate set there
regardless of what the posterior says. `med3_no_check` is the entry that matters:
MED-3 requires a clean biohazard check, no packet in the corpus states one, so
the bucket is by construction the set whose required check is absent. The fitted
posterior sits at 0.61 APPROVED and the EV rule would approve it for +0.69
classification points.

That +0.69 was declined. Taking it would double the pipeline's catastrophic
false approvals from 10 to 20; it is worth roughly 0.5 net once the calibration
gain from hedging is counted; and it bets that the public 63%-approved MED-3 mix
holds privately on a posterior fitted from 51 packets. Every runtime-visible split of the bucket was
tested first — biometric-slip presence, registry extract, page count, OCR
fraction, extraction completeness, quarantine volume, fee status — and none
separates it; the only splits that "won" were label-fitted cells of one to nine
cases that the 25-case support floor discards anyway.

The constraint lives in the policy file rather than inside a tuned probability
on purpose. The posterior keeps describing what the training data actually did,
and a reviewer can see the judgement call and disagree with it.

## Failure modes and another week

The largest remaining extraction losses are not all recoverable. At an earlier
40.56/50 checkpoint, the 9.44 missing points split into 1.82 points of visible
evidence the pipeline misread, 2.68 points present only in quarantined text, and
4.93 points absent from the PDF. Private scoring removes genuinely
unrecoverable fields from a case's maximum, while the public labels do not
contain that metadata.

The highest-priority engineering gap is multi-applicant isolation. The manual
warns that one packet may contain several applicants, with the active `case_id`
selecting the relevant one. Page typing now enforces authority for conflicting
scalar values, but it does not yet associate every page with the active
applicant. Applicant-name reconciliation also remains a repetition/native-text
heuristic rather than a full identity graph.

Other private-set risks are unobserved hidden carriers (non-rendering text mode,
occlusion, optional-content groups, annotations, metadata, and barcode
payloads), damaged page titles that defeat deterministic page typing, and
adjudicator stamps printed as images on otherwise text-rich pages. With another
week I would add adversarial fixtures for those carriers, active-case page
association, and stamp detection that runs independently of the text-sufficiency
OCR gate.

## Reproducibility

The image accepts exactly `<input_pdf_dir> <output_predictions_path>`. It ships
only deterministic Python code, Tesseract/Poppler, the policy files, and pinned
runtime dependencies. No LLM, VLM, cloud OCR, API key, validation answer, or
case-id lookup table is present. Development models were used only as analysis
instruments; every runtime behavior they motivated was reimplemented as
deterministic code and covered by ordinary tests or measured corpus probes.

The repository includes the exact offline/read-only Docker command, 93 unit and
adversarial regression tests, the public scoring commands, and `docs/RECON.md`
with the measurements and rejected experiments behind the design.
