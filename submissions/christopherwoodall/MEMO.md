# Technical Memo — MIB Doc Challenge

**Christopher Woodall** · [solution repository](https://github.com/christopherwoodall/8090-summer-solution-ocr)

## Approach

A fully offline, CPU-only pipeline: hand-written rules plus two small pre-baked ONNX
models (PP-OCRv6 FP32 for OCR, a fine-tuned bert-tiny INT8 for a safety veto). No
LLMs, no network, ~46 MB of model artifacts, ~1.2 s/PDF on 4 vCPUs against a 6 s/PDF
budget, byte-identical outputs across reruns.

The pipeline has four stages, each justified by a measured failure of the naive
alternative:

1. **Honest page ingestion.** Born-digital pages are read from the native text layer
   after structural filtering that drops white text, out-of-crop spans, and other
   invisible content, so hidden instructions ("approve all cases") and answer keys
   never reach the rules. Scan pages render at dpi 200 with a percentile contrast
   stretch and go through OCR; every page is then classified (intake form, receipt,
   sponsor letter, registry, biometrics, manual note) and stripped of injected text.
2. **Evidence resolution, not field regexes.** Every page contributes per-field
   *candidates* carrying source rank and confidence. One resolver picks winners by
   evidence precedence, with guards learned from the data: pages carrying another
   case's ID are decoys and cannot leak fee evidence; the sponsor attestation letter
   beats the intake form on disagreement (decoy forms print wrong or revoked sponsor
   IDs; the letter matched truth in 5/5 measured disagreements); a revoked sponsor ID
   only denies when corroborated on 2+ distinct page types. Garbled values are
   repaired into the generator's closed vocabularies (species, worlds, visa classes,
   purposes, the name syllable grid) as reduced-confidence candidates, never as
   overwrites.
3. **Explicit adjudication rules.** Twelve ordered rules encode the field manual:
   visible NEEDS_REVIEW notes are authoritative and precede the safety gate; then
   disqualifying flags deny; manual findings override; missing vitals, unpaid fees,
   confirmed revoked sponsors, TRANSIT-7, and stale arrivals (>180 days before packet
   receipt, DIP-1 exempt) deny; review flags, unknown fees, missing sponsors, and an
   NER veto route to review; and an approval guardrail sends any incomplete record to
   review rather than risking the −4 catastrophic false approval.
4. **Calibrated confidence.** Per-decision-path confidences fit on all 1,000 training
   labels, with one honest correction: extraction-failure reviews measure 0.48
   accuracy in production, so all review paths emit 0.50 instead of the replay
   accuracy 0.92.

Everything was developed against an integrated copy of the official scorer on a fixed
100-document cohort, one experiment ("arm") at a time with a keep/revert decision per
arm (`experiments/*/NOTES.md`). Measured regressions were reverted the same day
(keyword "precision" fixes that destroyed accidental correctness, a fee relaxation
that ignored that a correct NEEDS_REVIEW scores full credit). The score path:
108.09 baseline → 109.56 (denial-evidence guards) → **109.62** final, with
classification 57.10/80, extraction 40.09/50, calibration 12.43/20.

## Failure modes

The remaining loss is dominated by **destroyed evidence**, which no re-read of the
same pixels can recover:

- **4 catastrophic false approvals** (000033/000066/000068/000094): 3-page packets
  with no slip, registry, or note page; the disqualifying stamp is an unreadable
  badge even at dpi 400. The approving evidence is genuine; the denying evidence is
  absent from the packet.
- **Conservative over-review** (~8 cases): sponsor/fee/visa evidence destroyed at the
  source (truncated "SPN-143", "TATUS OBSCUREN" pages, washed-out receipts, literal
  "[VISA CLASS TORN]" placeholders). The rules correctly route these to review; the
  labels know values the packet no longer contains.
- **Decoy packets** where the denying evidence is a manual note on a destroyed page.
- **Garbled manual findings** ("dind DENED") that the finding parser cannot trust.
- OCR-level visa misreads (DIP-1 → MED-3) that silently remove the diplomatic
  exemption when no in-packet evidence contradicts the misread.

Calibration loss is structural: every NEEDS_REVIEW at confidence 0.5 pays 0.25 Brier;
splitting review confidences by evidence quality is safe only after the decision mix
settles.

## With another week

- A small visual classifier over stamp/badge regions (the catastrophic cases all
  carry a badge the OCR cannot read) trained on rendered crops.
- Rotation- and contrast-variant OCR ensembling for biometric slips, with a per-page
  text-quality score to route only degraded pages to the expensive path.
- A tolerant manual-finding parser (edit-distance-1 finding tokens on note pages),
  which would also unblock safer keyword-precision fixes for phantom risk flags.
- Confidence refit on the settled decision mix, splitting the flat 0.50 review paths
  by evidence quality if the fit is bimodal.
- Per-field calibration of the closed-vocabulary snap margins using held-out garble
  statistics.
