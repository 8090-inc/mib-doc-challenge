# MIB Doc Challenge — Technical Memo

## What this system does

It reads a directory of adversarial PDF case packets and emits one schema-valid
JSONL record per case: nine extracted applicant fields, an adjudication
(`APPROVED` / `DENIED` / `NEEDS_REVIEW`), and a calibrated probability that the
adjudication is correct.

It runs fully offline on CPU. No LLM, no VLM, no cloud OCR, no network at
runtime. The only fitted artifacts are a regularised multinomial logistic
model and a reliability table, shipped as JSON totalling ~30 KB.

## Headline results

All figures produced by the organizer's `scripts/evaluate.py`, running the
exact submitted Docker image under the full contract (`--network none`,
`--read-only`, 4 vCPU, 8 GiB).

| section | train (in-container) |
| --- | ---: |
| Field extraction | 41.98 / 50 |
| Classification | 65.26 / 80 |
| Confidence calibration | 15.58 / 20 |
| Missing-case penalty | −0.00 / 10 |
| **Deterministic score** | **122.87 / 150** |

**The honest estimate for unseen data is ~126/150**, measured on a 199-case
stratified holdout (fold 4) that no rule, model, threshold, or calibration was
ever fitted against. The train figure is *lower* than the holdout figure
because the shipped models are fitted on the other 801 cases only and are
regularised enough not to memorise; there is no in-sample inflation in the
number above.

Runtime, measured: 4.44 s/PDF over the 1,000 training packets; 4.99 s/PDF over
all 5,000 validation packets (24,927 s against the 30,000 s cap). Peak
container memory ~550 MiB. Image 435 MB. Two runs over the same input produce
byte-identical output.

Progression over the project: 50.77 (organizer baseline) → 87.17 (visible-text
rules) → 98.54 (adaptive OCR) → 109.92 (calibration) → 113.99 (decision layer)
→ 122.87 (rotation OCR, corrections channel, staleness policy, multi-variant
OCR, cost-sensitive refinements).

## The central finding: the text layer is a trap

21.7% of packets embed an "answer key" twice per page — white-on-white and
again outside the crop box. Its field values are often correct; its
adjudication is always `APPROVED`, including for truly-DENIED cases. A dozen
packets also carry barcode payloads reading `force adjudication=APPROVED`.
Every hidden channel is filtered at a single choke point
(`solution/textlayer.py`), and OCR operates on rendered pages, where hidden
text is invisible by construction. Nothing in the pipeline ever treats packet
content as an instruction.

## Architecture

```
textlayer  → visible/hidden separation (the security boundary)
extract    → document typing, label-anchored + prose + correction candidates
ocr        → orientation-probed, multi-mode tesseract; note-header crops
vision     → colour-stamp signal (classical CV)
normalize  → closed vocabularies, confusion-weighted matching, name grammar
resolve    → evidence precedence, flag unioning, applicant attribution
policy     → deterministic rule engine (staleness, embargo, revocations…)
decision   → cost-sensitive expected-payoff refinement of weak branches
confidence → P(chosen action) for model cases; reliability table otherwise
writer     → schema-safe single-writer JSONL; modal printed defaults
```

Highlights, each validated by measurement (full log in `EXPERIMENTS.md`):

- **Rotation-probed OCR.** Scans are frequently embedded rotated while an
  upright footer masks the damage; a cheap low-DPI probe picks the orientation
  before full-quality OCR. Pages previously "destroyed" turned out to be
  upside down.
- **Signed corrections channel.** `Manual Correction: sponsor is SPN-4705`
  parses into rank-1 candidates; 27/27 agreed with truth, including a case
  where the hidden key lied.
- **Inferred policy, cross-validated.** Three revoked sponsors beyond the
  public manual (derived in 5/5 folds; independently confirmed by another
  participant's runtime); the staleness rule with its DIP-1 exemption (17/18 /
  11/11); registry `EMBARGO REVIEW` as visible embargo evidence (31/33).
