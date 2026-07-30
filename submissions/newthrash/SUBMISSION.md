# Submission

- GitHub username: `newthrash`
- Public solution repository: <https://github.com/newthrash/mib-doc-solution>
- Dockerfile: <https://github.com/newthrash/mib-doc-solution/blob/main/Dockerfile>

The image accepts exactly two arguments and runs offline:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Verified end to end with the organizers' own harness,
`scripts/run_docker_submission.py`, under the published resource limits:
`--network none`, 4 vCPU, 8 GiB, `--read-only` root filesystem,
`--pids-limit 512`, tmpfs `/tmp`.

| Check | Limit | Measured |
| --- | --- | --- |
| Image size | 4 GiB | 0.15 GiB |
| Runtime | 6 s/PDF | 0.95 s/PDF |
| Model artifacts | 1 GiB total | none |
| Structural validity | — | 1000/1000 rows, 0 missing/extra/duplicate/invalid |

Public training score from `scripts/evaluate.py`: **118.44 / 150**
(extraction 41.63, classification 60.93, calibration 15.89), 1 catastrophic
false approval.

The honest estimate for unseen packets is the five-fold out-of-fold total,
**116.82 / 150**, where every held-out case is scored by a calibration table
fitted without it. `MEMO.md` reports both and explains the gap.

No LLM, VLM, network access, model artifacts or API keys at runtime. No
hardcoded case answers, filename dependencies or validation lookup tables. The
hidden answer-key channel present in some packets is quarantined at ingestion
and never used for field values or decisions.
