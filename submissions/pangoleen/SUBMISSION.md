# Submission

**Solution repository:** https://github.com/pangoleen/mib-doc-challenge-solution

<!-- TEMPLATE NOTE — replace https://github.com/pangoleen/mib-doc-challenge-solution with the public GitHub URL
     once the repository is created and pushed. The repo does not exist yet;
     nothing has been published. See CHECKLIST.md. -->

**Predictions:** `predictions.jsonl` in this folder — 5,000 records, one per
PDF in `data/validation/`, produced by the Docker image built from the
repository above, in a single container run under the exact scoring flags
(`--rm --network none --cpus 4 --memory 8g --pids-limit 512 --read-only
--security-opt no-new-privileges --tmpfs /tmp:rw,nosuid,nodev,size=2g`).

- `predictions.jsonl` sha256:
  `d1cbe8212ca52865a8f5c7f501ce4d8c11ccc98d26b627bf0b516dd6a85cfe0d`
- 1,696,633 bytes (cap 25 MiB).
- Schema-validated with `scripts/validate_submission.py --require-complete`
  against `data/validation_manifest.csv`: **5,000 valid records, 0 missing**
  (identical result against `--pdf-dir data/validation`).
- Wall clock 8,449 s for 5,000 PDFs = **1.690 s/PDF** against the
  6 s/PDF budget and the 30,000 s hard cap; degradation tier 0 (OCR
  escalation ladder fully enabled throughout); peak 3.00 GiB / 8 GiB; peak
  23 PIDs / 512.
- **One pipeline error** across all 5,000 cases: `MIB-104377` tripped the
  quarantine-provenance assertion and was emitted as a fail-closed
  `NEEDS_REVIEW` row. Safe by construction — it can never become a false
  approval — and it forfeits only its own extraction points. See
  `MEMO_FULL.md` §4.

**Measured on the labeled training set** with the official
`scripts/evaluate.py`: **126.72 / 150** full-1000 (classification 65.08,
extraction 44.40, calibration 17.24, confidences 5-fold out-of-fold),
**128.46 / 150** on a held-out 200, and **127.19 / 150** re-measured by
running all 1,000 train PDFs through this same Docker image (2,670 s, 0
errors, tier 0). The container's calibration-independent offset from the host
is **−0.03 / 150**; the +0.47 on the total is the expected in-fold-vs-OOF
calibration difference, so **126.72 is the number to compare against**.
**Zero catastrophic false approvals** in every one of those runs, and 18/18 on
an 18-variant adversarial red-team corpus.

**Attribution (README.md:108).** The multi-pass OCR pooling that produced most
of the gain over our previous build was found by auditing **PR #51,
arthurmichel00** (`arthurmichel00/mib-doc-solution`); the top-band crop variant
we tested came from **PR #39, zeroinfinity03**. No code was taken from either —
the implementation, every variant, all measurements and the injection-guard are
ours, and several of their passes we measured and rejected. See `MEMO.md`.

**Memo:** `MEMO.md` in this folder (2 pages). `MEMO_FULL.md` is the
long-form version with the complete measurement detail.

---

## What the solution repository contains

