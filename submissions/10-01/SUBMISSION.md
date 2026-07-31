# Submission

- **Solution repository:** https://github.com/10-01/mib-doc-solution
- **Entrypoint:** Docker image built from that repository’s `Dockerfile`
- **Runtime:** offline only (`--network none`); no LLMs, VLMs, or cloud OCR
- **Predictions:** `predictions.jsonl` for the public validation set
  (`data/validation/`), produced by the Docker pipeline (not hand-edited)

## Reproduce

```bash
git clone https://github.com/10-01/mib-doc-solution.git
cd mib-doc-solution
docker build -t mib-submission .
# then run under the challenge DOCKER_SUBMISSION.md contract
```

See the solution `README.md` and `ATTRIBUTION.md` for layout and licenses.
