# Submission

**Solution repository:** <https://github.com/henrybrewer00-dotcom/mib-doc-solution>

That repository contains this file, the `Dockerfile`, `solution.py`, and
`mibdoc/`. It must be public before this entry is valid; the rules require a
public solution repository.

The image builds from the repository root and accepts exactly two arguments:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/output,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

## Compliance with the runtime contract

| Requirement | This submission |
| --- | --- |
| Runs with `--network none` | Yes -- no network calls anywhere at runtime |
| No API keys or external services | Yes |
| No LLM / VLM / cloud OCR | Yes -- Tesseract, RapidOCR (PP-OCRv4 via ONNX Runtime), OpenCV, scikit-learn. Both OCR engines run locally from shipped weights |
| Image size ≤ 4 GiB | **0.35 GiB** (`docker image inspect`, confirmed by `docker save \| wc -c`) |
| Individual model artifact ≤ 250 MiB | **27.91 MiB** (`model/adjudicator.pkl`); largest shipped OCR weight is 10.36 MiB |
| Total model artifacts ≤ 1 GiB | **43.6 MiB** -- the adjudicator, 15.4 MiB of PP-OCRv4 ONNX weights inside the `rapidocr-onnxruntime` wheel, and 0.28 MiB of template banks |
| ≤ 6 s per PDF average on 4 vCPU | **1.54 s/PDF** in-container at `--cpus 4 --memory 8g --read-only` (5,000 packets in 7,686 s). Independently, 12.03 s of CPU per packet measured over 200 packets at 99% parallel efficiency, i.e. **~3.0 s/PDF at 4 vCPU** on slower cloud hardware. Both are inside the budget; see below |
| Read-only root filesystem | Yes -- temporary files go to `/tmp` only |
| Writes to the requested output path | Yes -- JSONL, or CSV if the path ends `.csv` |
| Deterministic | Yes -- repeat runs are byte-identical, and runs at 1, 2 and 4 vCPU all produce identical output |

### On the runtime figure

The margin is hardware-dependent, so it is stated as CPU cost rather than as a
single wall-clock number. Measured over 200 packets: **12.03 s of CPU per
packet**, at 99% parallel efficiency (200 x 12.03 / 2 workers = 1,203 s
predicted against 1,213 s measured). At the 4 vCPU the contract names that is
**~3.0 s/PDF**, half the budget. On fast local hardware in-container it is
1.54 s/PDF.

A 95-minute run over 1,000 packets initially read as 5.71 s/PDF and looked
alarming; that runner turned out to have 2 vCPU, not 4. The figure was right
and the denominator was wrong.

Where the time goes: primary OCR 41.7%, second engine 33.5%, parse/render/
resolve 24.8%. The cost is the mean, not the tail -- the slowest 1% of packets
hold only 4.3% of total time, which is why a per-page cap cannot buy runtime on
a real corpus (at a cap of 12, 8 or 6 OCR pages the projection moves 0 of 40
packets). The caps that exist are sized so a crafted packet cannot outspend a
genuine one -- 8 x 3.60 + 8 x 2.03 + 24 x 0.44 = 56 s against 58.7 s for the
slowest real packet measured -- and they are deterministic index caps, never
wall-clock gates, which would make output load-dependent (a bug this project
has already paid for once, MEMO section 9b).

## Anti-gaming statement

- No hardcoded answers and no lookup tables keyed to case ids.
- **`case_id` is taken from the filename when the filename is id-shaped**, and
  from the page header otherwise. This is stated plainly because it reverses
  what an earlier version of this file claimed, and because "uses the filename"
  deserves scrutiny: a filename cannot be OCR-damaged, whereas a printed header
  can, and a wrong `case_id` makes a packet unmatchable and costs it entirely.
  On 200 sampled training packets the header was readable on 172, agreed with
  the filename on 172 of 172, and was absent on the other 28 -- so the header
  adds no information here while carrying the risk of turning `MIB-000805` into
  `MIB-OOO805`. The `case_id` is a join key, never an answer: no field value or
  adjudication is derived from it, nothing is keyed to it, and the header path
  remains for a private set whose filenames are hashes or sequence numbers.
- The model is trained solely on the public training labels. Features are
  semantic document properties; no case identifier or file-ordering information
  is used.
- Two values are inferred from the public training labels, which the field
  manual explicitly invites ("Other revoked sponsors may appear in examples"):
  the additional revoked sponsors `SPN-9090 / SPN-7331 / SPN-2718`, and the
  embargoed home worlds `Wolf-1061c / TRAPPIST-1e / Eris Relay`. Neither is
  merely hardcoded -- both are **re-derived from the structure of whatever
  corpus the container is given**, with no labels:
  - Revoked sponsors are found by reuse frequency. Sponsor ids are near-unique
    (864 distinct over 1,000 packets, no innocent id seen more than twice)
    while revoked ones recur 13–20 times, so the cut point is visible in the
    count histogram. With the pinned list removed entirely the detector still
    recovers 6/6 at n=1000 and 5/6 at n=300, with zero false positives.
  - Embargoed worlds are found from two independent signatures: the share of
    *readable* risk panels showing `planetary_embargo` (1.000 for the two
    flagged worlds, ≤0.086 for every other), and the share of packets whose
    registry extract prints an `EMBARGO` status (0.16–0.47 for the three real
    ones, exactly 0.000 for all ten others).

  Run on the public set both detectors return exactly the pinned values. A
  pinned value is discarded only when the input corpus positively refutes it,
  so a private set that embargoes different worlds -- or that reuses one of
  these sponsor ids innocently -- overrides us, while a private set that is
  merely small does not. Absence is never treated as refutation, and neither
  is a corpus too thin for a reuse pattern to have shown; sponsor refutation
  requires at least 1,000 packets. Verified: swapping the embargo onto a
  different world in a mutated corpus moves the detector onto that world, and
  a corpus showing a pinned sponsor without the reuse signature drops it.

  Note that this symmetry is newer than the paragraph above it. Refutation was
  implemented for the embargoed worlds first, while `revoked_sponsors` remained
  additive-only -- a pinned sponsor could never be cleared, so the claim in this
  section was true of one detector and not the other. That is now fixed and
  tested in both directions. Only the three *inferred* sponsors are refutable;
  the field manual's own `PUBLISHED_REVOKED` is policy, not an induction from
  labels, and is never dropped.
- Every case in the input directory receives a prediction; no case is skipped.
- Hidden text, out-of-crop text and barcode payloads are never read as a field
  value, and never supply a value for any output field. **Nor is their presence
  used as a feature.** Six such features existed until late in development
  (`n_hidden_lines`, `has_injection`, `injection_and_clean`,
  `injection_and_damaged`, `injection_x_missing`, `hidden_density`). An ablation
  zeroing all six moved the out-of-fold classification score by 0.00 on each of
  three seeds -- 68.29 / 67.36 / 67.84, identical either way -- so the ensemble
  had never split on them. They bought nothing and were the only place the
  solution touched hidden text at all, so they were removed. The pipeline now
  reads no part of an untrusted channel, not even a count of it.

See `MEMO.md` for measurements and failure modes.
