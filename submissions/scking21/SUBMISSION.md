# Submission — scking21

## Solution repository

https://github.com/scking21/mib-solution

The predictions in this folder use the follow-up fix at commit
[`2da6eac`](https://github.com/scking21/mib-solution/commit/2da6eac5b0013b49d19347f788691358d4efc24d).

The repository contains the `Dockerfile` at its root, along with the `mib/`
package, `rules/` (policy, fitted posteriors, and two small fitted model
artifacts), `run.sh`, and `tests/`.

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

## How these predictions were produced

This follow-up starts from the PR #31 artifact at commit `ee5ef86`, whose
SHA-256 was
`aa3cd72c80d0927ccd5ae2864eaba8d78908799818964f6556abbaaa84bf7c7f`.
The updated extractor was rerun on the four affected validation PDFs. It rejects
closed-vocabulary values and neighboring headings, then continues scanning for
a real name. Two names were recovered and two remain blank. All other fields and
all other rows are unchanged.

| Case | Previous applicant name | Updated applicant name |
|---|---|---|
| MIB-100159 | `Titan Freeport` | *(blank)* |
| MIB-100859 | `Observed Match` | `Tekquell Veequell` |
| MIB-102682 | `Spectes Observed Match` | `Veemora Veerix` |
| MIB-104895 | `Luyten-b Oriul Ixokesh` | *(blank)* |

`predictions.jsonl` SHA-256:
`ffe10275d91e26e0d4a40de67d64e9d1ae6975f1ddb7fbc0da781d452a5001b8`

The artifact contains 5,000 rows. The focused diff is exactly four
`applicant_name` changes and zero changes to any other field.

## Verified against the submission contract

| Requirement | Status |
|---|---|
| Image builds | verified from the submitted commit |
| Runs offline (`--network none`) | verified by the PR #31 full run; the fix adds no network path |
| Read-only root, only `/tmp` writable | verified — same run |
| Image size ≤ 4 GiB uncompressed | **0.82 GiB** |
| Individual model artifact ≤ 250 MiB | **3.01 MiB** (`rules/blend.pkl`); `rules/correctness.json` is 4 KiB |
| Total model artifacts ≤ 1 GiB | **3.02 MiB** |
| Built for `linux/amd64` | the `Dockerfile` targets it; see the focused regeneration provenance above |
| No LLMs, VLMs, or cloud OCR at runtime | verified — no network, foundation model, or API import anywhere in `mib/` |
| One row per input PDF, no missing cases | 5,000/5,000 with 0 missing case ids |
| Passes `scripts/validate_submission.py` | yes, with `--require-complete` |
| No hardcoded validation answers, no per-case edits | yes — see `MEMO.md` |

### Runtime

**2.49 s/PDF**, measured in-container on the full 5,000-case validation set under
the exact contract limits above. Against the 6 s/PDF average and the 30,000 s
cap that is roughly 2.4× headroom on the per-PDF budget. Throughput is uneven —
text-layer packets run at ~25/min while OCR-heavy stretches drop below 1/min —
so a short sample is not representative; the figure above is the whole-run
average.

## Result on the public training set

| Section | Score |
|---|---|
| Field extraction | 43.47 / 50 |
| Classification | 68.86 / 80 |
| Confidence calibration | 16.67 / 20 |
| Missing-case penalty | −0.00 / 10 |
| **Deterministic total** | **129.00 / 150** |
| Catastrophic false approvals | 8 |

**Read this number in the light of `EVALUATION.md:117`.** The public
`train_labels.csv` omits `unrecoverable_fields`, so the figure above is charged
for every field whose visible evidence was cut out, washed out, torn away, or
present only in untrusted hidden text. Private scoring removes those from each
case's extraction maximum. Of our 1,131 wrong fields, 398 have their true value
**only** in quarantined hidden text and 665 are absent from visible evidence
entirely; excluding just the first group raises extraction from 43.72 to 45.74 on
the same predictions. We decline those 398 deliberately — see `MEMO.md`.

`MEMO.md` documents the approach, the failure modes, and the measurements behind
the levers that were tried and rejected.

## Attribution

All solution code is original. Third-party runtime dependencies are the ones
pinned in `requirements.txt` (pdfplumber, pypdfium2, pytesseract, Pillow,
opencv-python-headless, numpy, PyYAML, scikit-learn, rapidfuzz) plus the
Tesseract and Poppler system packages installed in the image. No other
participant's code or predictions were used.
