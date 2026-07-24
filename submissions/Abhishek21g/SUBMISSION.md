# Submission

**Solution repository:** https://github.com/Abhishek21g/mib-doc-challenge-solution @ `08947bd`

**Public-train score:** **130.72 / 150** (extraction 45.01, classification 68.69, calibration 17.02; **CFA 0**)

The repository includes a `Dockerfile` that accepts:

```bash
docker run ... <image> /input /output/predictions.jsonl
```

Build and run offline with `--network none` as specified in `DOCKER_SUBMISSION.md`.
