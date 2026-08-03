# Submission — Dinuda

**Solution repo:** <https://github.com/Dinuda/mib-solution>

## In short

I built an offline Docker pipeline that reads a folder of messy MIB PDFs and
writes `predictions.jsonl`. No LLM at runtime, no network, no per-case answers.

**Public train (1,000 cases, official scorer): 129.16 / 150**, CFA **0**.
Retrospective held-out 100 (artifacts refit on the other 900): **131.16**, also
CFA 0. Validation file: **5,000 / 5,000** rows from this image under the official
resource limits — **4.48 s/PDF** (budget 6.0), ~1.9 GiB image.

## How I got to the design

I spent a chunk of early time watching how a strong vision model adjudicates
these packets when you force it to be honest: one case, page images only, no
hidden PDF text, no other cases on the canvas. Isolated runs landed around
**132 / 150**. A sloppy contact-sheet run hit ~138 and taught me that number was
contaminated.

What the model did well became the product requirements: trust visible stamps
and notes first, don’t invent fees or risk from priors, abstain when the
controlling page is missing, and treat damage as a local ROI problem. The
submitted system is me trying to hard-code that discipline into classical OCR +
rules + two tiny train-only models — not “call GPT at score time.”

On packets where evidence can still exist, the same offline stack scores about
**132**. On the ~329 cases where risk or fee is absent by template, it’s ~110,
and guessing there is how you get catastrophic false approvals. I stopped
chasing a prettier full-train number that would require inventing those pages.

Longer write-up, score climb, and failure modes: `MEMO.md`.

## Pipeline (very short)

1. Visibility firewall — hidden / injected PDF text doesn’t count  
2. Bounded Tesseract OCR (no always-on challenger; that path lost hard in A/B)  
3. Field resolution in manual → intake → biometric → sponsor → registry order  
4. Conservative policy; missing controlling evidence → `NEEDS_REVIEW`  
5. Deny-only manual gate + confidence calibrator (train labels only)

Image contents: `vocab.json`, `manual_finding_gate.joblib`,
`path_calibration_bundle.joblib`.

Training labels (`train_labels.csv`) are used only at build time: closed
vocabularies, name grammar, field modes (fill empty slots only — never as
approve/deny proof), and small recurrence lists for revoked sponsors /
embargoed worlds. Two tiny logistics are fit on train traces afterward (a
deny-only unreadable-Finding gate, and a confidence calibrator). Validation is
never labeled and never fit.

## How to run

```bash
docker build -t mib-solution /path/to/mib-solution
mkdir -p /tmp/mib-output
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-solution /input /output/predictions.jsonl
```

Two arguments only: input PDF dir, output predictions path. Matches
`DOCKER_SUBMISSION.md`.

## Scores

| | Full train (1000) | Held-out 100 |
| --- | ---: | ---: |
| Total | **129.16** | **131.16** |
| Extraction | 44.71 | — |
| Classification | 67.33 | — |
| Calibration | 17.12 | — |
| CFA | **0** | **0** |

`predictions.jsonl` in this folder is the 5,000-row validation run from the
frozen image, checked against `validation_manifest.csv`.
