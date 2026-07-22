# Submission

Public solution repository:

https://github.com/afifi-yusuf/mib-doc-solution

The repository includes a `Dockerfile`. Offline entrypoint:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```
