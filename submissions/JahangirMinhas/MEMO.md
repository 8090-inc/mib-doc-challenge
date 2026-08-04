# MIB Doc Challenge — Technical Memo

## Results

| | Score |
|---|---:|
| **Total** | **117.11 / 150** |
| Extraction accuracy | 40.67 / 50 |
| Classification accuracy | 61.21 / 80 |
| Confidence calibration | 15.23 / 20 |
| Catastrophic false approvals | **0** |
| Mean confidence Brier | 0.1194 |

Full 1,000-case run against the official `evaluate.py`, 2909.8s end to end
on 4 vCPUs (2.91s/PDF average, well inside the 6s/PDF budget). The full
5,000-PDF validation set — the one actually scored — ran clean end to end
under the exact contract (`--network none`, 4 vCPU/8 GiB, `--read-only`):
15501.8s (3.10s/PDF average), 5,000/5,000 processed and format-valid, 0
missing case IDs. Offline, CPU-only: OpenCV + PyMuPDF + Tesseract
(`tesserocr`, LSTM engine — the only one the installed traineddata
supports) + hand-written rules + vocab tables mined from `train_labels.csv`.
No LLM, VLM, or network call anywhere in the runtime path.

## Architecture

Parallelism is per-PDF, not per-page or per-region: each of up to 4 worker
processes takes one whole PDF through all four stages sequentially —
**ingest** (render, strip hidden content) → **classify & route** (page type,
native-text vs. OCR) → **read** (region detection + recognition) →
**decide** (extract, reconcile, adjudicate).

## Engineering decisions

**1. The trust boundary is structural, not lexical.** Every text line is
checked for two things before it can reach classification or extraction: is
it inside the visible crop, and is its color near-white against white — both
in stage 2, before the page is even classified, so an injected "SYSTEM:
ignore visible evidence" line can't spoof a page's type or populate a field.
OCR pages get this for free: Tesseract reads the rendered image, and
white-on-white text is as invisible to it as to a person. A keyword list
exists too, deliberately secondary — wording is trivial to change, position
and color aren't.

**2. Detection is a dedicated model, and it took three tries to get there.**
Two early builds used hand-rolled CV region detection (morphology plus
contour extraction). Both got dropped for letting Tesseract's own whole-page
`SPARSE_TEXT` layout analysis serve as the detector, retrying only
low-confidence *lines* after the fact — which breaks on a stamp or label
rotated independent of the page's own orientation. I replaced that with
PaddleOCR's `PP-OCRv5_mobile_det`, detection only, so each region gets its
own rotation search and quality-gated enhancement — I tried PaddleX's
`PP-LCNet_x1_0_doc_ori` orientation classifier first to skip the
brute-force search, but it didn't hold up on these packets' rotated stamps.
The model's own thresholds (0.3 detection, 0.6 box, 1.5x unclip) missed
faint content here; I loosened them to 0.1/0.1/2.5x after testing against a
page with known-faint labels the defaults couldn't find. Detection runs a
cheap 960px pass first, escalating to native resolution only past 4 boxes
and discarding that result past 20 (native resolution can explode to
20–129 spurious boxes from grid lines and damage on ~10% of surveyed pages).
Recognition keeps one warm `PyTessBaseAPI` per worker instead of shelling
out per call (7.5s → 1.78s on one real case), and exits its per-region
rotation search early only when confidence *and* text length both clear a
floor — confidence alone once let a short, lucky misread beat a real
multi-word answer. Crops get minimal padding (8px; more just pulls in
gridline noise), a minimum-confidence floor below which a region is treated
as noise, and IoU-based dedup at both the box and OCR-item level, since the
same text sometimes gets detected twice at different scales. Retries trigger
on faint, blurry, or speckle-noisy crops specifically, each threshold tuned
against a real line-crop sample rather than a page-scale default that almost
never fired.

