# Technical Memo — MIB Doc Challenge

## Approach

The pipeline treats the task as evidence engineering, not answer extraction.

1. **Injection defense first.** 843 of the 1,000 training packets carry a
   white-text "SYSTEM: … answer key" injection; the traps also include
   invisible-render-mode text and off-page spans. A span-level visibility
   filter (alpha-composited color luminance > 240, font size < 3 pt, bbox
   outside the cropbox) quarantines all of it at extraction time. Hidden text
   is never parsed; the only thing the pipeline does with it is note that a
   field's value exists *only* there — and the one rule that consumes that
   fact (`nodate-hidden`) can only ever steer a case toward NEEDS_REVIEW,
   never supply a value.
2. **Two-source extraction.** The PyMuPDF text layer is trusted first; only
   image-only pages are OCR'd. The OCR configuration was chosen by a measured
   experiment on the worst-extracting scans: a two-pass Tesseract ladder
   (psm 11 with gamma 0.7 at 200 dpi, unioned with psm 3 at 300 dpi) plus a
   `--user-words` list derived from the closed vocabularies nearly doubled
   value recovery on the experiment set (34 → 62 field-value hits/40 pages).
   Rotation is rescued via OSD when anchors are missing.
3. **Cross-page resolution.** Six form types are parsed per page with
   OCR-noise-tolerant label matching; evidence merges by the field manual's
   precedence (manual corrections > adjudicator note > intake > biometric >
   attestation > registry), foreign-applicant pages (case-id mismatch) are
   discarded, and every value snaps to a closed vocabulary (12 species, 13
   worlds, 10 purposes, 5 visa classes, 144×144 name tokens) with
   tie-refusal — an OCR'd "XW-l" refuses to guess between XW-1 and XW-2.
   Unknowns stay unknown internally; validator-safe placeholders are applied
   only at the output boundary. One deliberate exception: when a fee status is
   genuinely unrecoverable, the output row emits the calibrated majority value
   ("paid", 274/397 on such train cases) instead of "unknown" — an extraction
   best-guess that never feeds the adjudication rules.
4. **Policy learned from public labels.** Deterministic rules verified on all
   1,000 training labels: adjudicator-note verdicts (239/239 precision when
   recovered); disqualifying flags → DENIED (186/186); TRANSIT-7 → DENIED
   (53/53); unpaid → DENIED, explicit unknown fee → NEEDS_REVIEW; six revoked
   sponsors (the three public ones plus SPN-7331/2718/9090, each 100%
   non-DIP-denied with the DIP-1 exemption intact); a 180-day staleness cutoff
   anchored to the dataset version date (28/28); TRAPPIST-1e and Eris Relay
   as embargoed worlds (50/50). Every constant re-derives from
   `train_labels.csv` via `tools/mine_policy.py` — these are class-level
   policy artifacts, the same class as model weights, keyed to nothing
   case-specific. Cases no deterministic rule decides fall into empirical
   paths keyed by flag profile, fee, visa group, and evidence quality
   (OCR-used / unreadable-pages / missing-field count / biometric-reading
   presence), with Laplace-smoothed class distributions.
5. **Decision theory on the scoring matrix.** The adjudication maximizes
   expected evaluator points — E[A]=8pA−4pD+pR, E[D]=8pD+pR,
   E[R]=8pR+2(pA+pD) — with one deliberate deviation: a guard refuses
   APPROVED whenever the path's denial probability exceeds 15%. The guard
   costs ~2 local points but takes catastrophic false approvals from 17 to 1;
   the challenge's tie-breakers and review bar treat a false-approval pattern
   as the worst failure mode, and we agree.
6. **Confidence is a probability, not a vibe.** Each rule path's confidence is
   its 5-fold out-of-fold decision accuracy on train (no resubstitution
   leakage). Mean Brier 0.095.
7. **Robustness.** Never omits a case: any per-PDF exception degrades to a
   NEEDS_REVIEW fallback row. 4-way multiprocessing (a late change from the
   original serial loop; output order is re-sorted so results are
   byte-identical across runs, verified by `cmp`). ~0.4 s/PDF against the
   6 s budget.

### Task 11 update (same day)

A residual-mining pass (tools/residuals.py, single-field counterfactuals) drove four
further changes: a registry-status EMBARGO REVIEW rule path (30/2/0 on train), a
destroyed-content-page evidence feature, TSV anchor-crop re-OCR (label located via
word boxes, value re-OCR'd from a tight high-DPI crop -- rendering pixels, so hidden
text stays invisible by construction), and an unread-adjudicator-note path feature
(a packet with a note we could not read is review-leaning, 22/19/6). Host-side local score
moved 121.97 -> 122.27. Fitting policy statistics from records extracted by the
container's own tesseract then removed a fit/serve OCR skew that the finer path
keys had amplified (in-container false approvals 11 -> 1), with the false-approval
guard re-swept to pD<=0.12; sample-size shrinkage of sparse path distributions was
evaluated (smooth and thresholded variants) and rejected as strictly worse than
the tightened guard. Final in-container train score 121.58 with 1 catastrophic
false approval. The dominant remaining residual is evidence that is absent
by design: flags with no visible source anywhere in the packet (verified by manual
page renders; the value exists only inside the untrusted hidden-text answer key,
which this pipeline deliberately never reads) and fee statuses whose receipt page
does not exist. The official evaluator's unrecoverable-field handling excludes much
of that class from scoring, so official numbers should read above local ones.

## Results (local, public train labels)

```
Field extraction:      41.58 / 50
Classification:        64.20 / 80
Calibration:           16.19 / 20
Missing-case penalty:  -0.00
Total:                121.97 / 150
Catastrophic false approvals: 1   |   Mean Brier: 0.095
```

Local scoring counts by-design-destroyed fields (torn, washed-out, no receipt
page in the packet) as misses; the official evaluator excludes admin-marked
unrecoverable fields from each case's maximum, so official scores should read
above the local number.

## Failure modes

- Deeply destroyed scans resist the OCR ladder; their fields resolve to None
  and the case routes to review-leaning empirical paths. That is the dominant
  residual: 155 true-APPROVED and 84 true-DENIED cases hedge to NEEDS_REVIEW.
- Scanned adjudicator notes whose "Finding" line is corrupted beyond fuzzy
  matching (e.g. OCR reads "Firing") lose the strongest evidence available.
- The FA guard intentionally hedges borderline approvals; flipping
  `FA_GUARD_MAX_PD` from 0.15 to 0.25 trades false-approval risk for ~2 points.
- A deterministic illegible-biometrics inference was tested and rejected —
  every predictor had a ≥2:1 false-positive ratio; the evidence-quality path
  features carry that signal probabilistically instead.

## With another week

- Fine-tune a Tesseract LSTM (or train a small glyph CNN) on the synthetic
  form fonts — fits the 250 MiB artifact budget and directly attacks the
  destroyed-scan tail.
- Template registration: align scanned pages to the six known form layouts
  and OCR field crops instead of whole pages.
- Barcode/QR decoding for registry cross-checks (decode as data, never as
  instructions).
- Per-path threshold sweep optimizing expected points jointly with the
  calibration term instead of a single global FA guard.
