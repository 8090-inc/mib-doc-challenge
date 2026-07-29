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

The shipped Docker image scores **133.93 / 150** on the complete public training
set under the official evaluator. The repeated out-of-fold estimate is
**128.53 / 150, SE 0.16**.

| Section | Training set | Out of fold |
| --- | ---: | ---: |
| Extraction | 44.16 / 50 | 44.15 / 50 |
| Classification | 72.69 / 80 | 67.88 / 80 |
| Calibration | 17.07 / 20 | 16.50 / 20 |
| Total | **133.93 / 150** | **128.53 / 150** |
| Mean confidence Brier | 0.0732 | 0.0874 |

The training-set score is in-sample: the model was fitted on those rows. The
out-of-fold estimate averages ten fold assignments in which every held-out
prediction comes from a model that did not train on that packet, and it is the
figure to use for expected performance on unseen packets.

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
