# MIB Document Challenge Technical Memo

## Summary

I built an offline, CPU-only document pipeline that extracts structured fields
from mixed-quality extraterrestrial work-authorization packets and adjudicates
each case as `APPROVED`, `DENIED`, or `NEEDS_REVIEW`. Run through the official
Docker wrapper, the final pipeline scored **132.44 / 150** on the 1,000 public
training cases:

| Component | Score |
| --- | ---: |
| Field extraction | 45.80 / 50 |
| Classification | 69.79 / 80 |
| Confidence calibration | 16.84 / 20 |
| Total | **132.44 / 150** |

The implementation is deterministic, uses no network access or external APIs,
and runs within the published Docker constraints. The generated validation
artifact contains 5,000 unique, schema-valid records.

## Approach

The pipeline begins by reading the native PDF text layer with Poppler. Native
text is useful on clean vector pages, but it is treated only as a source of
field candidates because hidden text may contain malicious or incorrect
instructions. Each PDF is also rendered at 150 DPI and processed by Tesseract
using page segmentation modes 3 and 11. These complementary passes recover both
ordinary page layouts and sparse stamps or handwritten corrections.

Every page is classified as an intake form, fee receipt, registry extract,
biometric scan, sponsor attestation, adjudicator note, or unknown page. Field
values are accepted only from labels and document contexts appropriate to that
field. Fixed challenge vocabularies repair common OCR errors in species codes,
home worlds, visa classes, declared purposes, and the compositional applicant
name grammar. Sponsor IDs and dates receive constrained character corrections
rather than unrestricted fuzzy matching.

Candidate resolution follows document precedence and cross-document consensus.
For example, sponsor attestations resolve sponsor and visa conflicts, while
applicant names and dates are ranked by native-text support, independent page
types, and repeated observations. Strong risk observations are unioned instead
of allowing a high-precedence note to erase a secondary biometric flag. Fee
amounts and waiver codes provide consistency checks when a degraded status word
is ambiguous.

Explicit visible adjudicator findings take precedence over inferred policy.
Otherwise, the classifier applies the public rules for disqualifying and review
flags, transit visas, revoked sponsors, fees, arrival dates, and diplomatic
exceptions. Repeated training evidence also identified two consistently
embargoed worlds, which are handled as a domain policy rather than as per-case
answers. Confidence is calibrated by evidence stratum: explicit findings are
highest, deterministic denials and review rules follow, and weak recovered
approvals are assigned lower confidence.

Low-confidence redacted packets with no recovered risk flag receive one
targeted second OCR pass. This pass renders at 300 DPI, converts to grayscale,
stretches contrast, sharpens the page, and uses Tesseract segmentation mode 6.
Restricting this expensive pass to ambiguous cases improved the public score
without applying noisier OCR to already reliable packets. On training it reduced
the remaining false-approval count produced by the preceding policy iteration
and recovered additional exact fields.

## Prompt-Injection and Reproducibility Controls

Hidden `SYSTEM` and answer-key text is never allowed to determine adjudication.
Visible OCR evidence wins over the PDF text layer. Non-sentinel hidden fields
are used only as a low-trust transcription fallback on severely damaged pages,
and known decoy values are excluded from that fallback. No case IDs or validation
answers are hardcoded.

The solution repository includes a Dockerfile and a two-argument entrypoint. It
uses Poppler, Tesseract, ImageMagick, and the Python standard library. A smoke
test passed with networking disabled, a read-only filesystem, four CPUs, 8 GiB
of memory, and a 2 GiB temporary filesystem. The image is approximately 93 MB.

## Failure Modes

The largest remaining errors are severely degraded handwritten notes where even
the high-resolution pass cannot recover a complete risk phrase. Some packets
also contain multiple plausible OCR spellings of a short enum or conflicting
values repeated across different forms. Conservative fuzzy thresholds avoid
many false matches, but they necessarily leave some fields unrecovered.

Adjudication is harder when a packet has no explicit finding and the decisive
evidence is entirely illegible. The weak-evidence review rule trades some false
reviews for fewer unsafe approvals, although the public training confusion
matrix still contains 35 denied cases predicted as approved. Finally, confidence
is calibrated on only 1,000 public cases, so evidence strata with few examples
may be less reliable on the private distribution.

## What I Would Improve With Another Week

I would add page-level image quality measurements and route each page to a small
set of preprocessing recipes instead of using one generic retry. I would also
train a lightweight, fully offline character-level model on synthetic
degradations for dates, sponsor IDs, and risk phrases, evaluated with grouped
cross-validation to prevent packet-template leakage. A final priority would be
better uncertainty decomposition: separate extraction confidence for each field
from policy confidence, then calibrate the resulting adjudication probability on
out-of-fold predictions rather than hand-selected evidence bands.
