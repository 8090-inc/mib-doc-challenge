# MIB-LEDGER - Technical Memo

Solution repository (code, Dockerfile, full engineering memo): **https://github.com/HetanshWaghela/mib-ledger**

## Approach

MIB-LEDGER is a provenance-first evidence ledger, not an end-to-end model. Offline,
deterministic, no LLM anywhere.

1. **Forensic intake** splits every PDF span into `visible` vs `quarantined`
   (near-white luminance, sub-4pt, off-crop) before anything downstream sees it. The
   hidden injected answer keys and prompt-injection payloads on 18.8% of packets land
   in quarantine and can never reach a field value or a decision. OCR reads only the
   embedded JPEG bytes of a page, never a page render, because a render rasterizes
   hidden text back into pixels an OCR engine would read.
2. **Extraction cascade**: native PDF text first, then dual OCR (Tesseract +
   RapidOCR) on the ~47% image-only pages, every candidate funneled through a
   closed-vocabulary snap. A **role-aware trust ladder** separates extraction credit
   from decision trust: a single engine's read may add DENY-direction evidence alone,
   but APPROVE-direction evidence requires corroboration (dual-engine agreement, a
   second independent page role, or a census-validated single-engine route with
   measured >=97.5% precision). Absence of a flag never approves.
3. **Deny-biased policy**: deterministic deny gates run first, uncertainty routes to
   NEEDS_REVIEW, and a strict positive-corroboration gate is the only general path to
   APPROVED. One exception, taken deliberately: the field manual ranks the visible
   signed adjudicator note as rank-1 evidence, so it decides first - measured 263/263
   agreement with truth, including 23/23 on packets that also carry an injected key.
   All lists, vocabularies, cutoffs and confidences are mined from training rows by
   scripts, nothing hand-hardcoded from labels.

## Measurement (why our headline is lower than others')

Our headline is **fold-clean out-of-fold: 120.00/150, catastrophic false approvals
(CFA) 0** - 5 folds where every mined artifact is re-derived from that fold's
training rows only, scored with the unmodified `scripts/evaluate.py`. A
template-grouped split (packets grouped by page-role layout, testing transfer to
layouts never trained on) scores 119.45, a 0.55 gap. In-sample scoring of the same
build is 120.47.

We refuse to report in-sample numbers as the headline because this codebase has
three documented incidents where they lied: identical code scored CFA 0 in-sample
and CFA 1 out-of-fold; a mined sponsor-registry rule scored 72.9% in-sample and
12.0% fold-clean (819 of 864 sponsor ids appear exactly once - the rule had
memorized the split); and a forged "Manual correction" string cleared a deny gate
while the pre-fix run still measured CFA 0. In-sample self-reports of ~138 are
reporting the number our own history shows is not predictive. We also note, from
rebuilding competitors' published techniques on this corpus: the hidden injected
answer key's field payload is 90-98% accurate, and reading it is worth roughly +18
points - its adjudication payload is wrong 188/188. The organizers' documentation
says hidden text is not trustworthy evidence; we do not read it, in any laundered
form.

## Failure modes

- **Extraction is capped by evidence that is not in the packet.** 868/1000 packets
  have at least one unrecoverable field; for most blocked determinative fields the
  carrying page is physically absent (85% of fee-blocked packets have no fee page;
  ~90% of risk_flags-blocked packets have no biometric slip). No preprocessing or
  model recovers a page that does not exist.
- **We leave 186 truth-APPROVED cases in NEEDS_REVIEW.** That is EV-rational at our
  measured read precision: approve-side EV flipping was CFA-unsafe in 53/53 swept
  configurations, and a final audit measured that even packets whose biometric page
  is provably absent split 83 APPROVED / 49 REVIEW / 18 DENIED in truth - converting
  them would mint 18 CFAs.
- **Calibration (16.04/20) is refinement-limited.** A fold-clean correctness
  predictor over every legitimate feature ties the shipped per-reason confidences
  within +0.004; the remaining gap is only recoverable by raising classification
  accuracy itself.

## With another week

- Two measured micro-fixes: title detection fails on 90-degree-rotated scan layouts
  (the title-band heuristic assumes horizontal top-of-page text) and on faint-ink
  pages below the current contrast ladder - together ~10% of the risk_flags-blocked
  packets have a legible page we currently miss. Each needs its own CFA-gated
  fold-clean measurement before shipping.
- Region-of-interest multi-scale re-reads doubled read accuracy (29.6% to 51.9%) on
  the small slice where a garbled label line exists; a runtime-bounded variant is
  worth measuring properly.
- Beyond that, our audits say the remaining gap is structural: the evidence is
  either absent from the packet or only present in hidden text we decline to read.
