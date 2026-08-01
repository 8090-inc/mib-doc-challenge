# Submission — AmosRM

**Solution repository (public, contains the `Dockerfile`):**
<https://github.com/AmosRM/mib-doc-solution>

The repository is published as a single commit whose tree is the exact source of
the scored image
(`sha256:c561c701e1afa433a88fd79ff04a95294e82dbbb1a90d006ebf87be9748ecfe2`,
115,731,362 bytes). Docker image IDs are not bit-reproducible, so this was
verified by behaviour: the published repository was cloned fresh, built, and run
offline over all 1,000 training packets, and its predictions are byte-identical
to the scored image's, reproducing 117.36173866666667 / 150 and 0 catastrophic
false approvals.

## Artifact

- `predictions.jsonl` — 5,000 validation-set records, one per manifest case.
- SHA-256 `b333b63c56f64eace1708f42b787954ef9a2df6135829e1ad1fdce38679dfd75`
- Passes `scripts/validate_submission.py --require-complete` against
  `data/validation_manifest.csv`: 5,000 valid records, 0 missing.

## Runtime

Offline (`--network none`), CPU-only, read-only root filesystem with a writable
`/tmp`, 4 vCPU and 8 GiB. Entry point takes `<input_pdf_dir>
<output_predictions_path>`.

- Image size 115,731,362 bytes against the 4 GiB cap.
- No model artefacts are vendored, so the 250 MiB per-artefact and 1 GiB total
  limits do not apply.
- No LLM, VLM, cloud OCR, network call, label file, case-ID lookup, or hidden
  answer text participates in the runtime.
- Official 1,000-case contract run: 1,202.26 s total, **1.202 s/PDF** against
  the 6 s/PDF budget.

## Result on public training labels

| Component | Score |
| --- | ---: |
| Field extraction | 40.496667 / 50 |
| Classification | 60.940000 / 80 |
| Calibration | 15.925072 / 20 |
| **Total** | **117.361739 / 150** |
| **Catastrophic false approvals** | **0** |
| True `NEEDS_REVIEW` recall | 280 / 280 |

This is an in-sample number on public labels, not an estimate of private-test
performance.

## Notes

- Approach, failure modes, and what another week would buy are in `MEMO.md`.
- Ported code, borrowed ideas, and third-party licences are recorded in
  `ATTRIBUTION.md` in the solution repository. Two field repairs derive from
  `strobl/mib-doc-solution` (MIT); the emission-only imputation idea derives
  from the published documents of challenge PR #51 (`arthurmichel00`, MIT).
- Our own code is MIT. PyMuPDF is AGPL-3.0 and governs the combined work, which
  is why the full source is published.
