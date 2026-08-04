# Submission — dhyantsoni

**Solution repository:** <https://github.com/dhyantsoni/mib-doc-challenge/tree/main>

The `Dockerfile` is at the repository root, so the scoring contract runs unchanged:

```bash
docker build -t mib-submission https://github.com/dhyantsoni/mib-doc-challenge.git
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## What is in the repository

| Path | What it is |
| --- | --- |
| `Dockerfile`, `run.sh`, `requirements.txt` | offline image; entrypoint takes `<input_dir> <output_path>` |
| `mib/page.py` | ink-verification gate separating visible evidence from hidden text |
| `mib/ocr.py` | Tesseract recovery of the scanned pages |
| `mib/extract.py` | template- and label-anchored reading, closed-vocabulary snapping |
| `mib/case.py` | evidence ledger, precedence resolution, case-id scoping |
| `mib/policy.py` | manual rules as constraints, learned residual, expected-utility decision |
| `mib/model.joblib` | the trained residual model and its calibrator (< 1 MiB) |
| `tools/train.py` | regenerates `model.joblib` from `data/train/` |
| `tools/score.py` | local scoring harness against `data/train_labels.csv` |

Everything runs offline on CPU. No LLM, VLM, or hosted API is used at any point —
the only models in the image are Tesseract's bundled English data and the
gradient-boosted classifier trained here on the public training split.

## Reproducing the model artifact

`mib/model.joblib` is checked in so the image builds without the dataset. To
rebuild it from scratch, with `data/train/` unpacked:

```bash
python3 tools/train.py --rebuild --workers 4
```

The technical memo is in `MEMO.md` beside this file.
