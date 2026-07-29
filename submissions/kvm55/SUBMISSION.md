# Submission

**Solution repository:** https://github.com/kvm55/mib-intake

Public, MIT licensed, includes a `Dockerfile` at the repository root.

## Build and run

```bash
docker build -t mib-submission .

docker run --rm \
  --network none --cpus 4 --memory 8g --pids-limit 512 --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

No network, API keys, or external services are required at runtime. No
LLM, VLM, or cloud OCR is used anywhere in the pipeline. There are no model
artifacts: the solution is deterministic rules, classical CV, and offline
Tesseract.

## Self-reported results

| Split | Cases | Total | Catastrophic false approvals |
|---|---|---|---|
| Iteration split (800 of the public train set) | 800 | 109.4 / 150 | 0 |
| Held-out split, scored once, never tuned against | 200 | 107.0 / 150 | 0 |

Measured in the scoring container under the published flags: 1.4 s/PDF
against the 6 s/PDF budget, and byte-identical output across repeated runs.

`predictions.jsonl` in this folder is the validation-set output of that same
image.

See `MEMO.md` for the approach, the failure modes, and what I would change
with more time.
