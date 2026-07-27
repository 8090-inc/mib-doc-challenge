# MIB Doc Challenge — technical memo

**Score on the public training split (challenge `scripts/evaluate.py`):**
`116.51 / 150` — extraction `40.39/50`, classification `60.72/80`, calibration
`15.40/20`, 0 missing cases, 6 catastrophic false approvals against 431 true
denials. Runtime 0.78 s/PDF on 4 vCPU against a 6 s/PDF budget; image 0.23 GiB.

No LLM, no network, no API keys. PyMuPDF for the text layer, OpenCV + Tesseract
for scans, a hand-written policy engine, and one 26-weight logistic model for
confidence, fitted on the public training labels.

## What the data actually is

Two facts shaped every decision:

1. **Roughly half the pages are scans.** 1,956 of 4,159 training pages carry no
   usable text layer, and 851 of 1,000 packets contain at least one. They are
   144-DPI JPEGs degraded with page skew, *per-line* jitter, faint gridlines,
   speckle, stray border ticks, decorative overlay stamps, and — in a minority —
   a 90° or 180° rotation. Anything that doesn't read scans well loses most of
   the available points.
2. **Fields are drawn from small closed vocabularies.** 12 species codes, 13
   home worlds, 5 visa classes, 10 purposes, 8 risk flags, and applicant names
   built from 144 first and 144 last name parts. This turns degraded OCR from a
   transcription problem into a nearest-neighbour problem.

## Pipeline

**Trust separation first.** Every page's text layer is split into visible spans
and untrusted ones — white fill, sub-6pt type, or geometry outside the page crop.
In the training set that isolates the injected content perfectly: every
`SYSTEM: ignore visible evidence…` payload is white 5pt text. The untrusted set
never reaches the field parser; it is only recorded as a calibration feature.
Large red overlays (`SAMPLE DENIAL`) are classified as watermarks and stripped
before the note parser looks for a verdict, per the field manual's trap list.

**Scans, line at a time.** Whole-page OCR on these documents produces garbage —
the ink covers a small fraction of a noisy page, so the layout analyser locks
onto gridlines. Instead I decode the embedded JPEG at native resolution (never
re-render — that resamples an already-lossy image), keep only glyph-sized
connected components, dilate horizontally into words, discard isolated marks,
group words into lines, deskew each line independently, and OCR one line at a
time at `--psm 7`. Crucially the OCR input is *grayscale inside a dilated glyph
footprint*, not a binary mask: the footprint removes gridlines while the retained
antialiasing is worth several characters per line.

Orientation is decided by how much real form vocabulary each of the four
rotations yields. I first tried a cheap geometric score (are lines wide and
horizontal?) and it was actively wrong — the scanned gridlines segment into
convincing-looking text lines at any angle, and it flipped pages that had read
correctly. The upright reading short-circuits, so only doubtful pages pay for
the alternatives.

**Parsing both layouts.** Native pages are two-column, so a single visual row
holds the value *and* its label, in either order and sometimes with placeholder
graphics text appended; OCR'd scans render `Label: value`. The parser locates the
label anywhere in a row, preferring the longest matching span (otherwise "Fee"
beats "Fee Status" and "Status" becomes the value), and pushes both sides through
the field normaliser, keeping whichever validates.

**Merging.** Each field is voted across pages, weighted by the field manual's
evidence precedence (note > intake > biometric > sponsor > registry) plus a bonus
for a clean text layer over OCR. Case id comes from the per-page footer, which
survives in the text layer even on scans — not from the filename.

**Vocabulary snapping** with a similarity floor *and* a margin check: a reading
that is nearly equidistant between two vocabulary entries is rejected rather than
guessed, and a value that matches nothing passes through unchanged. That is what
should keep the gazetteer from silently corrupting unseen values on the private
test set.

## The adjudication policy

The public manual covers most of it; the rest I read off the training packets'
own adjudicator notes, which cite their reasons in plain text. That surfaced two
revoked sponsors beyond the manual's list (`SPN-2718`, `SPN-9090`) and the
embargoed home world `Wolf-1061c`.

Checking each condition against the labels shows the policy is close to
deterministic: disqualifying flag → denied (186/186), `TRANSIT-7` → denied
(53/53), unpaid fee → denied (50/50, including diplomatic packets — the manual's
waiver language does *not* rescue an unpaid fee), unknown fee → review (44/44).
Review-only flags are review 78% of the time and denial the rest.

**Staleness needed a reference the packets don't contain.** The manual calls an
application stale more than 180 days before *packet receipt*, and no packet
states its receipt date. The signal is real — among otherwise-clean packets,
2025 arrival dates run 12 approved to 25 denied while 2026-01 onward runs 254 to
13 — so "now" is estimated from the batch's own arrival dates at the 95th
percentile. Not the maximum: a single OCR misreading of 2026 as 2076 would make
every other packet look stale, which is exactly what happened on my first
attempt. Judged below the adjudicator note so a signed verdict still wins. Worth
+0.87 classification points, and it drops false approvals from 10 to 6. The gain
is flat from a 180- to a 240-day threshold, so it is not fitted to one cutoff.

