# Technical Memo — Shared-Substrate Portfolio with a Learned Referee

## Thesis

The gold labels are post-arbitration truth: scoring well requires not just
reading pages but deciding which page to believe, because the corpus plants
decoy pages, damaged adjudicator notes, and fields that contradict each
other across a packet. Rather than build one more pipeline, this submission
runs three complementary open-source pipelines over a single shared
render/OCR substrate and merges their full evidence — votes, confidences,
decision paths, field candidates, injection and completeness signals — with
a frozen learned referee trained out-of-fold on the 1,000 labeled cases.

## Architecture (per input directory)

1. **Substrate (once per PDF):** render at 300 DPI grayscale, one
   13-configuration Tesseract union over the rendered pages, a
   visible/hidden glyph classifier over the text layer (white-ink,
   tiny-font, off-crop detection; ported from @scking21), and
   CropBox→MediaBox widening (ported from @zubalr). OCR is lazy: pages
   whose text layer passes a length gate (`MIB_OCR_GATE=120`) skip
   rasterization unless a pipeline's own conditional triggers request it.
2. **Three vendored pipelines** (adapted at their I/O seams only, decision
   logic unmodified; see `ATTRIBUTION.md`): @thegoleffect, @tylergibbs1
   (the public MIT revision), and @zubalr — including zubalr's two-phase
   corpus aggregation (per-case extraction, then corpus-level staleness /
   revoked-sponsor / median-date passes), which the adapter preserves by
   running phase 2 over the whole input directory.
3. **Note evidence:** an original dual-pass adjudicator-note reader plus
   two damage-specialist probes (faded-ink note recovery, margin-note
   device detection). A note finding corroborated by the reader or by ≥2
   pipelines is guardrail-grade: it locks the decision and the learned
   layers may not override it (277/277 on train). A disqualifying-flag
   consensus of ≥3 pipelines likewise locks DENIED (58/58 on train).
4. **Referee (frozen artifacts in `artifacts/`):** anchor-relative backoff
   posterior tables (state = anchor vote/confidence bucket, agreement
   count, top dissent, note signal, injection, completeness; Laplace
   smoothing, minimum-support backoff, anchor pseudo-count blend) give a
   base posterior; decisions maximize expected value under the scoring
   asymmetry (+8 correct / +2 punt / −4 false approval). On top sit three
   gated heads trained on the merged evidence: a 5-seed-averaged
   HistGradientBoosting decision head that overrides the base pick only
   when its EV margin exceeds a threshold chosen on inner out-of-fold data
   (adopted only after ≥4/5 outer folds showed non-negative payoff), a
   confidence head predicting correctness of the final pick, and a
   field-level candidate head with per-field adoption gates (8 of 9 fields
   adopted). Fields the head declines fall back to per-field strategies
   (solo-best vs accuracy-weighted voting) chosen out-of-fold.

Everything learned was fit with nested cross-validation and frozen; the
runtime is deterministic, offline, and LLM-free.

## Honest numbers

- 5-fold cross-validated train score (all learned components out-of-fold):
  **142.59 / 150**.
- One-shot sealed 200-case holdout (fresh pre-registered seed, spent once),
  scored on artifacts fit only on the other 800: **142.15 / 150**
  (CV→holdout gap 0.44; calibration 19.22/20).
- False approvals: 2/200 on the sealed holdout, 6/1000 on dev CV. These are
  expected-value-priced, not accidents: the residual error mass sits on
  packets whose planted evidence is unreadable at any OCR budget, where the
  payoff matrix makes the ensemble's pick optimal in expectation.
- Runtime in the official Docker contract (4 vCPU / 8 GiB, `--network
  none`): **3.70 s/PDF average** on a 200-case timed run (budget 6.0),
  byte-identical across repeated runs.
- Validation predictions: 5,000/5,000 cases, sha256 `ca6f9b629e99b361c04c020c2b59c60d82e88719de3ee8f90118fdc6f53953ce`.

## What is original vs. vendored

Vendored (MIT, licenses preserved, attributed in `ATTRIBUTION.md`): the
three constituent pipelines under `engine/deps_*`. Original: the substrate
and adapters, the note reader and damage probes, the feature builder, the
referee (tables, gated heads, EV layer, calibration), and the measurement
study behind every design choice.

## Selected negative results (kept for honesty)

- Literal field-manual rules are traps by design: "clean fields → approve"
  is right only 61% of the time (the corpus plants approvable-looking
  packets carrying damaged review notes), and the waived-fee rule scores
  44%. A full deterministic rule engine added nothing as a voter and was
  harmful as a veto; it survives only as features to the heads.
- A damage-specialist CRNN reader (83.6% exact-match on held-out damaged
  rows) was a measured NO-GO: in a pre-registered fixes-vs-breaks gate,
  10 of 25 breaks were pixel-perfect reads of pages whose printed values
  contradict gold. Reading pixels better cannot beat pages that lie; the
  pipelines' packet-level arbitration already encodes what matters.
- Two candidate false-approval guards (flags-seen approve-block, faded-note
  corroboration) failed count-verification (~79% right) and were rejected;
  the guardrail lock on note/DQ consensus is kept because it is measured at
  ~100% and costs nothing.
- Label-free drift checks train→validation: the rule-based constituents'
  decision mixes are stable (total variation 0.01–0.04); the one
  ML-heavy constituent shifts (−11 pp approvals). The referee's backoff
  tables and abstention gates were designed for exactly this: unseen
  states degrade to broader tables, and the heads only fire on states they
  proved out-of-fold.

## Failure modes and limits

- The posterior tables are aggregate statistics from train; the backoff
  ladder (exact state → broader state → anchor prior) degrades gracefully
  under shift, but the anchor reliability prior could weaken.
- A handful of train cases are missed by every constituent and by the
  ensemble; their disqualifying evidence appears genuinely unrecoverable
  at this OCR budget.
- Cross-machine numerical sensitivity is real and was measured rather than
  assumed. Running the identical image logic on two machines over the same
  50-case corpus, 48/50 adjudications and all extracted fields except
  `sponsor_id` (2 cases) agree, while 15 confidences differ slightly. It is
  not the OCR stack, the corpus, or the dependency set: tesseract 5.3.0 /
  leptonica 1.82.0 / Debian 12 and all 20 Python packages (direct and
  transitive) are identical, worker count is fixed at 4, and pinning
  `PYTHONHASHSEED` changed nothing (byte-identical output across two
  independent full runs). Holding the corpus constant reproduced the gap
  exactly, and varying the corpus alone (50 vs 500 cases) moved 5
  confidences and zero adjudications. What remains is the CPython build and
  CPU SIMD dispatch: float differences at the decision boundary flip cases
  where the head's EV margin sits near the adoption threshold. Each
  environment is internally deterministic; the effect is inherent to
  floating-point reduction order across machines, so graders should expect
  the same order of variation on their hardware.

## Reproduction

`docker build -t mib-submission .` then
`docker run --rm --cpus=4 --memory=8g --network none -v <in>:/input:ro
-v <out>:/output mib-submission /input /output/predictions.jsonl`
reproduces the reported numbers deterministically.
