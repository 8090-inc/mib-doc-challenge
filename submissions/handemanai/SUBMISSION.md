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

Measured inside the container under `--cpus 4 --memory 8g --read-only
--network none --pids-limit 512 --tmpfs /tmp:size=2g`, not extrapolated from
host runs, and re-verified at the submission commit on the image built from a
clean clone of the public repository.

| Limit | Measured | Margin |
| --- | --- | --- |
| Image ≤ 4 GiB uncompressed | 0.27 GiB | 14.8× |
| Model artifacts ≤ 1 GiB total, ≤ 250 MiB each | 12 MB total, 7.9 MB largest | 85× / 32× |
| Memory 8 GiB | 3.3 GiB peak RSS | 2.4× |
| 6 s/PDF average | 3.43 s/PDF | 1.75× |
| 30,000 s for 5,000 PDFs | ~17,100 s projected | 1.75× |
| Predictions ≤ 25 MiB | 1.6 MB | 15× |

The per-PDF figure is whole-batch wall-clock at 4 workers, which saturate the
4-vCPU quota (measured 400% CPU); the projection scales that rate to 5,000
packets. Peak RSS is the maximum over `docker stats` sampling across the run.
The memory ceiling was verified at 7.65 GiB rather than a full 8 GiB, because
that is all the local Docker VM could supply; peak usage sits far enough below
either figure that the difference does not bind.

## Provenance of `predictions.jsonl`

- **5,000 records, 0 missing.** Passes the challenge repository's
  `scripts/validate_submission.py --require-complete` against
  `data/validation_manifest.csv`.
- **sha256:** `6d51c904f006b80de9a7140c27ac8852776fd12b11b49f34a25214101ebe374a`
- Produced by a single uninterrupted 5,000-packet run of `scripts/predict.py`
  over `data/validation` at the code published as commit `fd6bbf6` of the
  solution repository, in 4h04m wall at 4 workers, with **zero per-case
  timeouts and zero retries** (slowest packet 57.0 s), and a full per-case
  evidence ledger retained. The batch-deadline governor stayed at level 0 for
  the entire run — **zero engagements**, so every submitted row is full-quality
  and byte-identical to what an ungoverned run produces.
- Cross-checked against the shipped container: a clean clone of the public
  repository at `fd6bbf6` was built with the published `Dockerfile` and run
  under the scoring flags (`--network none --cpus 4 --memory 8g --pids-limit
  512 --read-only --tmpfs /tmp:size=2g`) over a 300-packet random sample of
  `data/validation`; **all 300 rows are byte-identical to the submitted
  rows**.

## Relation to the 2026-07-31 file, and commits after `fd6bbf6`

Relative to the previous submission file (generated at `53dbe7a`, sha256
`8868cd19…`), exactly four rows changed — the four approvals demoted by the
anti-oracle guard (`MIB-101326`, `MIB-101982`, `MIB-102278`, `MIB-104773`,
each APPROVED → NEEDS_REVIEW with every extracted field unchanged); the
other 4,996 rows are byte-identical. The code delta `53dbe7a..fd6bbf6` is
the anti-oracle guard enablement, the batch-deadline governor (inert on
hardware inside the batch budget: the full-training-set gate at `fd6bbf6`
reproduces the certified 128.916 byte-identically with zero governor
engagements), and documentation. Commits after `fd6bbf6` touch
documentation only, verifiable with
`git diff fd6bbf6..HEAD -- mib scripts models tests tools Dockerfile run.sh`
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
  `enforce_final_consistency`). A small number of approvals (27 of 703: 23
  whose retained fields would re-adjudicate DENIED — revoked sponsor 10,
  TRANSIT-7 visa 6, embargoed world 3, unpaid fee plus a second blocker 2,
  stale arrival date 2 — and 4 whose unknown fee would re-adjudicate
  NEEDS_REVIEW) deliberately retain a field value that superficially
  contradicts approval: each is backed by a legible rank-1 adjudicator-note
  Finding — the field manual's highest-precedence evidence ("visible MIB
  adjudicator stamp or signed manual note", above intake form fields) —
  resolving a contradiction the generator planted in a lower-precedence
  page, and each retention is recorded in the evidence ledger. On the
  labeled training set a readable note Finding matches ground truth in 305
  of 305 cases across all three decision classes, including all 44 cases
  where the note contradicts the field-level policy verdict (the fee shape's
  labeled instance is MIB-000893), and every one of the 27 retained
  approvals was page-audited against the rendered packet before submission.
- The shipped container enables `MIB_ANTI_ORACLE_GUARD` (`run.sh`): a
  tentative APPROVED whose packet carries a hidden answer key itself
  claiming APPROVED, with no adjudicator-note authority behind the
  approval, demotes to NEEDS_REVIEW. The planted key's adjudication is
  wrong in all 216 labeled occurrences, so agreement with it is a trap
  signature; the demotion is distrust-direction only (hidden content is
  never evidence and can never move a decision toward approval) and fires
  on zero of the 1,000 labeled training cases.
- No absolute paths. Dev tooling and data-backed tests resolve the challenge
  checkout through `MIB_CHALLENGE_DIR`.
- 1,100 tests — 1,049 passed, 51 skipped, 0 failed against the `Dockerfile`'s
  pinned dependency set; those that skip without the optional dev-extraction
  fixtures skip deliberately rather than passing vacuously. Run the suite on
  the pinned versions: newer `rapidocr-onnxruntime` releases changed the
  detector-parameter API, so an unpinned interpreter fails roughly a dozen
  OCR-path tests in engine construction, before any assertion runs.
- The image links PyMuPDF, which is AGPL-3.0, so the built image as a
  distributed whole carries AGPL-3.0 terms while our own code remains MIT.
  The corresponding source is the public repository above. See `NOTICE.md`.
