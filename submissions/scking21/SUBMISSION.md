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
| Image builds | verified against the submitted commit — `docker build --platform linux/amd64` |
| Runs offline (`--network none`) | verified in-container — 25-PDF run under the invocation above |
| Image size ≤ 4 GiB uncompressed | **0.86 GiB** |
| Individual model artifact ≤ 250 MiB / total ≤ 1 GiB | no model artifacts ship; `rules/` is YAML + JSON |
| Built for `linux/amd64` | yes — `--platform linux/amd64` |
| Read-only root filesystem, only `/tmp` writable | verified in-container (25-PDF run) |
| No LLMs, VLMs, or cloud OCR at runtime | verified — no network, model, or API imports anywhere in `mib/` |
| One row per input PDF, no missing cases | 1,000/1,000 and 5,000/5,000 natively; 25/25 in-container |
| Passes `scripts/validate_submission.py` | yes, with `--require-complete` |
| Deterministic | two independent full **native** runs are byte-identical |
| In-container output equals native output | **not verified — see below** |

### What the container run does and does not establish

The 25-PDF container run establishes that the image builds from the submitted
commit, starts, honours `--network none` and a read-only root, reads only the
mounted input, and writes a schema-valid row for every input PDF.

It does **not** establish output equivalence with the native run, and on the
development host it demonstrably diverges. That host is arm64, the image is
`linux/amd64`, so the container executes under emulation at **23 s/PDF against
0.815 s/PDF native — roughly 28× slower**. At that speed the pool's 300 s
stall backstop fires and converts pending packets into fallback rows (blank
fields, `NEEDS_REVIEW`, confidence 0.05). 17 of the 25 rows came back that way.

This is an artifact of emulation rather than a defect in the pipeline: on native
`linux/amd64` the same backstop would require roughly 368 consecutive PDFs of
zero worker progress before firing. It is disclosed because the degradation is
*silent* — the run exits 0 and every row is schema-valid, so a row count alone
does not distinguish a healthy run from a stalled one. Anyone reproducing this
on Apple Silicon should expect the same and should compare row contents, not
just row counts.

### Runtime — measured natively, not in-container

Stated separately because it was **not** measured under the submitted image, and
because the emulated container timing above is not meaningful for grading: the
full 5,000-case validation run took **4,076 s wall (≈0.815 s/PDF)** executing the
package directly on the host (4 cores), and 0.68 s/PDF on the training set.
Against the 6 s/PDF average and the 30,000 s cap that is roughly 7× headroom.
Treat the native figure as indicative, not as a container benchmark on the
graders' hardware.

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
