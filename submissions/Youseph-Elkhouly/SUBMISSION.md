# Submission

Public solution repository (contains `Dockerfile`, builds and runs offline
per `DOCKER_SUBMISSION.md`):

<https://github.com/Youseph-Elkhouly/mib-doc-challenge/tree/main/solution>

Build and run locally:

```bash
docker build -t mib-submission solution/
docker run --rm --network none --cpus 4 --memory 8g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

See `solution/EXPERIMENTS.md` for the full development log and
`solution/MEMO.md` (also included in this folder) for the technical writeup.
