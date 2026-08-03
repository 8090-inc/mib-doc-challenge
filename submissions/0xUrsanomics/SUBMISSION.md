# Submission

**Solution repository:** https://github.com/0xUrsanomics/mib-doc-challenge-solution

Public, MIT, contains the `Dockerfile` and the full pipeline. Build and run instructions are in its
`README.md`; the technical write-up is `MEMO.md` in this folder and mirrored in that repo.

**Score on the labelled train split: 101.42 / 150** (fields 40.37/50, classification 48.94/80,
calibration 12.11/20, missing-case penalty 0/10), via the challenge's own `scripts/evaluate.py`.

`predictions.jsonl` here is the validation-set output, 5,000 of 5,000 cases, produced by that image
under `--cpus 4 --memory 8g --network none --read-only`.
