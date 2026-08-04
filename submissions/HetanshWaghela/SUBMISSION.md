# Submission - Hetansh Waghela

- **Solution repository (public, includes `Dockerfile`):**
  https://github.com/HetanshWaghela/mib-ledger
- **Predictions:** `predictions.jsonl` in this folder - all 5,000 validation cases,
  produced by the Docker image via `scripts/run_docker_submission.py` with the exact
  scoring flags (`--network none --cpus 4 --memory 8g --read-only`).
- **Memo:** `MEMO.md` in this folder. The solution repository carries the full
  engineering memo (incident history, mined-rule tables, negative-results appendix).

## Reproduce

```bash
git clone https://github.com/HetanshWaghela/mib-ledger
cd mib-ledger
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Deterministic across runs (thread pinning, `PYTHONHASHSEED=0`, integer date math,
case-id-sorted output); every per-PDF failure degrades to a valid NEEDS_REVIEW row.

## Headline numbers

| Measurement | Score |
|---|---|
| Fold-clean out-of-fold (5 folds, per-fold-mined artifacts) | **120.00 / 150, CFA 0** |
| Template-grouped OOF (layout-transfer proxy) | 119.45 / 150, CFA 0 |
| In-sample (full-train artifacts) | 120.47 / 150, CFA 0 |
| Runtime | 2.4-3.1 s/PDF against the 6 s budget |

Methodology and why we report fold-clean rather than in-sample: see `MEMO.md`.
