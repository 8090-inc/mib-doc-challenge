#!/usr/bin/env bash
# Full train-set evaluation loop: pipeline -> official evaluator -> error report.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=${1:-dev/train_run}
mkdir -p "$OUT"

PYTHONPATH=solution python3 -m mib_pipeline.cli data/train "$OUT/predictions.jsonl"
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission "$OUT/predictions.jsonl" \
  --output-json "$OUT/evaluation.json" \
  --case-scores-jsonl "$OUT/case_scores.jsonl" || true
python3 scripts_dev/error_report.py --run "$OUT" | tee "$OUT/error_report.txt"
