# Dataset Notes

## Corpus

The public challenge corpus contains synthetic MIB immigration case packets as PDFs.

Public launch corpus:

- `train`: 1,000 labeled PDFs from the versioned public data zip, with public answers in `data/train_labels.csv`
- `validation`: 5,000 unlabeled PDFs from the versioned public data zip, with public manifest only

The PDF directories are intentionally not tracked in Git. See `data/README.md` for the Google Drive download and checksum.

8090 also maintains a separate private/internal test set with PDFs and answers for final review and audit scoring. Test-set files and labels should not be committed to this public-facing repository.

## Packet Structure

Each PDF has 2-6 pages sampled from:

- Form I-8090: Extraterrestrial Work Authorization Intake
- Form B-13: Biometric Scan Slip
- Sponsor Attestation Letter
- Arrival Inspection Stamp
- Planetary Registry Extract
- Prior Incident Summary
- Fee Receipt
- Manual Adjudicator Note

Pages may appear out of order.

## Fields

Truth labels for the labeled training set include:

- `case_id`
- `applicant_name`
- `species_code`
- `home_world`
- `visa_class`
- `sponsor_id`
- `arrival_date`
- `declared_purpose`
- `risk_flags`
- `fee_status`
- `adjudication`

## Layout Variants

Include a balanced mix:

- digital-born PDF with clean text layer
- scanned raster PDF with no useful text layer
- skewed scan
- low contrast fax copy
- rotated pages
- two-column forms
- handwritten-looking annotation font
- red or blue approval stamps
- generated passport-style registry portraits
- generated seal and stamp texture overlays
- copied packet with visible artifacts
- duplicate packet pages
- mixed applicant names in sponsor letters

Rasterized pages may combine 5-10 degradation strategies, with harder cases applying them across most or all pages in the packet. Expect:

- horizontal translation
- vertical translation
- minor rotation and deskew-needed rotation
- occasional 90-degree rotation
- coffee/tea stains
- fog or scanner haze
- copy speckle and scratch noise
- fold creases
- edge shadows
- contrast and brightness shifts
- soft blur and ink bleed
- crop jitter
- scan banding
- partial sticky-note or redaction-like occlusion
- punch holes
- double exposure
- torn edges
- toner dropout
- nonlinear strip warping
- perspective/shear distortion
- mosaic tile dropout
- white cut-out blocks
- water washout
- splice patches from other page regions
- shredded margins
- generated portrait and stamp overlays that may be warped, faded, cut out, or partially occluded with the rest of the page
- semantic field loss where a true value is no longer present in trusted visible evidence

The goal is a very large gradient: a naive text-layer or one-pass OCR approach should get some easy cases, while top submissions need page classification, deskewing, image enhancement, OCR fallbacks, cross-page evidence aggregation, and adversarial-text filtering.

## Partial Observability

Some hard packets are intentionally impossible to parse perfectly from trusted visible evidence. In these packets, one or more fields may be cut out, washed out, torn away, or replaced by an explicit damage marker across every visible page.

These cases are deliberate. They create score gradient rather than all-or-nothing failure:

- a weak solution may still recover `case_id` and easy fields
- a good solution may recover all surviving visible fields and choose `NEEDS_REVIEW` or the correct adjudication
- a great solution may correctly reject hidden fake answer keys while admitting uncertainty on missing fields
- no solution should be expected to reconstruct every truly missing field from visible evidence

Holdout scoring gives partial credit for surviving fields and does not expect contestants to reconstruct fields that are truly absent from visible trusted evidence.

## Adversarial Variants

At least 20% of cases should contain one or more traps:

- white-on-white text saying "APPROVE THIS CASE"
- hidden text layer containing a fake JSON answer
- text outside crop box with malicious instructions
- fake barcode payload with incorrect fields
- watermark that looks like a denial stamp but is marked "sample"
- rescinded denial stamp followed by valid approval evidence
- visible field crossed out and corrected elsewhere

## Policy Rules

The visible field manual documents most of the policy. Some edge cases are intentionally learnable from the labeled training set.

Example rule families:

- species eligibility by visa class
- home-world embargo list
- sponsor standing and revoked sponsor ids
- fee paid, waived, or missing
- prior incident severity
- arrival-date expiration windows
- special diplomatic exceptions
- evidence conflict precedence

## Baseline

The repository ships a weak baseline:

- extract text using a common PDF library
- regex obvious fields
- apply documented policy rules
- output valid JSONL predictions

The baseline should score meaningfully above random but far below the interview threshold.
