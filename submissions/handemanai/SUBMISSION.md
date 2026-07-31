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
docker run --rm --network none --cpus 4 --memory 8g --read-only --tmpfs /tmp \
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

- **5,000 records, 0 missing.** Passes the challenge repository's
  `scripts/validate_submission.py --require-complete` against
  `data/validation_manifest.csv`.
- **sha256:** `8868cd194305d57b85bd7f291dead571bb4c26fa6537397052e2128220e86755`
- Produced by a single uninterrupted 5,000-packet run of `scripts/predict.py`
  over `data/validation` at the code published as commit `53dbe7a` of the
  solution repository, in 4h06m wall at 4 workers, with **zero per-case
  timeouts and zero retries** (slowest packet 57.4 s), and a full per-case
  evidence ledger retained.
- Cross-checked against the shipped container: a clean clone of the public
  repository at `53dbe7a` was built with the published `Dockerfile` and run
  under the scoring flags (`--network none --cpus 4 --memory 8g --read-only
  --tmpfs /tmp`) on sample validation packets; the container rows match the
  submitted rows byte-for-byte.

## Documentation-only commits after `53dbe7a`

The submitted `predictions.jsonl` was generated at commit `53dbe7a` of the
solution repository. Every commit after `53dbe7a` touches documentation and
experiment receipts only — nothing under `mib/`, `scripts/`, `models/`,
`tests/`, `tools/`, `Dockerfile`, or `run.sh` changes, verifiable with
`git diff 53dbe7a..HEAD -- mib scripts models tests tools Dockerfile run.sh`
(empty output), so a rebuild at any later commit reproduces the same rows.

## Notes for review

- No hardcoded answers or per-PDF lookup tables: no model artifact contains a
  case ID, and no validation-set case ID is used as data by the runtime or any
  artifact. (A grep for `MIB-1` in the solution repository finds exactly two
  incidental mentions, neither reachable from the prediction path: the
  synthetic negative-test fixture string `Packet MIB-100809 / page 2` in
  `tests/test_fee_amount_indicator.py`, which asserts that ID fragments can
  never match the fee-amount pattern, and the injection-census example
  MIB-102051 discussed in `docs/REVIEWER_GUIDE.md`.)
- Every APPROVED row is re-adjudicated against the exact field values it
  emits before it is written (`mib/two_ledger.py`,
  `enforce_final_consistency`). A small number of approvals (21 of 707)
  deliberately retain a field value that superficially contradicts approval:
  each is backed by a legible rank-1 adjudicator-note Finding — the field
  manual's highest-precedence evidence — resolving a contradiction the
  generator planted in a lower-precedence page, and each retention is
  recorded in the evidence ledger. On the labeled training set this shape is
  note-right, field-wrong (e.g. MIB-000893).
- No absolute paths. Dev tooling and data-backed tests resolve the challenge
  checkout through `MIB_CHALLENGE_DIR`.
- 1,085 tests; those that skip without the optional dev-extraction fixtures
  skip deliberately rather than passing vacuously.
- The image links PyMuPDF, which is AGPL-3.0, so the built image as a
  distributed whole carries AGPL-3.0 terms while our own code remains MIT.
  The corresponding source is the public repository above. See `NOTICE.md`.
