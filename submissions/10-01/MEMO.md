# MIB Doc Challenge — technical memo

## Approach

I built an offline, Dockerized intake pipeline that turns a directory of PDF
case packets into one JSONL row per case. The design goal was operational
safety first: **never false-approve a denial**, and never trust hidden PDF text
that looks like an answer key or system prompt.

**Parsing.** Visible spans are kept; pure-white and sub-threshold text is
stripped before OCR. Page roles (intake, biometric slip, fee receipt, sponsor
letter, registry, note) drive which fields may come from which page.

**OCR.** Clean native pages use the text layer. Raster pages run Tesseract plus
RapidOCR / PP-OCR routes. A restricted secondary reader can fill blank identity
fields from re-renders; its approval and confidence paths stay disabled so it
cannot invent a clean risk state.

**Policy.** Adjudication follows the field manual: disqualifying flags and unpaid
fees deny; review-only flags and incomplete identity review; approval only when
identity is complete, fee is paid or waived under the manual’s rules, and risk
flags were **positively observed**. Missing biometrics without observed flags
hedges to `NEEDS_REVIEW` rather than a silent clean approval.

**Late fills.** After serialization, narrow paths can re-open `APPROVED` when a
paid fee or sponsor id arrives late **and** the clean flags_observed bar still
holds. Fee ROI and OCR garble repairs target damaged “paid” ink without inventing
unpaid.

**Confidence.** Public-label logistic calibration is the default. Small floors
raise confidence on residual cohorts that are empirically pure correct
`NEEDS_REVIEW` or pure correct hard decisions (for example literal fee-status
unknown on a fee receipt page, or high-confidence paid approvals with risk
`none`). These floors do not change adjudication by themselves.

## What works

- Strong resistance to planted hidden answer keys (injection spans never enter
  the evidence model).
- Zero catastrophic false approvals on the fixed public validation holdout I
  used for ship gates.
- Full offline Docker contract: no network, 4 vCPU / 8 GiB class budget, multi-
  worker OCR.

## Failure modes

1. **True approvals with no biometric / unobserved flags.** Policy correctly
   refuses approval; those cases stay review and cost classification points.
2. **Disqualifying stamps with no OCR token.** Residual denials (especially
   biohazard) often have no readable “biohazard” text; they hedge or miss the
   flag unless pixel evidence is recovered.
3. **Unreadable fee receipts.** Status literally “unknown” or missing paid ink
   blocks approval even when the public label is paid.
4. **Calibration vs classification tradeoff.** Most late gains on my holdouts
   were calibration floors on pure residual cohorts, not large class lifts.
   Nested OOF still sits below the best post-hoc holdout total because the class
   wall is real.

## What I would do with another week

1. **Stamp geometry** for residual denials without readable text (color/shape
   detectors with strict CFA gates).
2. **Targeted fee re-OCR** only when a fee page exists and status is unknown.
3. **Nested OOF re-fit** of confidence after freezing adjudication so floors are
   absorbed into the model rather than stacked.
4. **Stress the 5,000-case validation run** for tail latency and worker recycling
   under the hard 30,000 s parent timeout.

## Attribution

Third-party code is listed in `ATTRIBUTION.md` in the solution repository
(secondary OCR reader lineage, fee-region templates, and challenge materials
under MIT where applicable). I do not use other participants’ validation
prediction files.
