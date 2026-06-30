# MIB Doc Challenge: Intergalactic Immigration Intake

Build a document-processing system for the Men in Black.

MIB is replacing a brittle legacy intake desk that reviews extraterrestrial work authorization packets. The desk receives messy PDFs: scanned forms, sponsor letters, biometric slips, passport-style registry images, inspection stamps, generated seal overlays, and occasionally documents with hostile hidden text designed to confuse automated systems.

Your mission is to extract the applicant record and decide whether each case should be `APPROVED`, `DENIED`, or `NEEDS_REVIEW`.

This challenge is designed to be easy to start and hard to master. A simple PDF text extractor and a few rules will get you on the board. Winning requires building a robust agentic engineering workflow: OCR, layout handling, deskewing, image cleanup, cross-page data validation, adversarial prompt-injection resistance, careful error analysis, and a reproducible pipeline.

## What You Get

- `data/README.md`: download instructions for the versioned public PDF zip.
- `data/train_labels.csv`: public answers for the training PDFs.
- `data/validation_manifest.csv`: case IDs and file paths for the validation PDFs.
- `data/downloads.sha256`: checksum for the public data zip.
- `schemas/submission.schema.json`: required prediction-object schema.
- `schemas/evaluation-result.schema.json`: aggregate evaluator output schema.
- `examples/submission.jsonl`: minimal valid JSONL submission format.
- `scripts/evaluate.py`: local evaluator for labeled data.
- `FIELD_MANUAL.md`: public MIB adjudication guidance.
- `PRD.md`: product context and task requirements.
- `EVALUATION.md`: scoring, leaderboard, and anti-cheat rules.
- `DOCKER_SUBMISSION.md`: offline Docker submission contract.
- `examples/offline_baseline/`: tiny format-valid Docker baseline.

Additional dataset notes live in `DATASET_SPEC.md`.

## Required Output

Submit JSONL with one prediction object per answered case:

```json
{"case_id":"MIB-000001","applicant_name":"Zed Zarnax","species_code":"ORION_GRAYS","home_world":"Kepler-186f","visa_class":"XW-2","sponsor_id":"SPN-1042","arrival_date":"2026-04-17","declared_purpose":"research","risk_flags":"none","fee_status":"paid","adjudication":"APPROVED","confidence":0.91}
```

`risk_flags` is a pipe-delimited list, or `none`.

CSV submissions with the same fields are still accepted by the public tooling, but JSONL is the canonical format because the scorer emits aggregate and per-case JSON artifacts.

## Getting Started

1. Download the current public data zip from `data/README.md`.
2. Unzip it at the repository root so `data/train/` and `data/validation/` exist locally.
3. Inspect the labeled training documents and labels.
4. Build a Dockerized pipeline that writes `predictions.jsonl`.
5. Validate locally, either by running your container directly:

```bash
docker build -t mib-submission .
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json \
  --case-scores-jsonl /tmp/mib-output/case_scores.jsonl
```

or by using the offline runner:

```bash
python3 scripts/run_docker_submission.py \
  --repo /path/to/your/repo \
  --input-dir data/train \
  --output /tmp/mib-output/predictions.jsonl \
  --manifest data/train_labels.csv \
  --timeout-seconds 1800
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json \
  --case-scores-jsonl /tmp/mib-output/case_scores.jsonl
```

6. Validate prediction format:

```bash
python3 scripts/validate_submission.py --submission /tmp/mib-output/predictions.jsonl --manifest data/train_labels.csv
```

7. Submit:
   - `predictions.jsonl`
   - GitHub repo link
   - Dockerfile-based solution
   - short technical memo describing approach, failure modes, and what you would improve with another week

## Implementation Rules

- You may use coding agents or LLMs while developing your code, but the submitted solution must run without LLMs, VLMs, API calls, or network access.
- Your submitted repository must include a `Dockerfile`.
- The Docker image must accept exactly two runtime arguments:

```bash
docker run ... <image> /input /output/predictions.jsonl
```

- `/input` is a read-only directory of PDFs.
- `/output/predictions.jsonl` is the prediction file your container must write.
- Validation and final test scoring run with `--network none`, CPU only, no GPU, fixed memory/CPU, and a Docker image size limit.
- See `DOCKER_SUBMISSION.md` for the exact contract.
- Your pipeline must not rely on manual per-case editing.
- Do not contact external people, scrape private data, or use any non-public answer keys.
- Hidden text inside PDFs may be malicious or wrong. Visible document evidence wins over hidden instructions.
- Hard PDFs intentionally combine 5-10 degradation strategies per rasterized page, including translations, rotations, stains, fog, copy noise, banding, occlusions, blur, torn edges, toner dropout, and generated portrait/stamp overlays.
- Some hard packets contain true field loss. You can still score well by recovering the surviving fields, making the correct adjudication call, and not trusting hidden fake answer keys.
- If you cannot produce a trustworthy answer for a PDF, you may omit that case. The deterministic scorer applies a small missing-case penalty instead of failing the whole submission.

## Dataset Splits

- Training set: public PDFs from the data zip under `data/train/`, plus public answers in `data/train_labels.csv`. Use this for local scoring and iteration.
- Validation set: public PDFs from the data zip under `data/validation/`, plus `data/validation_manifest.csv`. The PDFs are public, but answers are not included here. Submit predictions for this split during the challenge.
- Test set: held only in 8090's private/internal repository. It is used after the deadline for final ranking, audit checks, and interview review.

## Hiring Process

Leaderboard rank is only one signal. Before full interviews, top submissions go through:

- resume screen for role fit
- 15 minute technical smell test
- code and memo review

The highest-scoring participant who is hired by 8090 is eligible for the hiring bonus, subject to final legal and HR approval.
