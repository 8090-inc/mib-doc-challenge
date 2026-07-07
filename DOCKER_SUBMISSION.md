# Docker Submission Contract

The submitted solution must run offline in Docker. The goal is to make scoring simple for 8090, simple for candidates to reproduce, and hard to master without turning the contest into an API-spend competition.

## Candidate Contract

Your repository must include a `Dockerfile`.

The built image must accept two arguments:

```bash
<input_pdf_dir> <output_predictions_path>
```

Example:

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

Your container must write valid predictions to the requested output path. JSONL is canonical; CSV with the same fields is accepted for compatibility.

## Scoring Runtime

8090 will run submitted images with:

```bash
docker run --rm \
  --network none \
  --cpus 4 \
  --memory 8g \
  --pids-limit 512 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  <image> /input /output/predictions.jsonl
```

The image should not assume a writable working directory. Write temporary files under `/tmp` and final output under `/output`.

8090 can run the same contract with:

```bash
python3 scripts/run_docker_submission.py \
  --repo /path/to/submission-repo \
  --input-dir data/validation \
  --output /tmp/mib-score/predictions.jsonl \
  --manifest data/validation_manifest.csv
```

## Limits

- Docker image size: max 4 GiB uncompressed, measured by `docker image inspect`.
- Individual model artifact: max 250 MiB.
- Total model artifacts: max 1 GiB.
- Runtime budget: 6 seconds per PDF on average, on 4 vCPU / 8 GiB RAM. OCR-heavy pipelines should parallelize across the 4 vCPUs to stay inside it.
- Runtime hard limit: 8 hours for the 5,000-PDF validation set. Containers still running at the limit are stopped and scored on whatever output exists.
- The private test set is scored with the same 6-seconds-per-PDF budget.
- Output predictions file: max 25 MiB.
- No GPU.
- No network access.
- No API keys or external services.

## Allowed

- Tesseract or other offline OCR engines.
- OpenCV, Pillow, Poppler, pdfium, and similar document/image tooling.
- Hand-written rules and heuristics.
- Classical machine learning.
- Small task-specific local models that fit the artifact limits.
- Candidate-trained models using the public training data.

## Not Allowed

- LLMs in the submitted runtime.
- VLMs or multimodal foundation models in the submitted runtime.
- Cloud OCR, document AI APIs, or any network service.
- Runtime package downloads.
- Calling out to a local daemon outside the container.
- Hardcoding validation-set or private test-set answers.
- Manual per-case output editing.

## Why This Design

The Docker/no-network contract creates a useful gradient:

- a beginner can submit a small Python/Tesseract image and get a score
- a solid engineer can build robust preprocessing, OCR fallbacks, and validators
- a top engineer can build a full offline document pipeline with page classification, deskewing, evidence aggregation, uncertainty handling, and adversarial-text filtering

The best submissions should win because of engineering quality, not because they had access to a better hosted model.

## Minimal Entrypoint

A minimal `run.sh` inside a candidate repository can look like:

```bash
#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:?usage: run.sh <input_pdf_dir> <output_path>}"
output_path="${2:?usage: run.sh <input_pdf_dir> <output_path>}"

python3 /app/solution.py "$input_dir" "$output_path"
```

See `examples/offline_baseline/` for a tiny format-valid Docker submission. It is intentionally weak, but it is useful for testing the offline runner.
