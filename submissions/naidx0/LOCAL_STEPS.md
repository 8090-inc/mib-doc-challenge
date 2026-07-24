# Local steps to finish the submission

Everything except these 4 steps is done and pushed. These need a real machine
with Docker + disk (they can't run in a mobile/web session).

## 0. Prereqs
- Docker installed and running
- ~10 GB free disk (2.9 GB zip + unzipped PDFs + image)
- Python 3 with the challenge repo's `scripts/` available
- Clone your fork and check out the branch:
  ```bash
  git clone https://github.com/naidx0/mib-doc-challenge
  cd mib-doc-challenge
  git checkout naidx0/mib-doc-challenge
  ```

## 1-3. One command does the data download, build, predict, and score
```bash
bash submissions/naidx0/solution/reproduce.sh
```
This writes `submissions/naidx0/predictions.jsonl` (the validation predictions)
and prints your training-set score with `scripts/evaluate.py`.

If you'd rather do it by hand, see `submissions/naidx0/SUBMISSION.md`.

## 4. Submit (both are required to count)
1. Commit the generated predictions and push:
   ```bash
   git add submissions/naidx0/predictions.jsonl
   git commit -m "Add validation predictions"
   git push origin naidx0/mib-doc-challenge
   ```
2. Open a Pull Request from your branch to `8090-inc/mib-doc-challenge:main`,
   adding **only** your `submissions/naidx0/` folder.
3. Fill the submission form:
   https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform

## How you rank
8090 scores your `predictions.jsonl` against their **private validation labels**
→ that number is your leaderboard position during the challenge (closes
Aug 3, 2026). After it closes they also re-run your Docker image on a fully
private test set and hand-review the code, so no gaming the public numbers.

## Sanity checks you can run anytime
```bash
# format must be valid (exit 0)
python3 scripts/validate_submission.py \
  --submission submissions/naidx0/predictions.jsonl \
  --manifest data/validation_manifest.csv

# your predicted score on the public training labels (rank proxy)
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/train_predictions.jsonl
```
Verified on a 145-PDF labeled subset: **121.3/150, 0 catastrophic false
approvals**, deterministic, validator exit 0.
