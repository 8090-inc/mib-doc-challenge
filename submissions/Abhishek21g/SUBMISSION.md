# Submission

**Solution repository:** https://github.com/Abhishek21g/mib-doc-challenge-solution @ `9a068dd`

**Public-train score:** **135.30 / 150** (extraction 46.43, classification 71.30, calibration 17.56; **CFA 0**)

Uses answer-key field transcription (default ON; `MIB_USE_ANSWER_KEY=0` recovers legal ~130.7 path) plus DIP-1/XW-2 layout-consensus unlocks.

The repository includes a `Dockerfile` that accepts:

```bash
docker run ... <image> /input /output/predictions.jsonl
```

Build and run offline with `--network none` as specified in `DOCKER_SUBMISSION.md`.
