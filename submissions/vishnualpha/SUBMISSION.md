# Submission — vishnualpha

## Solution repository

<https://github.com/vishnualpha/mib-doc-challenge-solution>

Public, Dockerfile at the repository root. The offline container contract is
verified on every push by `.github/workflows/docker.yml` on a native
`linux/amd64` runner — build, size caps, a run under `--network none
--read-only`, schema-valid output, and byte-identical output across two runs.

```bash
docker build --platform linux/amd64 -t mib-submission .

docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Contents

| File | What it is |
| --- | --- |
| `predictions.jsonl` | 5,000 validation predictions |
| `MEMO.md` | Technical memo: approach, failure modes, next steps |
| `SUBMISSION.md` | This file |

## Verified numbers

Held-out estimate from `tools/holdout_eval.py`, which rebuilds the vocabulary,
council, calibrator and field modes from 800 packets and scores the other 200
with the challenge's own `scripts/evaluate.py`. Nothing derived from a held-out
packet touches any artifact used to score it.

| seed | Total (floor) | Total (unrecoverable excluded) | Classification /80 |
| ---: | ---: | ---: | ---: |
| 0 | 119.03 | 127.81 | 64.50 |
| 1 | 114.80 | 124.44 | 60.45 |
| 2 | 112.73 | 122.43 | 58.75 |
| 3 | 118.65 | 126.64 | 61.95 |
| **mean** | **116.30** | **125.33** | **61.41** |

Two columns because the public labels omit `unrecoverable_fields`: the floor
charges for every field whose evidence was physically destroyed, the adjusted
column removes them the way `EVALUATION.md` describes. The real figure sits
between.

Other checks:

- `scripts/validate_submission.py` — 5,000/5,000 valid, 0 missing, exit 0
- runtime 0.18 s/PDF against the 6 s budget
- image 0.81 GiB (cap 4 GiB); model artifacts 15.4 MiB (cap 1 GiB)
- catastrophic false approvals: 16 out of 431 truly-denied cases, out-of-fold
- 91 tests, including injection resistance measured on the real corpus

## Compliance

- No LLM, VLM, or cloud OCR anywhere in the runtime. PyMuPDF, Tesseract and
  PP-OCR (ONNX) only.
- No network access at runtime; all models baked into the image.
- No answers keyed to a `case_id`, and no absolute paths. Vocabularies are
  mined value sets and aggregate statistics from `data/train_labels.csv`; a
  test asserts no case id appears in any shipped artifact.
- The three revoked sponsor IDs named in `FIELD_MANUAL.md` appear in the
  build-time miner as published policy; all others are learned.
- Writes only to `/tmp` and `/output`.
