# Evaluation

## Submission Files

Candidates submit:

- `predictions.jsonl`
- GitHub repository link
- Dockerfile-based reproducible solution
- technical memo, 1-2 pages

The repository must build a Docker image whose entrypoint accepts:

```bash
<input_pdf_dir> <output_predictions_path>
```

8090 runs the image with no network access. See `DOCKER_SUBMISSION.md`.

Submissions are run with `scripts/run_docker_submission.py`, checked with `scripts/validate_submission.py`, and scored with `scripts/evaluate.py`.

The deterministic evaluation flow is:

1. Run the submitted Docker image to produce `predictions.jsonl`.
2. Validate JSONL structure, case IDs, enums, and confidence values.
3. Score predictions with `scripts/evaluate.py`.
4. Save `evaluation.json` for aggregate scores and `case_scores.jsonl` for per-case scoring details.

CSV submissions with the same fields are still accepted for convenience, but JSONL is the canonical format for the public challenge.

CSV compatibility requires the exact header order used in `examples/submission.csv`. JSONL avoids that ordering requirement.

## Dataset Splits

- Training set: public PDFs from the data zip under `data/train/`, with public answers in `data/train_labels.csv`.
- Validation set: public PDFs from the data zip under `data/validation/`, with no public answers. 8090 uses private validation labels for leaderboard scoring during the challenge.
- Test set: private PDFs and answers held only in 8090's internal repository. 8090 uses this split after the deadline for final ranking and audit checks.

## Scoring Summary

Final score is out of 150, inspired by the University of Waterloo CEMC Pascal contest's tiered, out-of-150 scoring style ([contest format](https://cemc.uwaterloo.ca/contests/pcf), [example scoring rules](https://cemc.uwaterloo.ca/sites/default/files/documents/2026/2017PascalContest.html)). The weights are adapted for document engineering:

- 80 points: adjudication/classification accuracy
- 50 points: field extraction accuracy
- 20 points: confidence calibration quality
- up to -10 points: missing-case penalty

Classification is deliberately worth more than extraction. A system that transcribes fields but makes bad immigration decisions should not beat a system that recovers fewer fields but reliably chooses `APPROVED`, `DENIED`, or `NEEDS_REVIEW` from trusted evidence.

## Runtime Environment

Validation and private test scoring run in Docker:

- no network: `--network none`
- CPU only, no GPU
- 4 vCPU
- 8 GiB RAM
- read-only input mount
- writable output mount
- writable `/tmp` tmpfs
- read-only container root filesystem
- 4 GiB maximum uncompressed Docker image size
- 250 MiB maximum individual model artifact size
- 1 GiB maximum total model artifact size

The submitted image must not require API keys, external services, package downloads, or internet access at runtime.

LLMs, VLMs, multimodal foundation models, and cloud OCR/document APIs are not allowed in the submitted runtime. Offline OCR engines, classical computer vision, hand-written rules, small task-specific models, and candidate-trained models are allowed if they fit the size limits and run offline.

## Prediction Format

Each JSONL line is one prediction object:

```json
{"case_id":"MIB-000001","applicant_name":"Zed Zarnax","species_code":"ORION_GRAYS","home_world":"Kepler-186f","visa_class":"XW-2","sponsor_id":"SPN-1042","arrival_date":"2026-04-17","declared_purpose":"research","risk_flags":"none","fee_status":"paid","adjudication":"APPROVED","confidence":0.91}
```

`risk_flags` is a pipe-delimited list, or `none`.

If your system cannot produce a trustworthy answer for a PDF, omit that case from `predictions.jsonl`. The evaluator applies the missing-case penalty below; it does not reject the whole submission.

## Missing Cases

Missing cases are valid but score negatively.

The scorer subtracts:

```text
10 * missing_cases / total_cases
```

This is intentionally small. Skipping a few impossible PDFs should not destroy a strong solution, but silently omitting hard documents should lose enough points to create separation.

## Field Extraction

Field extraction contributes 50 points after normalization.

Each field has a raw weight:

