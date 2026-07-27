# Submission

Public solution repository:

<https://github.com/vibemarketer94/mib-doc-solution>

Frozen release:

- Source commit: `6899dd2efdb6b27178c9ccb99c36c978f3d57416`
- Docker image ID:
  `sha256:59cfadd9583b3c539e1faef54ea63b025d475c215a51696e06df0ccfe8f756c1`
- Validation rows: `5000`
- Prediction SHA-256:
  `aaba0f9354067cdd92c43dc0a8f735461e3e34e7bae9a77964588528c2a669c0`

The repository contains the complete offline source, pinned dependency lock,
Dockerfile, technical memo, attribution, tests, and third-party notices.

Build:

```bash
docker build -t mib-visible-submission .
```

Runtime contract:

```bash
docker run --rm --network none \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="/absolute/path/to/pdfs",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-visible-submission /input /output/predictions.jsonl
```

The image accepts exactly the input directory and output path, uses no network,
GPU, API key, model download, or writable container root, and runs as a
non-root user.