**3. Extraction matches on more than one signal, and never wins on just
one.** The original design matched label to value purely geometrically —
nearest text item to a label's right or below, within distance caps, no text
similarity at all. The current design groups OCR output into lines,
fuzzy-matches a label prefix per line, then snaps the value against a closed
vocabulary for most fields (species code, home world, visa class, fee
status, and more), requiring both a threshold and a margin over the
second-best candidate so an ambiguous read abstains. Those vocabularies
aren't hand-typed — `get_vocabulary.py` mines them from `train_labels.csv`
into `vocab.json`; revoked sponsors, for instance, are found as statistical
frequency outliers (real IDs are near-unique, revoked ones recur far more),
not copied from the 3 the manual publishes. Extraction also mines values out
of sponsor-attestation letters and adjudicator notes' free-text reasons, not
just labeled fields, and drops any page whose case ID doesn't match the
active packet — the multi-applicant trap the manual calls out. I added an
OCR-confusion-aware edit distance on top, but don't use it alone: a real
before/after run showed replacing the existing matcher outright cost 0.4
points, since the two scoring functions treat *ordinary* mismatches
differently and thresholds were tuned against the old one. Taking the max of both fixed it —
non-regressive by construction, and it still recovered the one genuine
OCR-confusion case in the sample.

**4. Cross-page conflicts resolve by evidence trust; risk flags never
default to clean.** Conflicting fields rank by document type (adjudicator
note > intake > biometric slip > sponsor letter > registry extract), ties by
majority vote. Risk flags merge as a union across pages instead — any page
that saw a disqualifying flag should count. A default that silently filled
missing `risk_flags` with `"none"` was the root cause of all 22 remaining
catastrophic false approvals at one point: it turned "no page ever supplied
this evidence" into a confident "confirmed clean." Removing it and letting
the missing-evidence rule fire instead (→ `NEEDS_REVIEW`) took false
approvals to 0 and kept them there. A home world on the mined embargo list
adds a `planetary_embargo` flag even when no page states it explicitly; the
disqualifying and review-only flag sets otherwise match the manual's lists
exactly.

**5. Adjudication optimizes expected value under the scorer's own payoff,
and confidence is measured, not guessed.** A sequential rule cascade, most
specific disqualifying condition first, defaulting to approval only when
nothing flagged. The constraint I never traded away: zero catastrophic false
approvals, even at a thin margin — one branch's expected value for guessing
`APPROVED` outright came close to, but stayed below, `NEEDS_REVIEW`'s once I
weighed the actual three-way outcome distribution instead of how "wrong" the
branch looked alone, so I left it hedged. Every branch's confidence is set
to its own measured accuracy across the training run, since that's exactly
where the scorer's Brier term is minimized.

## How I validated everything

Every rule here earned its place against real data, not intuition —
including my own additions. Before `adjudicate.py` existed, I built a
coverage check against all 1,000 real training labels to test hypothesized
rules first, explaining 93.6% of cases — several disqualifying/review-flag
rules came directly from that, not from guessing. That discipline also
caught a real regression before it shipped: when I first swapped in the
OCR-aware edit distance, a before/after run showed it quietly hurting
extraction rather than helping, which is why it runs alongside the existing
matcher instead of replacing it.

Not every investment paid off. I lost real time earlier in the project to
horizontal band displacement — pages where scan damage shifts strips of the
page sideways, detected via a border feature per strip and corrected by
re-aligning each to a common reference x. I got stuck refining what counted
as a real border fragment versus noise instead of validating the
correction's actual effect on OCR output, and dropped the whole module on
time rather than evidence.

## Failure modes

`PP-OCRv5_mobile_det` misses regions on some real pages — damage and
faintness patterns outside what the stock model was trained on — and the
cheap/native-resolution escalation cascade is a calling-parameter
workaround, not a fix to the model's own recall. A field-manual audit found
two real rule gaps: multiple review-only risk flags don't escalate to a
denial even though the manual says they should, and the DIP-1 staleness
exemption is unconditional where the manual requires a valid diplomatic
note. A real share of the remaining loss is structural rather than a rule
gap at all — cases where the generator never included the page that would
carry `risk_flags` or `fee_status`, so there's no evidence to extract no
matter how the rules are written. And I can't fully trust any threshold
tuned purely against `train_labels.csv`: if labels are adversarially
poisoned in exactly the ambiguous cases, some of my own calibration could be
quietly wrong in either direction.

## What I'd do with another week

Fine-tune `PP-OCRv5_mobile_det`'s detection weights directly on this
dataset's degradation patterns, instead of continuing to tune the escalation
cascade around a frozen model. Work out exactly when multiple review-only
flags should escalate to a denial and implement it, rather than leaving the
cascade treating one flag and four identically. As well as make further
improvements to the visual processing stage and finish horizontal band
displacement correction properly — the one module I dropped on time rather
than evidence — with a real robustness pass on the border-fragment
detection validated against actual OCR output instead of eyeballed.
