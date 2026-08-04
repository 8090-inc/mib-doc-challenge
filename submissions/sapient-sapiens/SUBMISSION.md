# Submission — sapient-sapiens

## Links

- **Solution repository** (public, contains a `Dockerfile`):
  https://github.com/sapient-sapiens/evidence-ladder
- **Submission form:** in progress
- **Memo:** `MEMO.md` in this folder
- **Predictions:** `predictions.jsonl` in this folder (validation set)

This pull request adds files only under `submissions/sapient-sapiens/`.
The solution code lives in the linked repository above — it is **not**
vendored into this challenge repo.

## Reproduce

```bash
git clone https://github.com/sapient-sapiens/evidence-ladder
cd evidence-ladder
docker build -t evidence-ladder .
docker run --rm --network none --read-only \
  --cpus 4 --memory 8g --pids-limit 512 \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  evidence-ladder /input /output/predictions.jsonl
```

The image accepts exactly `<input_pdf_dir> <output_predictions_path>`, runs
CPU-only, and uses no LLMs, VLMs, cloud OCR, or network services at runtime.

## Checklist

- [ ] I filled out the submission form linked above
- [x] This PR only adds `submissions/sapient-sapiens/predictions.jsonl`, `MEMO.md`, and `SUBMISSION.md`
- [x] `predictions.jsonl` passes `scripts/validate_submission.py` against `data/validation_manifest.csv`
- [x] My solution repository is public and includes a `Dockerfile`
- [x] My Docker image runs offline (`--network none`) and accepts `<input_pdf_dir> <output_predictions_path>`
- [x] My submitted runtime uses no LLMs, VLMs, cloud OCR, or network services
- [x] Model artifacts fit the size limits in `DOCKER_SUBMISSION.md`
- [x] No hardcoded validation answers and no manual per-case edits
- [x] My memo describes my approach, failure modes, and what I would improve with another week
