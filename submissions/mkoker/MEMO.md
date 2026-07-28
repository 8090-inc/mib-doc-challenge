# Technical Memo (mkoker)

Local scores, measured with the official docker runner and evaluator on a train split
I held out myself (801 tune / 199 holdout by sha256 of case_id): DEV 111.53, HOLDOUT
110.77 out of 150. Classification 55.1/80, extraction 42.2/50, calibration 14.2/20,
no missing cases. The tune/holdout gap is 0.76 points. Runtime is 1.7s per PDF against
the 6s budget on 4 vCPU. Image is 257 MB. The only model artifact is the ~14 MB of
RapidOCR ONNX weights.

## How it works

The core decision: I treat the rendered page as the source of truth, not the PDF text
layer. Every page gets rendered with pypdfium2 and OCR'd with RapidOCR on CPU. Text
layer content only gets used when I can confirm it actually appears in the rendered
pixels. About a third of the training docs carry some kind of hidden text attack
(white on white, outside the crop box, fake answer keys, fake system prompts), and
this design ignores all of it by construction instead of trying to enumerate attacks.

Three stages, all deterministic:

1. Extraction (src/extract.py). OCR-first field recovery. Fields with a known value
set (species, visa class, fee status, purpose, home world) get fuzzy matched against
vocabularies built from the training labels. Structured tokens (case id, sponsor id,
dates) reconcile OCR output against text layer candidates that pass the visibility
check. There are two purely visual detectors where the signal isn't text at all:
illegible biometric slips (page ink statistics) and the green adjudicator APPROVED
stamp (color region analysis, 1.000 precision on my held-back split). The stamp is
the top of the field manual's evidence precedence, so it earns its rule. Output is a
per-field record of value, visibility, conflicts, and source.

2. Adjudication (src/rules.py, RULES.yaml). A plain rules engine. Base policy comes
from the field manual; the gaps the manual leaves open on purpose are filled with
rules mined from my 801-case tune split. Every rule has a one line citation, either a
manual section or the mined evidence with support counts (extra revoked sponsors,
embargo home worlds at 27/27 and 17/17, both being list patterns the manual says to
expect in the examples). Anything missing, invisible, or conflicting on a decision
field routes to NEEDS_REVIEW, because under this scoring a wrong NEEDS_REVIEW (2/8)
beats a false APPROVED (-4) every time. The approval stamp rule can only rescue a
would-be NEEDS_REVIEW into APPROVED and sits below every deny path. There's a script
in the repo that proves no hard-deny case can flip.

3. Confidence (src/calibrate.py). Confidence is just the observed tune-split accuracy
of whichever rule path fired, bucketed by rule id and evidence quality, minimum 20
cases per cell, thin cells inherit their parent. I also worked out the abstention
math (NOTES/abstain.md): submitting NEEDS_REVIEW beats omitting a case in every
scoring section, so the system always answers.

## Keeping myself honest

All tuning saw only the 801 tune cases. The 199 holdout cases got scored only at
phase gates, always through the full docker contract, never bare metal shortcuts.
Final gap 0.76.

## Where it fails

Classification is the binding constraint. About 45 residual false approves are cases
where the deny reason isn't recoverable from the nine output fields or my detectors:
staleness needs a packet receipt date that only exists as pixels, and some denials
hang on stamp semantics. I built and measured a DENIED stamp detector; it topped out
at 0.71 precision against my 0.90 gate, so it didn't ship. Same story for a home
world denylist that was only 55% pure. I'd rather eat the misses than ship a false
deny generator.

risk_flags sits at 81%. The remaining misses are visual stamps (biohazard, warrant)
that showed no detectable mark when I mined crops for them. No signal, nothing to
train on. applicant_name is 69%, mostly OCR-hostile scripts and multi-applicant
packets.

## Adversarial testing

I diffed the text layer against rendered pixels across the tune split: 284 of 801
docs carry hidden content. An earlier version leaked hidden-only sponsor ids and
dates on 44 docs. After forcing pixel confirmation on every text layer accept, zero
leak. Seven regression tests generate synthetic attack PDFs and pin that behavior.

## What I'd do with another week

Hand label stamp crops and train a small CNN for the deny-side stamps my weak
supervision couldn't separate; that's the biggest lever I found, worth maybe 2
points. Recover receipt dates from pixel-rendered date blocks to turn on the
staleness rule. Build a proper name selector for multi-applicant packets.

## Toolchain note

I built this with heavy use of AI agents running the extraction, rules, calibration,
and adversarial workstreams. Every rule, threshold, and go/no-go decision above went
through me, and the tune/holdout gating kept everyone honest.
