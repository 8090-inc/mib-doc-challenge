# Submission — mikeg-cerebras

Private solution repository:
<https://github.com/mikeg-cerebras/mib-doc-challenge>

## Exact Production

```text
branch: main
runtime-bearing private-main commit: 2f1d3af600c78556baad5fee5f0b8c2eb2669302
runtime source commit: 5c70e9edb1cfd736f87f9bdab4ecf6acc45cb738
runtime source tree: ebe6ffb25e73373f3d3e6e3c339fff1a6e19cf9e
official image: sha256:c8d238794c6ab7c1e3963fe7f588bf17df5428d39956d9352852322ffce16f0d
image size: 589402203 bytes
policy model SHA-256: 6d1c15254429409ffa9812ffc957764628b3dfebfa2a1ceccb1df61b271c7460
real validation JSONL SHA-256: 233cfea5a21462653e25b1744b4afdc194b8ec8efa0b3ccedbcb207e0ff79c70
real validation terminal receipt SHA-256: e0f8676d875db040abeec5b1a884ac9e117e40e42b097c616bc9d1310596c7fc
```

The frozen label-free verifier reports real-validation **PASS**: 5,000/5,000
strict rows and unique expected IDs, zero missing/extras, official validator
exit 0, and wrapper/container exit 0 without timeout, crash, or OOM-kill. The
artifact is 1,637,452 bytes. Full-lifecycle resource telemetry continuity is
not claimed because operator-requested sampling stopped about 2 hours 44
minutes before terminal; the observed segment was within limits with zero
swap/OOM.

## Score Evidence

- Primary grouped nested 5x4: `133.62002305740833/CFA1`, with all five outer
  folds positive versus owner `133.32418873300010/CFA1`.
- Descriptive all-1,000 fit: `133.88708608605802/CFA1`; full-public fit, not
  holdout evidence.
- Exact-image replay B: `133.88713553473560/CFA1`, 1,000/1,000 rows, zero
  extraction/adjudication changes, and 19 confidence-only differences. The
  internal exact-output parity subgate remains `STOP_SHIP`; byte-deterministic
  confidence is not claimed. Performance is `+0.56294680173550` over legacy.
- Reused 850/150 sensitivity: `130.07338821722735/CFA0`; disclosed reused
  evidence, not untouched holdout.

## Evidence Boundary

Rendered OCR remains the owner. Native/selectable text, PDF layout/object
structure, key-like visible text, and secondary OCR are limited to proposal,
localization, corroboration, conflict, and veto. They are never accepted
verbatim as truth. The runtime contains no answer-key harvesting/parser or
transcriber and no case/hash/path/output lookup or competitor-prediction route.

The frozen source, image, and real-run start all predate the August 3
Pacific-time deadline. The artifact publication retains its actual
post-midnight timestamp and changes no runtime code.

## Build and Run

```bash
docker build -t mib-submission /path/to/private/repo
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src=<pdf_dir>,dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

The organizer's exact four-CPU/7-GiB wrapper command is documented in the
private repository. Reviewer access to source, complete `FEATURE.md`,
`ARCHITECTURES.csv`, independent audits, and immutable receipts is available
under the organizer-confirmed private-repository arrangement.

The public PR contains only `MEMO.md`, `SUBMISSION.md`, and the immutable
`predictions.jsonl` at SHA-256
`233cfea5a21462653e25b1744b4afdc194b8ec8efa0b3ccedbcb207e0ff79c70`.