Applying this order to *ground-truth* fields scores 70.4/80 with 89.2% accuracy —
so the policy is essentially at its ceiling and my remaining classification gap
is an extraction gap, not a policy gap. I searched all orderings of the
conditions; the ranking is insensitive to it because they rarely co-occur.

**The one non-obvious rule.** My first working version made 74 catastrophic false
approvals. Almost all were packets where I found no risk flag — because the
biometric slip was unreadable or absent, not because the applicant was clean. So
approval now requires having actually *read* flag evidence; "no flag found"
defaults to review. That cut false approvals from 74 to 14 at no cost in total score.
I checked whether it was merely a scoring artefact: among fully-native packets
with no biometric page at all, 30% still have a real risk flag in the labels. The
evidence genuinely isn't in the packet, so review is the honest answer.

## Confidence

Calibration is scored on Brier error against "was the decision right", so the
target is honesty, not a high number. The dominant predictor is *why* the
decision was made — a signed adjudicator note is right 99.3% of the time, an
unread risk panel 25.5%. A logistic model over the decision reason, OCR fraction,
unreadable-page fraction, evidence recovered, and cross-page agreement gives a
**5-fold cross-validated Brier of 0.121** (15.2/20) against 0.216 for the
best constant predictor. I report the cross-validated figure because the
in-sample 0.114 is optimistic.

## Failure modes I know about

- **Unreadable scans dominate the loss, but less of it is recoverable than the
  correlation suggests.** Extraction accuracy is 96.1% on packets needing no OCR,
  83.3% when the scans are readable, and 71.8% when a page cannot be classified
  at all. I assumed classification was the bottleneck and made page kinds
  inferable from the fields a page parsed rather than its heading; that fixed ~30
  page kinds and moved the score by zero, because those pages were already
  contributing their fields regardless of kind. The remaining unreadable pages
  are genuinely destroyed ink, not mislabelled ones, so the correlation between
  "has an unreadable page" and "scores badly" is substantially confounded by
  damage that no OCR would recover.
- **Over-review is the largest single bucket and is not a rules problem.** 264
  packets are sent to review that should have been decided — nominally 15.8
  classification points. I tested every subgroup: no biometric page, fully
  native text, all pages classified, all seven core fields recovered. Approving
  scores worse than reviewing in every one of them; even the cleanest subgroup
  (121 packets, fully native, complete fields) splits 64 approved to 29 denied,
  where approving nets 396 raw points against 410 for reviewing. Those points
  need evidence, not a threshold.
- **Sponsor IDs are the weakest field.** They are 4 random digits with no
  vocabulary to snap to, and some are deliberately smudged. Digit-confusion
  repair helps but cannot verify.
- **The gazetteer is a generalisation risk.** If the private test introduces new
  species or worlds, the threshold and margin check should pass them through
  unchanged rather than snap them — but they would then be raw OCR, and less
  accurate. This is the part of the system I'd most want to see private-test
  numbers for.
- **Revoked-sponsor and embargo lists are learned from ~10 note citations each.**
  They are right 72–87% of the time on training. A private test with a different
  revoked set would degrade these specific rules, though not the policy shape.
- **Multi-applicant packets** are detected (conflicting case ids in headers) and
  routed to review rather than resolved per-applicant.

## What I would do with another week

1. **Template-registered field OCR.** The forms have fixed layouts. Registering a
   detected page against a template and OCR'ing fixed field boxes — instead of
   discovering lines — would recover fields on pages too degraded to segment.
   I now think this is the only remaining lever of real size, having ruled out
   the cheaper version (better page classification bought nothing).
2. **Train a small character classifier on the rendered fonts.** The generator
   uses a handful of fonts at known sizes; a few-hundred-KB CNN over segmented
   glyphs would likely beat Tesseract on this specific degradation, and fits the
   250 MiB artefact limit comfortably.
3. **Multi-hypothesis OCR with vocabulary-constrained decoding.** Keep Tesseract's
   top-N per line and score candidates against the closed vocabularies, rather
   than snapping a single noisy string after the fact.
4. **Per-field confidence, not just per-decision.** Extraction is scored per
   field; knowing which fields are shaky would let me choose between emitting a
   low-confidence reading and leaving it blank.
5. **Cross-validate the policy constants.** The revoked-sponsor and embargo lists
   are currently fitted on all 1,000 training packets with no held-out estimate
   of how much they generalise.

## Reproducing

`README.md` covers the Docker contract and the two fitted artefacts
(`mib/lexicon.json`, `mib/calibration.json`), both regenerated from the public
training split by scripts in `tools/`. Nothing is keyed to a case id or filename;
`python -m pytest tests/ -q` runs 20 unit tests covering layout parsing, OCR
normalisation, injection resistance and every policy branch.
