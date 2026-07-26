# Submission — naidx0

## Solution repository

The complete, self-contained Dockerized solution lives in this same folder:

**`submissions/naidx0/solution/`** — includes a `Dockerfile`, `run.sh`, `solution.py` and supporting
modules, pinned `requirements.txt`, and `POLICY.md` documenting the adjudication rules.

Public repository: <https://github.com/naidx0/mib-doc-challenge> (path `submissions/naidx0/solution/`).

## Build & run (offline scoring contract)

```bash
# 1. Download the public data zip (see data/README.md) and unzip so data/validation/ exists.

# 2. Build the image.
docker build -t mib-submission submissions/naidx0/solution

# 3. Produce predictions for the validation set, fully offline.
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl

# 4. (optional) Score against the training labels to reproduce the reported numbers.
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl
```

The image also runs under the exact scoring harness:

```bash
python3 scripts/run_docker_submission.py \
  --repo submissions/naidx0/solution \
  --input-dir data/validation \
  --output /tmp/mib-output/predictions.jsonl \
  --manifest data/validation_manifest.csv
```

## Runtime characteristics

- Fully offline (`--network none`), CPU-only, deterministic (byte-identical across runs).
- ~4.5 CPU-seconds per PDF on 4 vCPU — inside the 6 s/PDF budget.
- Image ~1.1 GiB, well under the 4 GiB limit; no model artifacts beyond the Tesseract system package.
- Scores 123.36 / 150 on the full 1,000-case public training set with 2 catastrophic false approvals.

## Notes on `predictions.jsonl`

`predictions.jsonl` in this folder is the validation-set output produced by the command above. The
public data archive (2.88 GB of PDFs) is downloaded separately per `data/README.md`; regenerating the
file from a clean checkout reproduces it byte-for-byte.

## Compliance

- No network, API keys, or external services at runtime.
- No LLM/VLM/cloud OCR in the submitted runtime.
- No hardcoded per-case answers or lookups keyed to specific case ids; the revoked-sponsor and embargo
  tables are general policy constants learned from the training distribution (see `solution/POLICY.md`).
- Only files under `submissions/naidx0/` are added.
