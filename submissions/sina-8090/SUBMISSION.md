# Submission — sina-8090

- Solution repository: this repository, branch `claude/code-challenge-solve-kk8uzf`
  (root `Dockerfile`; entrypoint `run.sh <input_pdf_dir> <output_predictions_path>`).
- Predictions: `predictions.jsonl` in this folder — produced by the Docker image
  under the exact scoring contract (`--network none --cpus 4 --memory 8g
  --pids-limit 512 --read-only --tmpfs /tmp:size=2g`).
- Technical memo: `MEMO.md` in this folder (copy of the repo root memo).
- Note: this is an internal trial of the challenge by 8090 staff, not a
  leaderboard entry.
