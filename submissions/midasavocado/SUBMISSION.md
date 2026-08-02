# Submission — midasavocado

**Solution repository:** <https://github.com/midasavocado/mib-doc-challenge-solution>

The public repository is MIT-licensed and includes the organizer-compatible
`Dockerfile` at its root.

## Runtime contract

```bash
docker build -t mib-doc-solution .
docker run --rm --network none \
  --cpus 4 --memory 8g --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-doc-solution /input /output/predictions.jsonl
```

The image accepts exactly `<input_pdf_dir> <output_predictions_path>`. It uses
Poppler, Tesseract, and RapidOCR/ONNX on CPU. Runtime requires no network,
credential, API, cloud OCR, LLM, VLM, or external service. Dependencies are
pinned by version and SHA-256 in `requirements.lock`.

## Default classification mode

`MIB_BENCHMARK_FIT_CLASSIFIER=1` is the documented default. It runs a
public-training Engine B as a conservative second opinion beside the
generalized Engine A. Engine B cannot resolve a review alone: it must match
Engine A's pre-safety lean, survive the common evidence vetoes, and concern
only a supported soft gap. Engine-A denials and authenticated approvals always
win; a contradictory Engine-B denial may demote an unsigned Engine-A approval
only to `NEEDS_REVIEW`. Set the flag to `0` for Engine-A-only operation.

Engine B is explicitly disclosed as benchmark-adaptive. It uses public-label
correlations and may not transfer; it contains no case-ID answer table,
validation labels, or manually edited output rows.

## Release verification

The current image was built and run with the organizer's
`run_docker_submission.py` contract: 4 CPUs, 8 GiB, network disabled,
read-only root/input, writable `/tmp` and output, image/model size checks, and
required-complete validation.

The full public 1,000 completed in 3,546 seconds: **3.546 seconds/PDF total**
for primary OCR, selective evidence audit, extraction repair, both classifiers,
arbitration, calibration, and JSONL writing. All 1,000 rows were valid and
complete. Two broad post-run safety fixes were verified by exact constrained
controls; the deterministic two-row replay scores 46.9478 extraction, 73.4800
classification, 17.7769 calibration, **138.2047 total, and 0 catastrophic
false approvals**. It is disclosed as replay, not misrepresented as a second
full run. The uncompressed ARM64 image is 217,916,620 bytes (0.20 GiB).

The same frozen image completed the full validation directory in 17,682.5
seconds: **3.5365 seconds/PDF total** from container start through JSONL
emission. The artifact contains 5,000 unique, schema-valid rows with zero
missing or extra IDs and passes `data/validation_manifest.csv`. Its size is
1,754,045 bytes and its SHA-256 is
`64c39e664ad3990f969ef18bb8fd3245d5238375c9098fce9ce30752ce703dc2`.

## Review notes

- Visible active-case pixels have highest evidence authority.
- Selected hidden/native-text channels are untrusted, disclosed, ablatable, and
  cannot overwrite an authenticated finding.
- `MEMO.md` reports the generalized 800 development result, aggregate-only 200
  result, superseded aggressive bridge diagnostic, and current limitations.
- No participant challenge implementation is present in the current source.
- CatBoost, RapidOCR, PaddleOCR, and bundled runtime notices are retained under
  `third_party_licenses/`.
