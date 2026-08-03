# Submission — midasavocado

**Public solution:** <https://github.com/midasavocado/mib-doc-challenge-solution>

The root contains an MIT `LICENSE`, executable `run.sh`, and organizer-compatible
`Dockerfile`. The image accepts exactly `<input_pdf_dir>
<output_predictions_path>` and runs CPU-only with no network, API key, cloud
OCR, LLM, VLM, or external service.

## Default mode

The default runs generalized Engine A with a bounded, public-training Engine B
second opinion. Engine B cannot override an Engine-A denial or authenticated
approval. It may resolve an Engine-A review only after deterministic safety
vetoes. Its only reverse authority is fail-closed: B abstention or a late
refreshed B denial may demote a qualifying unsigned approval to
`NEEDS_REVIEW`, never to denial. Set `MIB_BENCHMARK_FIT_CLASSIFIER=0` for
Engine-A-only operation.

Engine B is disclosed as benchmark-adaptive. It uses public-label correlations
and may not transfer; it contains no case-ID answer table, validation labels,
or manually edited output rows. Selected native-PDF channels are also
untrusted, disclosed, and separately ablatable. Visible or signed evidence
retains deterministic veto authority.

## Release verification

The exact constrained public 1,000 run completed in 3,624.11 seconds
(3.62411 seconds/PDF) with 1,000 valid complete rows. The evaluator measured:

- extraction: 46.9478/50
- classification: 76.9800/80
- calibration: 18.3819/20
- **total: 142.3097/150**
- catastrophic false approvals: **0**

The identical 217,919,202-byte ARM64 image completed all 5,000 validation PDFs
under the organizer's offline 4-vCPU/8-GiB, read-only-root contract in
19,717.37 seconds (**3.943474 seconds/PDF total**). The copied artifact has
5,000 unique complete rows, zero missing/extra IDs, and passes
`data/validation_manifest.csv` plus an independent exact-schema audit.

- predictions size: 1,749,573 bytes
- predictions SHA-256:
  `85ca045b1a5a652d6cc9d041966bee05cba17fc75675ef3be10ecccbb517b536`
- image ID:
  `sha256:fc5c5eb8057d850b91e033ff3b49b28016afbd14cc4879b1264ba340c635bded`

No validation labels or private score were available or inferred. The roadmap,
failure modes, generalization boundary, and next-week plan are in `MEMO.md`.
Third-party notices are retained in the solution repository under
`third_party_licenses/`.
