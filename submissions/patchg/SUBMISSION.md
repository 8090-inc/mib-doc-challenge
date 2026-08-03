# Submission — patchg

## Solution repository

**Public repo:** https://github.com/patchg/mib-doc-solution  

Includes:
- `Dockerfile` + `run.sh` (two-arg offline contract)
- **MIT `LICENSE` at repository root**
- v12.1 freeze pipeline (Tesseract + rules, no network)

## Docker

```bash
docker build -t mib-submission .
docker run --rm \
  --network none \
  --cpus 4 \
  --memory 8g \
  --pids-limit 512 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Freeze summary (public train labels)

| Item | Value |
|------|-------|
| Version | v12.1 |
| Train score | **122.74 / 150** |
| Catastrophic FA | **0** |
| Throughput | **~3.98 s/PDF** under challenge Docker flags |
| Image size | ~190 MiB |

## This folder

| File | Contents |
|------|----------|
| `predictions.jsonl` | Validation-set predictions (5000 cases) |
| `MEMO.md` | Technical memo |
| `SUBMISSION.md` | This file |