| Field | Raw points |
| --- | ---: |
| `case_id` | required for scoring |
| `applicant_name` | 5 |
| `species_code` | 6 |
| `home_world` | 5 |
| `visa_class` | 5 |
| `sponsor_id` | 5 |
| `arrival_date` | 4 |
| `declared_purpose` | 3 |
| `risk_flags` | 8 |
| `fee_status` | 4 |

The raw extraction score is normalized to 50 points across all scored cases.

Some private/admin labels mark fields as genuinely unrecoverable because visible evidence was cut out, washed out, torn away, or only present in untrusted hidden text. Those fields are removed from that case's extraction maximum. Candidates still receive credit for every other correctly recovered field and for the adjudication decision. This makes hard PDFs a gradient instead of a perfect-or-fail OCR task.

The public `data/train_labels.csv` intentionally omits admin-only metadata such as `unrecoverable_fields`, `difficulty`, `damage_profile`, and `traps`. 8090's private validation and test labels include those columns for scoring and analysis.

## Classification

Classification contributes 80 points after normalization.

Each case has 8 raw classification points available:

| Prediction result | Raw points |
| --- | ---: |
| Correct `APPROVED`, `DENIED`, or `NEEDS_REVIEW` | 8 |
| Wrongly sending an `APPROVED` or `DENIED` case to `NEEDS_REVIEW` | 2 |
| Missing a true `NEEDS_REVIEW` decision | 1 |
| Wrong `APPROVED` vs `DENIED` decision | 0 |
| Invalid or blank adjudication on a submitted record | 0 |
| False approval of a denied case | -4 |

The false-approval penalty is intentionally severe because it is the riskiest operational failure.

## Confidence Calibration

Calibration contributes 20 deterministic points.

For each submitted prediction, the evaluator compares `confidence` to whether the adjudication was correct:

- correct adjudication target: `1.0`
- incorrect adjudication target: `0.0`

The evaluator computes mean Brier error and scores:

```text
20 * max(0, 1 - 2 * mean_brier)
```

This rewards systems that know when they are likely right, and it discourages overconfident hallucinated answers on damaged or adversarial packets.

## Evaluator Artifacts

Run:

```bash
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json \
  --case-scores-jsonl /tmp/mib-output/case_scores.jsonl
```

`evaluation.json` contains aggregate counts, section scores, the total score, confusion counts, duplicate/extra/missing examples, and catastrophic false-approval counts.

`case_scores.jsonl` contains per-case deterministic scoring details, including field match status, classification reason, confidence error, and missing-case penalty contribution.

`evaluate.py` exits with code `0` for a structurally valid submission. It exits with code `2` after writing diagnostics if submitted records contain duplicate IDs, unexpected case IDs, invalid adjudications, invalid confidence values, or invalid `fee_status` values. Missing expected cases do not trigger a failing exit code because they are scored through the missing-case penalty.

## Prompt-Injection Robustness

Some PDFs contain:

- white text on a white background
- text outside the visible page crop
- hidden PDF text layer content
- fake system prompts
- QR codes or barcodes containing incorrect instructions
- decoy fields labeled as "answer key"

The correct answer is based on visible document evidence and the MIB field manual. A candidate is penalized when outputs follow adversarial hidden instructions.

If a hidden text layer or fake barcode supplies a value for a field that is missing from visible evidence, that value should be treated as untrusted. Strong systems should distinguish "unknown from trusted evidence" from "filled in by prompt injection."

## Private Test Set

After the deadline, 8090 runs submitted repositories on unreleased PDFs from a private/internal test set.

The private test set checks:

- no hardcoded validation-set answers
- no reliance on absolute file names
- no manual per-case edits
- stable execution from a clean checkout
- generalization to new layout variants
- compliance with the offline Docker runtime contract

## Tie Breakers

Ties are broken by:

1. private test-set classification score
2. catastrophic false-approval count
3. extraction score on high-difficulty packets
4. technical memo quality
5. runtime and reproducibility

## Minimum Bar For Interview Consideration

A candidate should usually clear all of:

- 105+ total score
- 55+ classification score
- 90%+ valid predicted rows
- no catastrophic false-approval pattern
- runnable repo
- memo demonstrates they understand their own system

8090 can still advance a lower-scoring candidate if the repo shows unusually strong engineering judgment.
