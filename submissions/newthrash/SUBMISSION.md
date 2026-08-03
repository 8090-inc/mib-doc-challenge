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
| Image size | 4 GiB | 0.21 GiB |
| Runtime | 6 s/PDF | ~4 s/PDF in-container incl. image build and engine warm-up |
| Model artifacts | 1 GiB total | PP-OCR ONNX models, ~15 MiB, bundled in the wheel |
| Structural validity | — | 1000/1000 train and 5000/5000 validation rows, 0 missing/extra/duplicate/invalid |

Public training score from `scripts/evaluate.py`: **122.30 / 150**
(extraction 43.27, classification 63.12, calibration 15.91), **0 catastrophic
false approvals**.

The honest estimate for unseen packets is the five-fold out-of-fold total,
**120.56 / 150**, where every held-out case is scored by a calibration table
fitted without it. `MEMO.md` reports both and explains the gap, which is 1.74
points.

No LLM, VLM, network access, model artifacts or API keys at runtime. No
hardcoded case answers, filename dependencies or validation lookup tables. The
hidden answer-key channel present in some packets is quarantined at ingestion
and never used for field values or decisions.
