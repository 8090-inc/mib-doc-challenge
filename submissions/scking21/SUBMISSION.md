# Submission — scking21

## Solution repository

https://github.com/scking21/mib-solution

The predictions in this folder were produced by commit
[`19a6643`](https://github.com/scking21/mib-solution/commit/19a6643d02cdd0a39f82127a92e87dfa8733c5c6).

The repository contains the `Dockerfile` at its root, along with the `mib/`
package, `rules/` (policy and fitted posteriors), `run.sh`, and `tests/`.

## Running it

The image takes an input directory of PDFs and an output path, exactly as
`DOCKER_SUBMISSION.md` specifies:

```bash
docker build --platform linux/amd64 -t mib-submission .

docker run --rm --network none \
  --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v /path/to/pdfs:/data/pdfs:ro \
  -v /path/to/out:/data/out:rw \
  mib-submission /data/pdfs /data/out/predictions.jsonl
```

## Verified against the submission contract

| Requirement | Status |
|---|---|
| Runs offline (`--network none`) | verified in-container — 25-PDF smoke test under the invocation above |
| Image size ≤ 4 GiB uncompressed | **0.86 GiB** |
| Individual model artifact ≤ 250 MiB / total ≤ 1 GiB | no model artifacts ship; `rules/` is YAML + JSON |
| Built for `linux/amd64` | yes — `--platform linux/amd64` |
| Read-only root filesystem, only `/tmp` writable | verified in-container (25-PDF smoke test) |
| No LLMs, VLMs, or cloud OCR at runtime | verified — no network, model, or API imports anywhere in `mib/` |
| One row per input PDF, no missing cases | 1,000/1,000 and 5,000/5,000 |
| Passes `scripts/validate_submission.py` | yes, with `--require-complete` |
| Deterministic | two independent full runs are byte-identical |

### Runtime — measured natively, not in-container

Stated separately because it was **not** measured under the submitted image:
the full 5,000-case validation run took **4,082 s wall (≈0.82 s/PDF)** executing
the package directly on the host (4 cores), and 0.68 s/PDF on the training set.
That is a strong signal against the 6 s/PDF average and the 30,000 s cap, but
the only container-verified run is the 25-PDF offline smoke test. Treat the
native figure as indicative, not as a container benchmark on the graders'
hardware.

## Result on the public training set

Scored with the challenge's own `scripts/evaluate.py`:

| Section | Score |
|---|---|
| Field extraction | 41.70 / 50 |
| Classification | 64.72 / 80 |
| Confidence calibration | 15.89 / 20 |
| Missing-case penalty | −0.00 / 10 |
| **Deterministic total** | **122.31 / 150** |
| Catastrophic false approvals | 10 |

See `MEMO.md` for the approach, the failure-mode analysis behind those numbers,
and what the remaining headroom actually consists of.

## Attribution

All solution code is original. Third-party runtime dependencies are the ones
pinned in `requirements.txt` (pdfplumber, pypdfium2, pytesseract, Pillow,
opencv-python-headless, numpy, PyYAML, scikit-learn, rapidfuzz) plus the
Tesseract and Poppler system packages installed in the image. No other
participant's code or predictions were used.
