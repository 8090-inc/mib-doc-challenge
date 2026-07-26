# MIB Doc Challenge — Technical Memo

## Results (public train set, official evaluator)

| Section | Score | Honest 5-fold OOF |
| --- | ---: | ---: |
| Field extraction | 41.3 / 50 | 41.3 |
| Classification | 66.8 / 80 | 60.7 |
| Confidence calibration | 16.6 / 20 | 14.6 |
| Missing-case penalty | −0.0 | −0.0 |
| **Total** | **124.7 / 150** | **~116** |

Runtime: ~1.2 s/PDF on 4 vCPU (budget: 6 s/PDF). All 1000/1000 cases answered.
The in-sample numbers use a model fitted on all train labels; the OOF column is
the out-of-fold estimate and the better predictor of validation performance.
Public-label extraction understates private scoring: fields destroyed by the
generator are excluded from the private per-case maximum, and most of our
remaining extraction misses are exactly those fields.

## Architecture

Two-phase offline pipeline (no LLMs/VLMs/network):

1. **Trusted-text harvest** (PyMuPDF). Text is trusted only when it
   demonstrably contributes visible ink: each page renders twice — as-is and
   with all text redacted — and spans whose pixels don't change are hidden
   (catches white-on-white, invisible render mode, covered-by-rectangle, and
   clipped text with one mechanism). Off-crop, zero-opacity, and tiny-font
   checks label the hiding method. Image-dominated pages distrust their
   embedded text layer wholesale (the fake-OCR-layer trap). Answer-key /
   "SYSTEM:" instruction lines are dropped as untrusted even when visibly
   rendered, per the field manual.
2. **OCR path** (Tesseract 5, subprocess, TSV word confidences). 200 DPI
   grayscale; OSD orientation with a 4-way fallback; projection deskew;
   best-of-variants enhancement — raw, percentile contrast stretch, CLAHE,
   and a dark-percentile ink isolation that recovers washed-out pages by
   keeping only the darkest ~1% of pixels (dropping ruling lines and haze);
   confidence-gated 300 DPI escalation. Per-PDF watchdog and a batch governor
   stay inside the 6 s/PDF budget.
3. **Field extraction**: fuzzy label anchors per page template plus an
   unanchored vocabulary sweep (rescues values when OCR garbles the labels),
   OCR-confusion-aware snapping to the closed domain vocabularies with a
   margin-over-runner-up gate, format normalizers for sponsor ids and dates,
   and a name lexicon learned from training labels. Specialized parsers read
   sponsor attestation letters ("Sponsor SPN-#### attests that <name>…"),
   adjudicator notes ("Finding: DENIED. Reason: …"), registry status, and
   biometric confidence.
4. **Evidence aggregation** follows the manual's precedence ladder
   (adjudicator note > intake form > biometric slip > sponsor letter >
   registry extract), with fee receipts authoritative for fees; cross-page
   conflicts feed identity/sponsor flags; pages carrying a different case id
   are quarantined.
5. **Adjudication**: an order-locked deterministic cascade encodes the manual
   plus train-mined rules (TRANSIT-7, embargo worlds incl. Wolf-1061c's
   diplomatic exemption, revoked sponsors, fee rules, arrival staleness
   against the packet's receipt window — computed relative to the batch, no
   calendar constants). A regression gate proves the cascade reproduces
   973/1000 with zero false approvals on true fields. Non-forced cases go to
   a 400-tree random forest over extraction-quality features (JSON-exported,
   evaluated by a pure-python tree walker — no pickle, no sklearn in the
   container), and the final decision maximizes expected score under the
   published rubric: approving requires the approval posterior to outweigh
   1.5× the denial posterior, and uncertain cases hedge to NEEDS_REVIEW.
6. **Confidence** is the out-of-fold-calibrated probability the adjudication
   is correct (monotone binned calibration), clamped to [0.05, 0.97].

## Learned artifacts (disclosure)

Domain vocabularies, the 144×144 applicant-name lexicon, mined revoked
sponsors (SPN-7331/2718/9090 beyond the manual's three), embargoed worlds,
the adjudication forest, and the calibration bins are all derived from the
public training set, as the challenge invites. In-document evidence always
outranks mined lists at runtime. Nothing is keyed to case ids; no validation
or test answers are encoded anywhere.

## Failure modes

- Heavily damaged packets where the generator destroyed the evidence stay
  imperfect by design; the EV layer hedges them to NEEDS_REVIEW and the
  calibrated confidence drops accordingly.
- Risk flags with no visible manifestation (e.g. a flag whose only trace was
  cut out) cannot be recovered; they are also excluded from private
  extraction maxima.
- Hidden text painted over noisy scan textures could in principle pass the
  ink-contribution check; content tripwires and the untrusted-scan-layer rule
  cover the observed variants.

## With another week

Template-registered word-crop re-OCR for the splice-damaged tail; learned
strikethrough repair; barcode corroboration; per-tier calibration heads; a
page-type CNN fallback for pages whose headers are destroyed.

## Reproducing

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=$PWD/data/validation,dst=/input,readonly \
  --mount type=bind,src=/tmp/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```
CI (`.github/workflows/docker-verify.yml`) builds the canonical image and
replays the scoring contract on trap fixtures at every push. The validation
predictions in this repo were produced by exactly this container invocation.
