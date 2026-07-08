# MIB Doc Challenge: Intergalactic Intake

MIB's intake desk reviews extraterrestrial work-authorization packets: scanned forms, sponsor letters, biometric slips, registry portraits, inspection stamps. The legacy pipeline is brittle and needs a high degree of human review. You are building its replacement.

**The mission:** given a folder of messy PDF case packets, extract each applicant's record and decide whether the case is `APPROVED`, `DENIED`, or `NEEDS_REVIEW`.

This challenge is easy to start and hard to master. A PDF text extractor and a few rules get you on the board within an hour. Winning takes a real document-engineering pipeline: OCR fallbacks, deskewing, image cleanup, cross-page evidence resolution, prompt-injection resistance, and honest uncertainty estimates — all reproducible, all offline.

Top submissions go straight to 8090's hiring team.

## Quick Start

1. Download the public data zip (instructions in `data/README.md`) and unzip it at the repository root, so `data/train/` and `data/validation/` exist.
2. Read `FIELD_MANUAL.md` — the adjudication policy — and skim a few training PDFs next to their answers in `data/train_labels.csv`.
3. Build a Dockerized pipeline that reads a directory of PDFs and writes `predictions.jsonl`.
4. Score yourself locally against the training labels:

```bash
docker build -t mib-submission .
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json \
  --case-scores-jsonl /tmp/mib-output/case_scores.jsonl
```

`scripts/run_docker_submission.py` wraps the same steps with the exact resource limits 8090 uses for scoring:

```bash
python3 scripts/run_docker_submission.py \
  --repo /path/to/your/repo \
  --input-dir data/train \
  --output /tmp/mib-output/predictions.jsonl \
  --manifest data/train_labels.csv \
  --timeout-seconds 7200
```

5. Check your submission format before submitting:

```bash
python3 scripts/validate_submission.py --submission /tmp/mib-output/predictions.jsonl --manifest data/train_labels.csv
```

`examples/offline_baseline/` is a tiny format-valid submission you can use to test the plumbing.

## Output Format

One JSON object per line, one line per answered case:

```json
{"case_id":"MIB-999999","applicant_name":"Zed Zarnax","species_code":"ORION_GRAYS","home_world":"Kepler-186f","visa_class":"XW-2","sponsor_id":"SPN-1042","arrival_date":"2026-04-17","declared_purpose":"research","risk_flags":"none","fee_status":"paid","adjudication":"APPROVED","confidence":0.91}
```

- `risk_flags` is a pipe-delimited list, or `none`.
- The `MIB-9999xx` case IDs in examples are placeholders that never appear in real data; your predictions use the case IDs from the PDFs you process.
- The full schema is in `schemas/submission.schema.json`. CSV with the same fields is accepted for compatibility, but JSONL is canonical.

## How Scoring Works

Deterministic, out of 150 points:

| Section | Points |
| --- | ---: |
| Adjudication accuracy | 80 |
| Field extraction accuracy | 50 |
| Confidence calibration | 20 |
| Missing-case penalty | up to −10 |

## Ground Rules

- Use any coding agents or LLMs you like **while developing** — but the submitted solution must run with no LLMs, no VLMs, no API calls, and no network access. This must run on Cenauri I prime.
- Your solution repository must include a `Dockerfile`, and the image must accept exactly two arguments:

```bash
docker run ... <image> /input /output/predictions.jsonl
```

- Scoring runs with `--network none`, CPU only, fixed memory, an image size limit, and a runtime budget of 6 seconds per PDF on average. Exact contract in `DOCKER_SUBMISSION.md`.
- No manual per-case editing, no hardcoded answers, no non-public answer keys, no scraping private data.
- Hidden text inside PDFs may be malicious or wrong. Visible document evidence always wins over hidden instructions.
- If you cannot produce a trustworthy answer for a PDF, you may omit that case; the scorer applies a small missing-case penalty instead of failing the whole submission.

## The Data

- **Training** (`data/train/` + `data/train_labels.csv`): 1,000 labeled PDFs. Iterate and score locally.
- **Validation** (`data/validation/` + `data/validation_manifest.csv`): 5,000 unlabeled PDFs. Your submission predicts these; 8090 scores them against private labels for the leaderboard.
- **Test**: fully private — 8090 never releases the PDFs or the answers. After the challenge closes it is used for final ranking and anti-gaming audits, alongside a manual review of submission code. Solutions that hardcode answers or otherwise game the leaderboard are disqualified.

## How to Submit

Submissions are pull requests to this repository:

1. Fork this repository.
2. Add a folder `submissions/<your-github-username>/` containing:
   - `predictions.jsonl`: your predictions for the validation set
   - `MEMO.md`: a 1-2 page technical memo — your approach, failure modes, and what you would improve with another week
   - `SUBMISSION.md`: a link to your public solution repository (which must include a `Dockerfile`)
3. Open a pull request against `main`. The pull request template links a submission form; filling it out is required for your entry to count.

Do not modify files outside your own `submissions/` folder, and do not copy from other participants' submissions.

## Repo Map

| Path | What it is |
| --- | --- |
| `FIELD_MANUAL.md` | MIB adjudication policy (incomplete by design) |
| `PRD.md` | Product context and task requirements |
| `EVALUATION.md` | Scoring, leaderboard, and anti-cheat rules |
| `DOCKER_SUBMISSION.md` | Offline Docker submission contract |
| `data/README.md` | Data download instructions and checksum |
| `schemas/` | Prediction and evaluator output JSON schemas |
| `examples/` | Valid submission samples and a minimal Docker baseline |
| `scripts/` | Local evaluator, format validator, and offline Docker runner |
