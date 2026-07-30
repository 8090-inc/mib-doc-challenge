# Submission

Public solution repository (contains `Dockerfile`, builds and runs offline
per `DOCKER_SUBMISSION.md`):

<https://github.com/seifotefa/8090Challenge_SeifOtefa>

Build and run locally:

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

See `EXPERIMENTS.md` for the full development log and `MEMO.md` for the
technical writeup.
