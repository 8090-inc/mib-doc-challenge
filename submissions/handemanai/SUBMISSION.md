# Submission — handemanai

- **Solution repository:** https://github.com/handemanai/mib-solution
  (Dockerfile at repo root; currently private — it will be made public with the
  final update to this pull request before the submission deadline.)
- **Predictions:** `predictions.jsonl` in this directory (validation set,
  5,000 records; validated with `scripts/validate_submission.py`).
- **Memo:** `MEMO.md` in this directory (preliminary; final version lands with
  the final predictions).

The Docker image accepts exactly two arguments:

```bash
docker run --rm --network none <image> /input /output/predictions.jsonl
```

Runs offline (no network, CPU-only) within the published resource contract.
