# MIB Doc Challenge — Build Plan

**Goal (measurable end state):** an offline, Dockerized pipeline that reads a directory of PDF
case packets and writes `predictions.jsonl` scoring well on the challenge's deterministic rubric
(150 pts = classification 80 + extraction 50 + calibration 20 − missing≤10), with **zero
catastrophic false approvals**, full prompt-injection resistance, and reproducible runs on the
private test set from a clean checkout.

## Phases

### Phase 1 — Evidence layer (ingest)
Parse each PDF into per-page structured evidence. Read the text layer via PyMuPDF with per-span
color + bbox; classify image-only pages and OCR them (Tesseract) with grayscale/contrast/deskew
preprocessing and orientation correction. Tag every text span as trusted or untrusted.
**Done when:** every page yields a normalized bag of (label, value, trust) evidence; image pages
produce OCR text; the trust tagger flags white/off-crop/injection spans.

### Phase 2 — Field extraction + canonicalization
Map evidence to the 12 output fields using source precedence (I-8090 > B-13 > Registry > sponsor
letter). Fuzzy-canonicalize OCR'd enums (species_code, home_world, visa_class, fee_status,
risk_flags) against known vocabularies. Never fill a field from untrusted text.
**Done when:** clean text-layer fields extract near-perfectly; OCR fields recovered via fuzzy match;
injected values never appear.

### Phase 3 — Adjudication + confidence
Apply the verified decision policy (see `solution/POLICY.md` / code comments), ordered so hard
denials fire before review signals. Emit calibrated confidence ≈ P(correct).
**Done when:** classification ≥ 60/80 on the labeled corpus and 0 catastrophic false approvals.

### Phase 4 — Robustness + contract
Parallelize across 4 vCPU, per-PDF timeout + try/except isolation, atomic JSONL write, deterministic
output, Docker image with tesseract + poppler under the size/offline limits.
**Done when:** the container runs `--network none` and processes the corpus without crashing.

## Standing gate (run after every phase)
```
venv/bin/python solution/solution.py corpus/train /tmp/preds.jsonl
python3 scripts/evaluate.py --truth corpus/labels_subset.csv --submission /tmp/preds.jsonl
```
Check: total score, classification /80, extraction /50, calibration /20, catastrophic count (must be 0),
confusion matrix.

## Final gate
Adversarial review (independent) of the full pipeline — injection resistance, edge cases, Docker
contract, offline compliance, no hardcoded per-case answers — fix-and-re-review until releasable;
then a clean container run.

## Verified policy (reverse-engineered from 1,000 training labels)
See `solution/POLICY.md`. Key rules (all verified against real labels): disqualifying risk flags →
DENIED; revoked sponsor on non-DIP-1 → DENIED; TRANSIT-7 → DENIED; unpaid fee w/o waiver → DENIED;
stale arrival (>180 d before batch-max) on non-DIP-1 → DENIED; fee unknown or missing arrival →
NEEDS_REVIEW; review-only flags → NEEDS_REVIEW; cross-page contradictions → NEEDS_REVIEW; else
APPROVED. Adjudicator-note findings and injection-text traps handled explicitly.

## Local-later steps (not possible in the online mobile session)
- Download the 2.88 GB public data zip (Hugging Face) and unzip to `data/`.
- Generate `predictions.jsonl` for all 5,000 validation PDFs (≈ hours of OCR).
- `docker build` + `run_docker_submission.py` full offline run under the scoring limits.
These are documented in `submissions/naidx0/SUBMISSION.md`.
