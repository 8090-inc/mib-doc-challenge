# MIB Doc Challenge — Technical Memo

## Approach

The pipeline is a five-stage, fully offline document-engineering system,
not a single LLM/OCR call:

1. **Ingest** (`pipeline/ingest.py`) — PyMuPDF extracts the text layer
   per span, tagged with color, font size, and bbox-vs-page-crop, so
   hidden/white-on-white/off-page text is flagged at the source rather
   than filtered later by string luck. Barcode payloads are decoded for
   metadata cross-checking (case_id, sponsor_id) at lowest trust tier,
   and are never treated as instructions. Hidden-text detection covers
   white-on-white, near-white pastels, micro-text (< 3pt), and
   off-page-boundary text.

2. **OCR fallback** (`pipeline/ocr.py`) — only runs on pages with no
   reliable selectable text layer (scanned biometric slips, faxed
   sponsor letters). Deskew via `cv2.minAreaRect` on the ink mask,
   denoise via `fastNlMeansDenoising` + adaptive threshold +
   morphological closing (to reconnect broken characters from fax
   artifacts), then Tesseract with a PSM fallback chain (PSM 6 → 3 → 4)
   to handle both structured forms and free-form layouts. Targeted
   single-page rendering stays inside the 6s/PDF budget.

3. **Classify** (`pipeline/classify.py`) — splits each page into
   sections by document-type header (INTAKE FORM, SPONSOR ATTESTATION,
   BIOMETRIC SLIP, REGISTRY EXTRACT, ADJUDICATOR STAMP) so the trust
   hierarchy can be applied per section. OCR-tolerant header patterns
   handle common confusions (I/1/l, O/0). Each section is annotated
   with `is_watermark_trap`, `is_crossed_out`, and
   `has_signed_approval` metadata for the rules engine.

4. **Extract + resolve** (`extract_fields.py`, `resolve.py`) — regex/label
   extraction produces candidate values per field with OCR-tolerant
   patterns for case_id (catches `M1B-100001`), sponsor_id (catches
   `5PN-0007`), and visa_class. Date parsing handles ISO, US, European,
   and spelled-out formats. Species codes are canonicalized (spaces →
   underscores, uppercased). Contextual fee inference detects "FEE PAID",
   "UNPAID BALANCE", and "FEE WAIVER" when the labeled field is missing.
   Resolution picks the highest-trust-tier value and only escalates to a
   majority vote within a tier if the tier itself disagrees. Multi-tier
   agreement is tracked and used as a confidence bonus. Hidden-text
   candidates are kept completely separate and can only ever demote a
   decision to NEEDS_REVIEW.

5. **Adjudicate + calibrate** (`rules.py`, `confidence.py`) — a 13-step
   rule engine implementing FIELD_MANUAL.md's decision classes:
   - Structural gates (missing case_id, arrival_date, visa_class)
   - Stamp override (highest trust, checked early, handles rescinded
     denials and crossed-out-then-signed-approved patterns)
   - Disqualifying risk flags (with stamp override escape)
   - Sponsor revocation checks
   - Fee rules (paid/unpaid/waived/unknown with waiver detection)
   - Visa-class specifics (TRANSIT-7 default deny, MED-3 biohazard,
     XW-1 30-day max, DIP-1 no sponsor/fee waiver)
   - Date staleness (> 180 days with diplomatic exemption)
   - Review flag combinations (2+ → DENIED)
   - Biometric species cross-check
   - Evidence conflicts within top trust tier
   - Hidden-only field detection

   Confidence is calibrated with penalties for OCR reliance, low-trust
   evidence, conflicts, and hidden-only fields, plus bonuses for
   multi-tier agreement and evidence richness. The distribution uses
   the full [0.05, 0.95] range for honest calibration scoring.

## Robustness features

- **Crash recovery**: if a worker process dies (e.g. segfault in native
  libs), the pool exception is caught and already-written records are
  preserved on disk.
- **Case ID deduplication**: prevents duplicate predictions across PDFs.
- **3-level case_id fallback**: resolved field → filename regex → full
  visible text scan.
- **Barcode supplementary evidence**: decoded barcode payloads provide
  lowest-trust cross-checks for case_id and sponsor_id.
- **Per-PDF timeout**: 30s hard limit prevents hung workers from
  stalling the entire batch.

## What's deliberately heuristic (and how I'd validate it)

FIELD_MANUAL.md is "incomplete by design." Several branches in
`rules.py` are conservatively tuned:

- Whether staleness (arrival > 180 days before receipt) resolves to
  DENIED vs. NEEDS_REVIEW — currently defaults to DENIED.
- Whether 2+ review-only flags always combine into DENIED, or only in
  specific combinations — currently uses the threshold from policy.json.
- The exact list of revoked sponsors beyond the 3 public ones.

`scripts_local/mine_sponsor_rules.py` is a dev-time-only script (never
part of the Docker image) that scans `data/train` + `data/train_labels.csv`
for sponsor IDs whose DENIED outcomes aren't already explained by fee/
risk-flag/visa-class rules, as a generalizable signal rather than a
memorized answer key. Run `scripts/evaluate.py` after every rule
change and diff `case_scores.jsonl` for the specific failure classes.

## Failure modes

- **Heavily skewed/rotated scans** beyond what `minAreaRect` deskew
  handles (folded documents, extreme perspective) will degrade OCR
  quality; a projective-transform deskew would help but costs more time.
- **Novel document-type headers** not in the OCR-tolerant patterns fall
  back to `TEXT_LAYER` (lowest trust), which is safe but may under-trust
  genuine evidence phrased unusually.
- **Multi-applicant packets** are handled by keying sections to the
  active `case_id` regex match — a packet where the wrong applicant's
  fields sit nearer the target case_id could mis-attribute a field.
- **Barcode-only fields**: barcode payloads are decoded and used as
  lowest-trust cross-checks but not as primary evidence, since
  FIELD_MANUAL.md only credits them as "registry metadata."

## With another week

- Replace the header-keyword section classifier with a small layout
  model (looks at font size / position clustering) so document-type
  detection doesn't depend on exact header phrasing.
- Add a projective/perspective deskew path (four-corner detection) for
  photographed rather than flatbed-scanned pages.
- Build a proper calibration curve (isotonic regression) from
  `case_scores.jsonl` instead of the current additive confidence model.
- Expand `scripts_local/mine_sponsor_rules.py` into a general "residual
  miner" that surfaces any field/value pair correlated with a mismatch
  between predicted and true adjudication, not just sponsor IDs.

## Reproduction

```
docker build -t mib-submission .
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-output/predictions.jsonl \
  --output-json /tmp/mib-output/evaluation.json \
  --case-scores-jsonl /tmp/mib-output/case_scores.jsonl
```
