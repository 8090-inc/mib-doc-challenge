# Submission: zubalr

**Solution repository:** https://github.com/zubalr/mib-intake

The repository is public and includes a `Dockerfile` at its root. The solution
is fully offline, and its entrypoint accepts an input PDF directory and an
output JSONL path:

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

The Docker image scores **137.83 / 150** on the complete public training set
under the official evaluator.

| Section | Training set |
| --- | ---: |
| Extraction | 45.31 / 50 |
| Classification | 74.45 / 80 |
| Calibration | 18.07 / 20 |
| Total | **137.83 / 150** |
| Mean confidence Brier | 0.0482 |
| Catastrophic false approvals | 12 |

This is in-sample: the model was fitted on these packets. It is a
reproducibility figure, not an estimate of performance on unseen packets, and
it comes from running the image itself under the submission constraints.

## Approach

The solution combines:

- trust-ranked evidence extraction based on the field manual;
- local Tesseract OCR plus a lower-trust RapidOCR fallback for scanned pages;
- OCR-aware matching for closed-vocabulary fields;
- structural quarantine of hidden and non-evidentiary text;
- deterministic rules for high-confidence policy evidence;
- a compact calibrated classifier for unresolved cases; and
- expected-value adjudication using the published payoff matrix, with approval
  blocked when the packet's risk page is unreadable.

The classifier uses document-evidence features only. It does not receive case
IDs, filenames, hidden answer content, or packet-identifying inputs.

No LLM, VLM, cloud OCR service, network request, or API key is used.

See `MEMO.md` for technical details and reproducibility notes.
