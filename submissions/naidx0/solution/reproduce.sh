#!/usr/bin/env bash
# Turnkey reproduction of the MIB Doc Challenge submission.
# Run from the root of the challenge repository (the dir containing scripts/ and data/).
# Steps that need the network (data download, docker build) run first; scoring is offline.
set -euo pipefail

REPO_ROOT="$(pwd)"
SOLUTION_DIR="submissions/naidx0/solution"
DATA_ZIP="mib-doc-challenge-public-data-v2026-07-07.zip"
OUT_DIR="/tmp/mib-output"
mkdir -p "$OUT_DIR"

# 1. Download + unzip the public data (skip if data/validation already exists).
if [ ! -d data/validation ]; then
  echo ">> Downloading public data (~2.9 GB)..."
  if command -v hf >/dev/null 2>&1; then
    hf download arjun-krishna1/mib-doc-challenge-data "$DATA_ZIP" --repo-type dataset --local-dir .
  else
    curl -L -o "$DATA_ZIP" \
      "https://huggingface.co/datasets/arjun-krishna1/mib-doc-challenge-data/resolve/main/$DATA_ZIP"
  fi
  echo ">> Verifying checksum..."
  echo "a9bb8c1bbf51346ebf49c2e3e1acdb7a5d6cd0760162767b0d133c7b7200f3c4  $DATA_ZIP" | shasum -a 256 -c -
  unzip -q -o "$DATA_ZIP"
fi

# 2. Build the offline image.
echo ">> Building Docker image..."
docker build -t mib-submission "$SOLUTION_DIR"

# 3. Generate validation predictions (fully offline).
echo ">> Generating validation predictions..."
docker run --rm --network none \
  --mount type=bind,src="$REPO_ROOT/data/validation",dst=/input,readonly \
  --mount type=bind,src="$OUT_DIR",dst=/output \
  mib-submission /input /output/predictions.jsonl
cp "$OUT_DIR/predictions.jsonl" "$SOLUTION_DIR/../predictions.jsonl"
echo ">> Wrote submissions/naidx0/predictions.jsonl"

# 4. Sanity-check the format.
python3 scripts/validate_submission.py \
  --submission "$OUT_DIR/predictions.jsonl" \
  --manifest data/validation_manifest.csv

# 5. (optional) Score against the public training labels to reproduce the reported numbers.
echo ">> Scoring on the training split (offline)..."
docker run --rm --network none \
  --mount type=bind,src="$REPO_ROOT/data/train",dst=/input,readonly \
  --mount type=bind,src="$OUT_DIR",dst=/output \
  mib-submission /input /output/train_predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission "$OUT_DIR/train_predictions.jsonl" \
  --output-json "$OUT_DIR/evaluation.json"

echo ">> Done. Validation predictions: submissions/naidx0/predictions.jsonl"
