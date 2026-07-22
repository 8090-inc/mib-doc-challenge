# Submission

Solution repository: <https://github.com/dumko2001/mib-doc-solution>

The public repository contains a root `Dockerfile`, `run.sh` and MIT licence.
The image accepts:

```bash
docker run --rm --network none <image> /input /output/predictions.jsonl
```

It uses no network service, API key, cloud OCR, LLM or VLM at runtime.
