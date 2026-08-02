# Submission — Tejasvini Chawla

**Solution repository:** https://github.com/TejasviniChawla/mib-doc-challenge-solution

The repository contains a `Dockerfile` implementing the offline submission contract:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

No network, no API keys, CPU-only; ~1.2 s/PDF on 4 vCPUs against the 6 s/PDF budget.
See `MEMO.md` (also in this folder) for the technical write-up.
