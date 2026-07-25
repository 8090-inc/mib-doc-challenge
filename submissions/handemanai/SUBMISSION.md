# Submission — handemanai

**Solution repository (public, contains a `Dockerfile`):**
<https://github.com/handemanai/mib-doc-challenge-solution>

An offline, CPU-only adjudication engine for the intergalactic intake desk:
PyMuPDF span forensics → trap-masked OCR with a budget-aware escalation ladder →
closed-vocabulary template parsing → a deterministic policy engine → EV-optimal
decisions with a calibrated confidence head. No LLM or VLM anywhere in the
runtime, so the injection surface the dataset targets does not exist in this
system. `MEMO.md` in this directory is the technical write-up; `NOTICE.md` in the
solution repository itemizes third-party licenses and the provenance of every
model artifact.

## Build and run

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Contract compliance, as measured

Measured with the organizers' own `scripts/run_docker_submission.py` under
`--cpus 4 --memory 8g --read-only --network none --pids-limit 512
--tmpfs /tmp:size=2g`, not extrapolated from host runs.

| Limit | Measured | Margin |
| --- | --- | --- |
| Image ≤ 4 GiB uncompressed | 0.27 GiB | 14.8× |
| Model artifacts ≤ 1 GiB total, ≤ 250 MiB each | 12 MB total, 7.9 MB largest | 85× / 32× |
| Memory 8 GiB | 2.88 GiB peak RSS | 2.8× |
| 6 s/PDF average | 3.41 s/PDF | 1.76× |
| 30,000 s for 5,000 PDFs | ~17,000 s projected | 1.76× |
| Predictions ≤ 25 MiB | 1.6 MB | 15× |

The memory ceiling was verified at 7.65 GiB rather than a full 8 GiB, because
that is all the local Docker VM could supply; peak usage sits far enough below
either figure that the difference does not bind.

## Provenance of `predictions.jsonl`

- **5,000 records, 0 missing.** Passes `scripts/validate_submission.py
  --require-complete` against `data/validation_manifest.csv`.
- **sha256:** `8997c9e8f8833ea657d8ca5d9551bfb3cfce1bc39026e3b9cb19411d1ed86e85`
- Produced by a single uninterrupted 5,000-packet run of `scripts/predict.py`
  over `data/validation`, on a clean checkout, in 4h05m wall at 4 workers, with
  **zero per-case timeouts** and a full per-case evidence ledger retained.

Being precise about what that run was: it executed the pipeline as it stands in
the published repository, from a working tree that has since received three
changes, none of which alter output.

1. **Per-case deadline raised** 60 s → 120 s (watchdog 75 s → 150 s, retry 70 s →
   130 s). The deadline is a `signal.alarm` value and nothing else reads it, so
   it cannot affect a packet that finishes before it fires — and none did: the
   slowest of the 5,000 took 57.3 s against the 60 s alarm in force at the time.
2. **228 unreachable templates dropped** from `models/pix_bank.npz`. They sat
   under a field label the decoder never queries.
3. Documentation, tests, and dev tooling, none of which ship in the image.

Rather than assert that (1) and (2) are inert, each was A/B'd: extraction over a
20-packet sample chosen to include the five slowest packets in the corpus
produces a states file with the **same sha256** before and after. Extraction is
additionally identical across platforms — on a separate 105-packet containerized
run, all nine extracted fields and all 105 adjudications match the host run,
despite the staleness epoch being inferred from 105 packets there and 5,000 here.

## Notes for review

- No hardcoded answers or per-PDF lookup tables: no model artifact contains a
  case ID, and no validation-set case ID appears as data anywhere in the
  repository.
- No absolute paths. Dev tooling and data-backed tests resolve the challenge
  checkout through `MIB_CHALLENGE_DIR`.
- 1,078 tests; the 51 that skip without the optional dev-extraction fixtures skip
  deliberately rather than passing vacuously.
- The image links PyMuPDF, which is AGPL-3.0, so the built image as a distributed
  whole carries AGPL-3.0 terms while our own code remains MIT. The corresponding
  source is the public repository above. See `NOTICE.md`.
