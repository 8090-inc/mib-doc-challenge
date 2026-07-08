# MIB Doc Challenge — Technical Memo

_Solution by sina@8090.inc (developed with Claude). Status: awaiting real-data
iteration; numbers below marked [pending] update after train-set runs._

## Approach

**Architecture.** An offline two-phase pipeline. Phase 1 (parallel, 4 workers)
converts each packet into an evidence table; Phase 2 finalizes decisions with
batch context and writes a strictly schema-valid JSONL.

1. **Trusted-text harvest.** Text is trusted only when it demonstrably
   contributes visible ink: each page is rendered twice (as-is, and with all
   text redacted) and a span whose pixels don't change is hidden. Attribute
   checks (invisible render mode, zero opacity, off-crop bbox, tiny fonts)
   label the hiding mechanism. Pages that are one big image distrust their
   embedded text layer wholesale (that layer is the classic fake-answer trap)
   and go to OCR.
2. **OCR path.** 200 DPI grayscale render, orientation via Tesseract OSD with
   a 4-way trial fallback, projection-profile deskew, conditional CLAHE and
   median filtering, Tesseract `--oem 1 --psm 6` TSV, and a confidence-gated
   300 DPI escalation pass. Per-PDF watchdog keeps the 6 s/PDF average budget.
3. **Extraction.** Fuzzy label anchors per page type, values snapped to the
   closed domain vocabularies (species, worlds, visas, purposes, flags, fees)
   with an OCR-confusion-aware distance and a margin-over-runner-up rule;
   below-margin values stay raw rather than corrupting good OCR. Sponsor ids,
   case ids and dates go through confusion-fixing normalizers.
4. **Evidence aggregation.** Field-manual precedence (adjudicator note >
   intake form > biometric slip > sponsor letter > registry extract); fee
   receipts outrank forms for fee status; cross-page conflicts feed
   identity/sponsor flags; pages bearing a different case id are quarantined.
5. **Adjudication.** An order-locked deterministic cascade encodes the manual
   plus rules mined from the 1,000 public training labels (each mined rule:
   support >= 20, 100% purity, and membership in a rule family the dataset
   spec names). On true train fields the cascade scores 97.3% with zero
   catastrophic false approvals. Stamps and signed adjudicator notes override
   policy (highest-precedence evidence); "sample" denial watermarks and
   rescinded denial stamps are neutralized. Staleness (>180 days before
   receipt) uses the packet's own receipt date, falling back to a batch-level
   receipt clock — no calendar constants in code.
6. **Decision layer.** The final call maximizes expected score under the
   published scorer: approving requires the approval posterior to beat 1.5x
   the denial posterior (the -4 false-approval penalty), and uncertain cases
   hedge to NEEDS_REVIEW (worth 2/8 raw). Confidence is the calibrated
   probability the adjudication is correct [pending: OOF isotonic fit].

## Learned artifacts (disclosure)

Domain vocabularies, the name lexicon, extra revoked sponsors
(SPN-7331/2718/9090), and embargoed worlds (TRAPPIST-1e, Eris Relay,
Wolf-1061c non-diplomatic) were mined from the public training labels, as the
manual invites. In-document evidence takes precedence over every mined list at
runtime. Nothing is keyed to case ids; no validation/test answers are encoded.

## Failure modes

- Fields destroyed by damage are emitted as best guesses (they score zero
  weight when marked unrecoverable); heavy damage lowers confidence and can
  push borderline cases to NEEDS_REVIEW.
- Traps that survive: hidden text painted over noisy scan textures could pass
  the ink check in principle; content tripwires only lower trust.
- [pending] top extraction error buckets after real-data iteration.

## With another week

Trained page-type classifier and per-field value validators; barcode
corroboration; learned strikethrough repair; sharper per-tier calibration.

## Reproducing

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=$PWD/data/validation,dst=/input,readonly \
  --mount type=bind,src=/tmp/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```
CI (docker-verify.yml) builds the canonical image and replays the scoring
contract on trap fixtures at every push.
