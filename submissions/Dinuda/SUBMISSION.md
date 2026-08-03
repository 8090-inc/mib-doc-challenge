# Submission

- Candidate: Dinuda
- Public solution repository: <https://github.com/Dinuda/mib-solution>
- Runtime: Docker, offline, CPU-only
- Entrypoint: `run.sh <input_pdf_dir> <output_predictions_path>`

## Build and run

```bash
docker build -t mib-solution .
mkdir -p /tmp/mib-output
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-output,dst=/output \
  mib-solution /input /output/predictions.jsonl
```

The image contains only `artifacts/vocab.json`,
`artifacts/manual_finding_gate.joblib`, and
`artifacts/path_calibration_bundle.joblib`. These were derived from the public
training set only; no validation labels, pseudo-labels, persistent validation
features, case-specific rules, cloud APIs, or network access are used.
