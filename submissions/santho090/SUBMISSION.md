# Submission: santho090

## Repository

<https://github.com/santho090/mib-doc-challenge>
(this fork; the pipeline lives in `solution/`, the Dockerfile is at the repository root)

## Entrypoint

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Runtime

| Property | Value |
| --- | --- |
| Image size (uncompressed) | ~0.11 GiB (limit 4 GiB) |
| Model artifacts | no weights trained on challenge data or bundled separately; distribution-packaged Tesseract English/orientation data only |
| Network use at runtime | none; verified with `--network none` |
| OCR/runtime | measured final image: Tesseract 5.5.0, classical CV, deterministic rules, no hosted services |
| Throughput | 1.21 s/PDF on 4 vCPU over 1,000 cases, including bounded rescue (budget 6 s/PDF); see [SCORES](https://github.com/santho090/mib-doc-challenge/blob/main/SCORES.md) |
| Architecture check | linux/amd64 build succeeded; eight-case smoke output matched arm64 |
| Writable paths needed | `/tmp` and the requested output mount; container root remains read-only |
| Validation artifact | 5,000 valid records, zero missing; 1,677,695 bytes; SHA-256 `27787cae7369fc1150f253590882e49d4fd6960c1d4e04d8ef40712c6e087a57` |

Predictions are finalized after the batch epoch and policy pass, so a hard kill during
extraction leaves no partial JSONL. The challenge hard limit for the 5,000-file run is
30,000 seconds.

## Documentation

- [README](https://github.com/santho090/mib-doc-challenge/blob/main/README.md): build, run, and scoring
- [Architecture](https://github.com/santho090/mib-doc-challenge/blob/main/ARCHITECTURE.md): flow, policy order, and provenance
- [Technical memo](./MEMO.md): approach, failure modes, and next improvements
