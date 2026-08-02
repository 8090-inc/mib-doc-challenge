# Submission — mtata55

## What this is

An offline, rules + classical-CV/OCR pipeline for the MIB Doc Challenge. No LLM/VLM, no cloud OCR,
no network at runtime. The pipeline source and Docker image live in the companion public
repository **https://github.com/mtata55/mib-doc-solution**; this folder holds the deliverables.

## Result

Scored in the exact offline sandbox (`--network none --read-only --cpus 4 --memory 8g`) against
the 1,000 public training labels:

| | score |
|---|---|
| **Total** | **111.58 / 150** |
| classification | 58.59 / 80 |
| extraction | 37.44 / 50 |
| calibration | 15.55 / 20 |
| **catastrophic false approvals** | **0** |

This is the deterministic score of the pinned image (base digest + `tesseract` version pinned), so
a rebuild reproduces it exactly. **FA = 0 is invariant, independent of the OCR build.** This total
is the pessimistic floor (every destroyed field counts); on a forgiveness proxy it is ~120–124.
`predictions.jsonl` here is the pipeline's output on the 5,000-case **validation** set.

## Approach in one paragraph

The scorer makes a false approval catastrophic (−4 plus a disqualifier) while a hedge to
NEEDS_REVIEW still scores +2. So the pipeline denies only on rules that were 100% correct on
training, approves only packets that are complete and clean, and sends everything else to
review — which makes **0 false approvals a built-in property, not a tuned result**. When pages
disagree, the more trustworthy source wins (stamps over forms over OCR). Planted content
(invisible text, barcode instructions, fake answer keys) is filtered by how it is presented,
never by reading what it says. The full design, the measured failures, and the runtime table are
in [`MEMO.md`](MEMO.md).

## Reproducing

```bash
# in mtata55/mib-doc-solution
docker build -t mib-submission .
docker run --rm --network none --read-only --cpus 4 --memory 8g \
  --pids-limit 512 --tmpfs /tmp:size=2g \
  --mount type=bind,src=<validation_pdfs>,dst=/input,readonly \
  --mount type=bind,src=<out>,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

`python -m unittest discover -s tests` runs the offline test suite.

## Files

- `predictions.jsonl` — pipeline output on the 5,000-case validation set
- `MEMO.md` — approach, measured results and negative results, runtime
- `SUBMISSION.md` — this file
