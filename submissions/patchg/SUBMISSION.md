# Submission — patchg

## Solution repository

**Public repo:** https://github.com/patchg/mib-doc-solution

*(If the URL differs after you create the repo, update this line before opening the PR.)*

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

## Freeze summary

| Item | Value |
|------|-------|
| Version | v12.1 |
| Train score (public labels) | **122.74 / 150** |
| Catastrophic FA | **0** |
| Throughput | **~3.98 s/PDF** (4 vCPU, challenge flags) |
| Image size | ~190 MiB |
| Stack | Tesseract + PyMuPDF + rule policy (offline) |

## This folder

| File | Contents |
|------|----------|
| `predictions.jsonl` | Validation-set predictions (5 000 cases) |
| `MEMO.md` | Technical memo |
| `SUBMISSION.md` | This file |
