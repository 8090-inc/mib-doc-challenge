# Submission: zubalr

**Solution repository:** https://github.com/zubalr/mib-intake

The repository contains a Docker-based, fully offline solution. Its entrypoint
accepts an input PDF directory and an output JSONL path:

```bash
docker build -t mib-intake .
```

```bash
docker run --rm --network none --cpus 4 --memory 8g --read-only --tmpfs /tmp \
  -v /path/to/pdfs:/input:ro \
  -v /path/to/output:/output \
  mib-intake /input /output/predictions.jsonl
```

## Public-data results

| Section | Out of fold |
| --- | ---: |
| Extraction | 44.15 / 50 |
| Classification | 67.88 / 80 |
| Calibration | 16.50 / 20 |
| Total | **128.53 ± 0.16 / 150** |
| Mean confidence Brier | 0.0874 |

The total above is an out-of-fold estimate over ten fold assignments: each
held-out prediction comes from a model that did not train on that packet. It is
the figure to use for expected performance on unseen packets.

The same Docker image scores **133.93 / 150** on the complete public training
set. That number is reproducible but in-sample — the model was fitted on those
rows — so it is reported for completeness rather than as a generalization
estimate.

## Approach

The solution combines:

- trust-ranked evidence extraction based on the field manual;
- local Tesseract OCR for scanned pages;
- OCR-aware matching for closed-vocabulary fields;
- structural quarantine of hidden and non-evidentiary text;
- deterministic rules for high-confidence policy evidence;
- a compact calibrated classifier for unresolved cases; and
- expected-value adjudication using the published payoff matrix.

The classifier uses document-evidence features only. It does not receive case
IDs, filenames, hidden answer content, or packet-identifying inputs.

No LLM, VLM, cloud OCR service, network request, or API key is used.

See `MEMO.md` for technical details and reproducibility notes.