| Path | What |
| --- | --- |
| `Dockerfile` | The submission image. `python:3.12-slim` (digest-pinned), no BuildKit-only syntax, builds with both the BuildKit and classic builders. 0.56 GiB arm64 / 0.61 GiB amd64 uncompressed, against the 4 GiB cap. |
| `docker/requirements.txt` | Runtime-only pins, taken verbatim from the development virtualenv, with a per-module justification for every entry and for every deliberate exclusion. |
| `docker/run.sh` | Entrypoint. Accepts exactly `<input_pdf_dir> <output_predictions_path>`. |
| `docker/selfcheck.py` | Build-time import / OCR-model / tessdata verification, so a broken image fails at `docker build`, not at scoring time. |
| `docker/build.sh` | One-command build; reports image size and every baked model artifact against the 4 GiB / 250 MiB / 1 GiB caps. |
| `docker/verify_contract.sh` | Contract harness: runs the image twice under the exact evaluator flags, checks row count, schema validity, byte-level determinism, output size, and per-PDF timing. |
| `predict.py` | CLI entrypoint (`predict.py <input_dir> <output_jsonl>`). |
| `mib/ingest.py` | Stage 1 — forensic PDF ingest, five hidden-text trap detectors, barcode decode, quarantine. |
| `mib/ocr.py` | Stage 2 — rasterize, preprocess, **additive five-pass recognition pool per scanned page**, Tesseract → 300 DPI → RapidOCR escalation ladder, rotation retries, and the injection-boilerplate detector. |
| `mib/reconcile.py` | Stage 3 — region-level text-layer/OCR union, visible-wins contradiction handling. |
| `mib/extract.py` | Stage 4 — per-template field extraction, bbox label↔value pairing, lexicon snapping, document-level signals, quarantine-leak audit. |
| `mib/noisy_channel.py`, `mib/ocr_confusion.json` | Noisy-channel decoding of degraded closed-vocabulary reads, under a character-confusion matrix measured from the corpus (13 KB, a general corpus statistic — no per-case information). |
| `mib/fusion.py`, `mib/source_reliability.json` | Fellegi–Sunter likelihood fusion over measured per-`(doc type \| read method)` error rates (5 KB, ~60 entries), replacing the hand-ordered conflict-precedence list. |
| `mib/adjudicator.py`, `mib/decision.py` | Stage 5 — field-level rule engine plus the document-level decision layer (named decision paths). The staleness rule's receipt-date epoch is *derived* from the corpus's own arrival geometry and cross-checked against the label-admissible window; see `MEMO.md`. |
| `mib/calibration.py`, `mib/calibration_table.json`, `mib/calfeatures.py`, `mib/calibration_model.json`, `mib/ev_decision.py` | Stage 6 — per-decision-path out-of-fold confidence, blended 50/50 with a 56-feature packet-level logistic model baked as a 9 KB JSON and scored in **pure Python** (no scikit-learn at run time). Confidence never feeds the adjudication. |
| `mib/lexicons.py` | Closed vocabularies mined from the training labels. |
| `mib/pipeline.py` | Parallel runner (4 worker processes), deterministic ordering, global deadline tracker, fail-closed row for any PDF that cannot be processed. |
| `scripts/recon/` | Phase-0 data forensics: structure scan, trap scan, answer-key audit. Raw JSON outputs included. |
| `scripts/redteam/` | 18-variant adversarial injection corpus generator and PASS/FAIL harness. |
| `scripts/score_train.py`, `scripts/eval_extraction.py`, `scripts/mine_mismatches.py` | Scoring and error-mining harnesses. |
| `scripts/build_confusion.py`, `scripts/build_reliability.py`, `scripts/fit_calibrator.py`, `scripts/build_calibration.py` | **Build-time** artifact fitting. Nothing here runs at inference time; scikit-learn is used only by `fit_calibrator.py` and is not installed in the image. |
| `scripts/wave3/`, `scripts/e22/`, `scripts/e23/` | Measurement harnesses for the rejected experiments (constrained ROI OCR, constraint-purity scan, transductive snapping, cross-fitted reliability control, the PDF-metadata census and the receipt-date transfer-risk sweep). |
| `tests/` | 227 tests, including adversarial-injection regression tests. |
| `notes/` | Full measurement log: `RECON.md` (data forensics), `PHASE4_LOG.md`, `PHASE45_LOG.md` (every experiment, accepted **and rejected**, with its measured deltas), `PHASE5_DOCKER.md` (packaging and contract validation), `PHASE6A_REDTEAM.md` (red-team results). |

## Compliance with the ground rules

- **Offline.** No network access at run time; all OCR models are baked into
  the image. Verified live inside `--network none --read-only`.
- **Contract.** Image takes exactly two arguments and writes JSONL to the
  requested path; nested output paths are created; an empty input directory
  exits 0 with an empty predictions file.
- **Resource limits.** Verified under the exact evaluator flags
  (`--cpus 4 --memory 8g --pids-limit 512 --read-only --tmpfs /tmp:size=2g
  --security-opt no-new-privileges`): peak memory 2.99 GiB / 8 GiB, peak PIDs
  23 / 512, well inside the 6 s/PDF average budget and the 30,000 s
  hard cap.
- **No hardcoded answers, no per-case editing, no answer keys.** Every rule
  is a named general predicate. Hidden text and barcode payloads — which in
  this corpus contain a near-accurate answer key — are quarantined by
  construction, and an assertion in `mib/extract.py` fails the case if any
  emitted value has no visible provenance. The training labels are used only
  to mine closed vocabularies, to fit four small corpus-statistic artifacts
  (character-confusion matrix, per-source error rates, per-path calibration
  table, packet calibrator — all quoted cross-fitted), and to score. **Nothing
  is learned about when to approve**: the adjudication is a hand-written rule
  cascade. The confusion matrix and reliability table decide only *which
  candidate value* a field takes, which can change a rule's input but not the
  rule; the calibrator affects only the emitted confidence, and classification
  and extraction are bit-identical with it disabled. Zero catastrophic false
  approvals were measured in every run with all four artifacts live, plus
  18/18 on the adversarial corpus.
- **Deterministic.** Repeated runs are byte-identical, and arm64 and amd64
  container outputs are byte-identical on the tested sample. Determinism is
  guaranteed *within a fixed OCR toolchain*: a 200-case A/B against a native
  host run (identical Python dependency versions, tesseract 5.5.1 instead of
  the image's 5.5.0) diverged on 21/200 rows, so the **image is the
  reproducibility artifact** and every submitted number was produced by it.
  See `MEMO.md`, "Failure modes and limitations" item 3.
- **Attribution.** No third-party solution code was reused. Third-party
  libraries are the pinned open-source dependencies listed in
  `docker/requirements.txt`.
