# Technical Memo — Visible-Evidence Hybrid

## Approach

My submission treats the rendered page as the trust boundary. PDF-native text
is useful, but this dataset demonstrates why it cannot be trusted blindly:
white text, off-crop content, and hidden answer keys can all be present in the
text layer without appearing to a reviewer. I inspect native spans and retain
only spans that intersect the crop box and have sufficient contrast. Every page
is also rendered at 220 DPI and OCRed with Tesseract. The OCR text is therefore
derived from visible pixels and cannot see white-on-white prompt injections.

The OCR stage has bounded, selective fallbacks. Ordinary pages use a grayscale
PyMuPDF render. Low-confidence pages are retried with contrast enhancement and
form-line removal. PyMuPDF and Poppler rasterize some damaged synthetic scans
differently, so hard pages receive one independent Poppler render and the
higher-quality OCR result wins. The system uses four processes and one
Tesseract thread per process. It writes predictions incrementally and runs
under the supplied read-only, network-disabled Docker contract.

Field extraction is evidence-aware rather than a single regex over concatenated
text. Pages are classified as intake forms, biometric slips, sponsor letters,
registry extracts, fee receipts, or manual notes. Candidate values receive the
document precedence specified in the field manual. Explicit manual corrections
outrank the original field, including sponsor corrections embedded in an intake
page. Closed vocabularies (species, home world, visa, purpose, fee, and risk
flags) use OCR-tolerant matching; names, dates, and sponsor IDs use
context-specific parsers and conservative OCR-character repairs.
Cross-document disagreements are retained as evidence unless a trusted final
finding supersedes an inferred, non-explicit conflict.

The adjudicator is a hybrid of deterministic policy and two small offline
models. A word-and-character TF-IDF logistic model is robust to both policy
phrases and recurring OCR damage such as `DENIEN`, while an Extra Trees model
consumes the resolved structured record. Small field classifiers fill non-risk
closed-vocabulary fields only when the rule extractor is missing or the model
is highly confident. Risk flags must come from visible evidence and are never
inferred from packet correlations. Case identifiers are also removed before
vectorization. Hard guardrails cover visible manual findings, disqualifying
risks, revoked sponsors, transit classes, stale non-diplomatic packets, and
unpaid fees. Manual findings are applied first, which prevents an old or
crossed-out denial from overriding a later signed decision.

Policy-time missingness is separate from the required serialized output. The
adjudicator sees an unread fee or visa as unknown. Fold-validated field models
and fold-learned categorical priors may estimate unresolved output fields,
including a neutral in-window date when the schema requires a date but the
visible value is unreadable. Visible `$809` and `DIP-WAIVER` receipt geometry
also recover fee status when the status word is damaged. A final one-way
postcondition checks the emitted fields before confidence calibration:
disqualifying risks, revoked non-diplomatic sponsors, transit classes, stale
dates, and unpaid fees force denial, while review flags and unresolved core
evidence can only demote an approval to review. Thus output-only estimates
cannot leave a decision that contradicts the serialized row.
The output-boundary idea was inspired by the public MIT-licensed
`OUTPUT_ONLY_FALLBACKS` design in Abhishek Enaguthi's challenge solution;
`ATTRIBUTION.md` in my solution repository records the source and the
independent implementation details.

I selected the text/structured blend and decision thresholds using stratified
five-fold out-of-fold predictions. Model selection maximized the challenge's
actual asymmetric classification score subject to no more than five
catastrophic false approvals across the 1,000 public cases. Confidence is not
the winning class probability. A separate logistic calibrator is trained on
out-of-fold correctness using the complete probability vector, predicted
class, model margin and disagreement, OCR quality, missingness, document mix,
and explicit guardrail source.

## Validation discipline and results

The validation PDFs and their case IDs were never used as labels, pseudo-labels,
or model-selection feedback. The pipeline contains no per-case lookup table and
does not use filenames for anything beyond the required case ID.

On five-fold out-of-fold public training predictions, the selected policy
achieved 71.4% adjudication accuracy, 61.56/80 classification points,
15.16/20 calibration points (mean Brier 0.1209), and five catastrophic false
approvals. Emitted field accuracy is 94.0% species, 90.7% home world, 90.7%
purpose, 89.0% visa class, 83.6% arrival date, 82.9% sponsor ID, and 82.8% fee
status, for 42.53/50 extraction points. The combined development OOF estimate
is 119.25/150. Because blend and threshold selection use these OOF predictions,
this is still a development estimate rather than an untouched final audit.

The fitted full-data integration evaluation scores 134.52/150
(43.81 extraction, 72.83 classification, 17.87 calibration) with zero false
approvals. I report that only as an end-to-end sanity check, not as evidence of
generalization.

Tests cover the public evaluator/schema contract, white and off-page text
rejection, multi-page field resolution, manual-note precedence, and stale
packet policy. The fitted artifact is about 19 MB and the Docker image is about
264 MB, both comfortably inside the published limits. The final rebuild passed
a 20-packet read-only, network-disabled smoke at about 3.2 seconds per PDF
without nested parallelism or runtime warnings.

## Known failure modes

- Severe scan damage can destroy an arbitrary sponsor ID, date, or applicant
  name. The system uses a schema-valid unknown fallback and lowers confidence,
  but exact extraction credit is still lost.
- Rare risk classes (`memory_tampering` and `active_warrant`) have few public
  examples. Rules protect high-precision visible hits; learned field models
  never invent a risk flag when its evidence is absent.
- Multi-applicant packets remain difficult when the active form's case header
  is itself destroyed. Document precedence helps, but I do not claim perfect
  entity resolution.
- OCR behavior changes slightly across operating systems even with near-matched
  Tesseract versions. The final Debian image uses Tesseract 5.5.0, is tested
  under the exact contract, and character n-grams reduce sensitivity to those
  changes.
- The public manual is intentionally incomplete. I inferred only stable,
  repeated sponsor and stale-packet behavior; ambiguous cases are routed to
  review rather than accumulating case-specific exceptions.

## With another week

I would train inside the final Linux image from the start, add coordinate-aware
OCR for the fixed form fields, and put blend and field-threshold selection
inside a fully nested outer audit. I would also add a small image-quality model
for illegible biometrics, because raster damage is sometimes more informative
than OCR text. Finally, I would profile fallbacks by damage type and spend the
recovered runtime on a second OCR pass only where held-out expected value is
positive.
