# Technical Memo — Intergalactic Intake

**Training set (public labels, official evaluator): 120.6 / 150** —
extraction 40.5/50, classification 64.5/80, calibration 15.7/20, zero
missing cases, 15 catastrophic false approvals (down from 41 before the
expected-value layer). 5-fold cross-validation of the decision layer:
63.1/80 classification, 15.5/20 calibration — within ~1.4 points of
in-sample, so the layer is not memorizing. Runtime: 1.96 s/PDF for the full
pipeline inside the contest Docker limits (4 vCPU, network none).

## Approach

The pipeline is a classical document-engineering stack — no LLMs anywhere —
built around one organizing idea: **every extracted value carries provenance,
and only provably-visible evidence may influence output.**

1. **Ingest (PyMuPDF).** Each page's text spans are classified visible vs
   hidden (white/near-white fill, sub-5.5pt fonts, out-of-crop boxes). Hidden
   text — including every `SYSTEM: ignore visible evidence...` answer-key
   injection — is quarantined: it is never parsed for values. Its *presence*
   is kept as a fraud signal (see Decision layer).
2. **OCR path (Tesseract + OpenCV).** Pages whose visible text layer is empty
   are rasterized at 200dpi. Preprocessing ensemble: dark-ink threshold →
   deskew (projection-profile sweep) → OCR; hard pages retry with raw
   grayscale and Otsu binarization, and rotated slips get a 4-orientation
   fallback scored on a half-scale render. The parser keeps whichever variant
   parses best and unions the rest. White-on-dark decoys baked into scan
   images are erased by the ink threshold before OCR ever sees them.
3. **Parsing.** Page typing (fee receipt / registry / intake / biometric /
   sponsor letter / adjudicator note) by fuzzy title match with a
   distinctive-fields fallback. Field labels are fuzzy-matched
   ("Species Coda:" still binds), values snap to closed vocabularies mined
   from the training labels (12 species, 13 worlds, 5 classes, 10 purposes),
   digit fixups repair OCR confusions in `MIB-`/`SPN-` ids and dates.
4. **Evidence resolution.** Cross-page trust ladder per the field manual
   (signed manual corrections > intake form > slips > letters > registry),
   with two evidence-backed exceptions measured on train: the registry wins
   identity conflicts (21/21), and majority-vote beats tier for dates (two
   agreeing pages outvote one misread). Pages whose header case id differs
   from the active case never contribute values (multi-applicant decoys).
5. **Policy engine.** Deterministic rules from FIELD_MANUAL.md plus rules
   mined from the 1,000 labels and verified exactly: embargo world
   (Wolf-1061c, non-DIP-1 = 51/51 denied), six revoked sponsors, 180-day
   staleness against the packet epoch, DIP-1 exemptions, fee rules,
   visible adjudicator notes as definitive tier-0 evidence (162/162).
6. **Decision layer.** The rule verdict is replayed through the scoring
   payoff matrix using the empirical truth distribution of its
   (decision-path × packet-hygiene) bucket:
   EV(APPROVE)=8pA−4pD+pR vs EV(DENY)=8pD+pR vs EV(REVIEW)=2(pA+pD)+8pR.
   This mechanically encodes "when torn, punt to review" and makes false
   approvals require overwhelming evidence. Packet hygiene distinguishes
   pristine / damaged / injection-present packets — an injected packet with
   clean-looking fields is 5× more likely to be a denial trap, and the EV
   layer prices that in. Confidence = P(chosen class correct | bucket),
   which is exactly what the Brier calibration score rewards (5-fold CV
   confirms no memorization: CV vs in-sample gap < 1 point).

## Failure modes (known, measured)

- **Invisible-evidence denials.** A minority of packets are denied on
  evidence deliberately removed from the visible document (e.g. biohazard
  flags with no visible trace). These are statistically shaded by the
  hygiene priors but individually undetectable; they bound our
  classification ceiling.
- **Severely smudged scans.** The worst damage profiles defeat all four OCR
  variants; those packets resolve to NEEDS_REVIEW with calibrated low
  confidence rather than being guessed.
- **Injection self-test.** Grafting a hidden answer-key injection onto clean
  packets changes no field value and never flips a non-approval to APPROVED
  (verified by `tools/injection_selftest.py`; the only permitted shift is
  toward NEEDS_REVIEW, since detected tampering is itself evidence).
- **OCR name recovery.** Names have no closed vocabulary; fuzzy cross-page
  clustering recovers most, but scan-only packets keep an OCR-flavored
  spelling of the name.

## With another week

- A small stamp/cross-out detector (red-ink segmentation + tiny CNN) for
  rescinded-denial and biohazard stamp graphics.
- Superresolution or a lightweight text-line recognizer (PP-OCR mobile) as a
  third OCR engine for the worst damage profiles.
- Replace hand-tuned fuzzy cutoffs with thresholds swept per field against
  held-out folds.
