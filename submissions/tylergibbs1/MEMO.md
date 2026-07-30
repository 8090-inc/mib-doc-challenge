# Technical Memo — Audited Visible-Evidence OCR

## Approach

This resubmission uses a deterministic, offline visible-evidence OCR pipeline.
The runtime is reused under MIT from the public Calling Moonshots solution at
commit `9ed5ed360ae40053dfee80bff09eef29a83a3980`, which is itself derived under
MIT from Brian Pridgen's `handemanai` baseline at commit
`4b37a7815bea79de0a01beca6eb6566e1611af73`. The original copyright and MIT
permission notice, detailed model provenance, package licenses, and upstream
technical memo are preserved in my public solution repository.

I did not copy another participant's validation predictions. The attached
5,000 rows were generated independently by executing the attributed source
against the checksum-verified public validation PDFs with networking disabled.

The rendered page is the trust boundary. Before rasterization, the system
examines PDF spans for render mode, opacity, color, and crop intersection.
White-on-white, off-crop, and other hidden text is removed so contrast
enhancement cannot turn a fake answer key into OCR evidence. It never decodes
barcodes and uses no LLM, VLM, cloud OCR, API key, or runtime network.

RapidOCR provides text detection while a compact PP-OCRv5 English mobile
recognizer reads visible text. Ordinary pages use a bounded low-resolution
path; packets missing deny-relevant evidence receive a higher-resolution
second view. Closed vocabularies constrain species, home world, visa class,
purpose, fee, and risk extraction. Template-anchored readers recover damaged
fee, flag, sponsor, world, and adjudicator-note regions. Cross-page candidates
retain source authority, strike-through, correction, and agreement evidence.

Adjudication combines field-manual rules with evidence-only terminal guards.
The guards may demote a terminal decision to `NEEDS_REVIEW`, but cannot invent
an approval or denial. A small exported tree ensemble may resolve only the
specific `insufficient_evidence` review path; it contains no case IDs or open
applicant/sponsor identity values. Confidence uses a public-training-derived
logistic and isotonic calibrator.

The entrypoint uses four worker processes, parent heartbeats, per-case
deadlines, worker recycling, and atomic output replacement. It first writes a
complete fallback file, checkpoints extraction state, and replaces the
fallback only after final adjudication. A single native-library hang therefore
does not erase the batch.

## Validation discipline and results

I froze the prior submission and compared candidates using only public training
labels. The primary audit used a fixed 700/150/150 author split, label-blind
layout groups, and group-disjoint folds. The two 150-case author holdouts were
not used to fit the candidate.

On those holdouts, this one-pass candidate scored 131.19 and 137.43; pooled it
scored about 134.31. The frozen prior submission scored about 125.56 pooled on
the same cases, for an estimated gain of about 8.75 points. A paired
document-bootstrap comparison had a positive 95% lower bound. The upstream
authors' fresh full-1,000 Docker audit reported 134.7171/150: 45.4722
extraction, 71.9300 classification, and 17.3149 calibration.

I also evaluated a four-system research ensemble that reached about 140.86
pooled locally with zero catastrophic false approvals. I did not submit it:
running all four OCR pipelines was incompatible with the official average
runtime limit, and cached ensemble outputs would not be a reproducible Docker
solution. Two attempted one-pass learned distillations were rejected after
losing score on the author holdouts.

The submitted image is about 287 MB and contains about 14.2 MB of model
artifacts, below the published image, per-model, and aggregate-model limits.
The retained upstream validation run completed all 5,000 PDFs in 6 h 36 m 46 s
(4.761 s/PDF) with four CPUs. I rebuilt the source in my solution repository
and confirmed byte-identical output against the audited image on a
network-disabled, read-only smoke case before generating this file. The
submitted JSONL has SHA-256
`08ba6fb615129dccd78ce29025d8d3945b7bea1b1e5bec4a0093fb8e7ec8e71f`;
the solution repository includes a machine-readable generation receipt.

## Known failure modes

- When decisive visible evidence is physically absent, the resolver sometimes
  makes a score-optimal bet instead of preserving review. On the public
  full-set audit this improved average score but increased catastrophic false
  approvals to 12. This is the main private-set risk.
- Severe scan damage can still destroy an arbitrary name, date, or sponsor ID.
- The compact OCR correction transducer did not generalize on a sealed split
  and therefore ships disabled.
- Authority resolution remains hardest when a damaged manual correction and a
  clean lower-authority field disagree.
- The public generator may not perfectly represent the private template and
  damage distribution, so the local score should not be read as a guarantee.

## With another week

I would add a direct visual keyword spotter for decision-bearing crops, trained
only on synthetic fonts and unlabeled visible crops, to recover damaged
`APPROVED`/`DENIED` evidence without full transcription. I would also build a
typed candidate ledger with pairwise source-aware ranking and
conflict-conditioned uncertainty. Both would remain behind group-disjoint
acceptance gates, a zero-new-false-approval requirement, and measured CPU
budgets.