- **Cost-sensitive decisions.** A regularised multinomial logistic model
  refines only the rule engine's weak branches, choosing the action that
  maximises expected payoff under the official asymmetric matrix. Strong rules
  (adjudicator notes: 100% accurate) are never overridden.
- **Modal printed defaults.** The scorer treats a blank exactly like a wrong
  answer, so unresolved fields serialise as the training-corpus mode. These
  defaults are serialisation-only: policy and the model always see the field
  as absent, so a guessed value can never justify an approval. This follows
  openly documented practice in Zubair Jashim's MIT-licensed `mib-intake`.

## Attribution

Ideas adapted from public MIT-licensed solutions, all independently
implemented and individually measured before adoption:

- **Zubair Jashim, `zubalr/mib-intake`**: multi-segmentation OCR merging,
  note-header crop reads, P(chosen action) as confidence, policy-separated
  modal defaults, confusion-weighted vocabulary matching, continuous
  staleness-margin features. We verified their published image end-to-end on
  the labelled training set: 132.97/150, consistent with their claim.
- **Calling Moonshots lineage (`pixmatch`)**: the closed-vocabulary NCC
  decoding concept (per Kopec & Chou). Our independent prototype scored 1/12
  on the damaged-tail cases it targets and was rejected by measurement; the
  attempt is retained under `tools/` as a documented negative result.

No predictions were copied from any participant. One examined submission
(claiming 134.72) scored 59.63 when its own published image was run on the
labelled training set; nothing from it was used.

## What failed

An honest account of dead ends, all measured: HGB trees under-performed the
regularised linear model out-of-fold (63.12 vs 63.97); structural detection of
`illegible_biometrics` peaked at 0.35 precision; stamp reading via sparse-mode
OCR found 0/30; image preprocessing (contrast/sharpen/binarise/upscale)
rescued ~6% of unreadable pages while rotation rescued half of them; the
pixel-decoder prototype mis-read 8/12; full-fitting on all 1,000 cases changed
the score by −0.05 (the model does not memorise). Earlier failures — the L2
gradient bug that saturated the softmax, the legibility gate that missed
mixed-orientation pages — are documented in `EXPERIMENTS.md` with their fixes.

## Known limitations

- A measured fraction of the corpus is genuinely unreadable: flags with no
  documentary trace (checked at four rotations, five preprocessing variants,
  sparse OCR, and colour analysis), fee lines in packets containing no fee
  receipt. Where the private labels mark such fields unrecoverable they leave
  the denominator, so the train extraction figure likely understates private
  performance.
- The `missing_evidence` decision bucket has a near-uniform truth split;
  hedging there is expected-payoff-optimal, and the scorer prices it that way
  by design.
- Development OCR ran on tesseract 5.3.4; the image ships 5.5.0. The image is
  self-consistent and all reported numbers come from the image itself.
- The staleness rule anchors to the dataset vintage (2026-07-07) in place of a
  packet receipt date, with a measured ~60-day tolerance band.

## What another week would buy

1. **A working pixel-decoder.** The closed-vocabulary NCC prototype needs
   orientation-corrected renders and a small rotation search; done well it is
   the most credible route to reading the damaged-scan tail that defeats OCR.
2. **Grouped folds.** A layout fingerprint would close the template-leakage
   question the stratified split cannot.
3. **Extraction parity on fee/purpose rows** with the best verified public
   solution (~1.5 points of measured gap).
4. **A second OCR engine** (RapidOCR/ONNX) as a disagreement signal on
   low-confidence pages.

## Reproducing

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src=/tmp/out,dst=/output \
  mib-submission /input /output/predictions.jsonl

python3 scripts/evaluate.py --truth data/train_labels.csv \
  --submission /tmp/out/predictions.jsonl
```

Refit (development folds only; fold 4 is never read):

```bash
python3 tools/build_evidence_cache.py data/train /tmp/evidence.jsonl
python3 tools/fit_decision_model.py /tmp/evidence.jsonl data/train_labels.csv --l2 0.01
python3 tools/fit_calibration.py /tmp/evidence.jsonl data/train_labels.csv
```

Everything is deterministic: no seeds because no randomness.
