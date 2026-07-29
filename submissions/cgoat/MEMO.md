# MIB Doc Challenge — technical memo

**Score on the public training split (challenge `scripts/evaluate.py`):**
`122.34 / 150` — extraction `42.55/50`, classification `63.66/80`, calibration
`16.12/20`, 0 missing cases, 6 catastrophic false approvals against 431 true
denials. Runtime 0.63 s/PDF on 4 vCPU against a 6 s/PDF budget; image 0.32 GiB.

No LLM, no network, no API keys. PyMuPDF for the text layer, PP-OCRv4 via ONNX
Runtime for scans, a hand-written policy engine, and one 27-weight logistic
model for confidence, fitted on the public training labels.

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

**Scans: the recognition engine turned out to be the whole game.** I built the
scan path around Tesseract first, and it needed a lot of scaffolding to work at
all: decode the embedded JPEG at native resolution (never re-render — that
resamples an already-lossy image), keep only glyph-sized connected components,
dilate into words, group into lines, deskew each line, then OCR one line at a
time at `--psm 7` on *grayscale inside a dilated glyph footprint* rather than a
binary mask. Whole-page Tesseract produces pure garbage on these documents,
because the ink covers a small fraction of a noisy page and the layout analyser
locks onto the scan gridlines. Orientation needed its own OCR-based vote across
four rotations, because every geometric score I tried was actively wrong — the
gridlines segment into convincing-looking "text lines" at any angle.

All of that scaffolding produced 40.7/50 extraction, and it was still misreading
`Wolf-1061c` as `Woll-1081c` and `2026-03-15` as `2028-03-16`.

Swapping the engine for PP-OCRv4 (`rapidocr-onnxruntime`, 16 MB of ONNX carried
inside the wheel) replaced the segmentation, grouping and orientation machinery
with a text detector that simply finds the boxes, and moved the score by more
than every other change I made combined:

| | Tesseract + scaffolding | PP-OCRv4 |
| --- | ---: | ---: |
| Extraction | 40.69 | **42.55** |
| Classification | 60.68 | **62.01** |
| Adjudication accuracy | 69.8% | **72.1%** |
| Total | 116.71 | **120.29** (later 121.09 with a policy fix; see below) |

The per-field gains land exactly where the old pipeline was weakest —
`sponsor_id` 65.8 → 78.7%, `arrival_date` 78.9 → 87.9%, `visa_class` 80.4 →
85.7% — and it is no slower end to end (1.00 s/PDF against 0.96), because
detection replaces the per-line calls and the orientation sweep. The Tesseract
path is still in the tree behind `MIB_OCR_ENGINE` so the comparison is
reproducible.

The one integration wrinkle: PP-OCR returns a detected box as a single token, so
`Visa Class: MED-3` comes back as `VisaClass:MED-3`. OCR lines are re-spaced on
the colon and on lower-to-upper transitions before label matching.

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

**Vocabulary snapping, and what the scoring asymmetry implies.** A wrong
extraction and a blank score identically — zero — so refusing an ambiguous match
buys nothing and forfeits the chance of being right. Below the strict threshold
the normalizer therefore still names the nearest entry, flagged as a guess.

The flag is what makes that safe. A guess is reported for extraction, but the
rules engine treats it exactly as a field it never recovered, so a guessed
`TRANSIT-7` or `Wolf-1061c` can never deny an applicant. The invariant is
checkable and I checked it: classification is bit-identical either way, 60.72/80
with the same 6 false approvals, while extraction rises. Fields whose value comes
from a regex rather than a vocabulary — sponsor id, dates — have no meaningful
"nearest" reading and stay strict.

## The adjudication policy

**A policy gap found by looking at where extraction was already correct.**
After the engine swap I went looking for cases where the extracted fields
matched the labels exactly and the packet was *still* adjudicated wrong - that
isolates a pure policy bug from an extraction one. Several were denied on
`revoked_sponsor` or `embargo_home_world` with a correctly-read `DIP-1` visa.

The manual states a sponsor is required "unless they are applying under
DIP-1" - a diplomatic packet has no work-authorization sponsor relationship to
revoke in the first place. The training labels show the same shape for the
embargo, which the manual doesn't state explicitly: every non-DIP-1
Wolf-1061c packet is denied (51/51), while DIP-1 ones split 11 approved / 10
review / 5 denied on other grounds. I checked disqualifying risk flags for the
same pattern before changing anything - they deny DIP-1 packets uniformly
(34/34) and are correctly left alone. Fixing the other two: classification
62.01 -> 62.52, calibration 15.73 -> 16.02 on refit, total 120.29 -> 121.09.

I also re-swept the staleness threshold against the corrected policy in case
the interaction shifted the optimum; 240 days is still the peak (62.52),
confirming that channel is exhausted rather than just untried.

**A field I had extracted but never used.** `registry_status` was on the
`Packet` object and reached the dev cache tool, but `main.py`'s runtime record
never included it - the signal was inert in the shipped image. Its
`EMBARGO REVIEW` value turned out to be a direct, registry-verified check that
denies regardless of visa class (DIP-1 packets carrying it are 7/9 denied, not
the clean split the home-world-name embargo gets), and it names worlds beyond
Wolf-1061c (`TRAPPIST-1e`, `Eris Relay` both appear). Wiring it in and testing
both a DIP-1-exempt and a uniform version before choosing: uniform wins, +0.40
against +0.29. Classification 62.52 -> 63.00, total 121.09 -> 121.60.

**A rule I measured, believed, and reverted.** The manual: `waived` is
acceptable "only for DIP-1 or a visible hardship waiver" - and no training
packet ever prints "hardship", so a non-DIP-1 waiver looked like it should be
at least a review trigger. Stripped of every other denial reason, those
packets do split 46 review / 37 approved / 10 denied, which reads like a
real signal. But the *marginal* population - packets the existing rules
already approve, that this one would newly flip to review - is only 55, and
67% of those are truth `APPROVED`, because rules already covering the
review-flag and fee-unknown cases had already caught the ones that needed
catching. Net effect: -1.05 points. The lesson worth keeping is to isolate
the marginal population a rule change actually touches before trusting the
label distribution of the population matching its *condition*.

The public manual covers most of it; the rest I read off the training packets'
own adjudicator notes, which cite their reasons in plain text. That surfaced two
revoked sponsors beyond the manual's list (`SPN-2718`, `SPN-9090`) and the
embargoed home world `Wolf-1061c`.

**Revoked sponsors, generalised past the ones I happened to read.** The manual
says other revoked sponsors appear in the examples without naming them, and a
fixed list only ever catches ones already seen by hand. A revoked sponsor is
denied every time it shows up, so it recurs far more than an ordinary sponsor:
on the training batch the 99th-percentile sponsor id appears twice, while
every sponsor I'd found by reading notes appears 9-32 times. `batch_revoked_sponsors`
now flags any sponsor id appearing more than 4x that 99th-percentile baseline,
recomputed fresh per input directory rather than hardcoded, with a 400-sponsor
minimum corpus size so a small run falls back to the public list instead of
treating sampling noise as a signal. This surfaced `SPN-7331` — 15 occurrences,
12 of them truth `DENIED` — which I'd missed by hand. Worth +0.66 classification
points on the training cache and drops catastrophic false approvals from 8 to 6,
measured through the real `adjudicate()` (so note-precedence cases like
MIB-000194 aren't miscredited). The mechanism is more valuable than the one id
it found here: it should also catch whichever revoked sponsors show up in the
validation and private test sets without needing another manual note-reading pass.

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
- **Eight false approvals, five of them one cause.** The packet's fee receipt was
  unreadable, so the fee defaulted to `paid` when the truth was `unpaid`.
  Requiring a *read* receipt before approving cuts them to four — but costs 2.4
  classification points, so I did not take it. Eight against 431 true denials is
  a tail, not a pattern.
- **Sponsor IDs remain the weakest recovered field** at 78.7%. They are 4 random
  digits with no vocabulary to snap to, and some are deliberately smudged, so
  unlike the vocabulary fields there is no defensible guess to fall back on.
- **Applicant-name precision looks like a bug and isn't worth fixing.** 152 names
  are wrong, half confidently snapped to real-but-incorrect lexicon entries.
  Tightening the threshold would genuinely reduce that, but it converts *wrong*
  into *blank* and both score zero.
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

1. **Not a task-specific recogniser — I tried it and it lost.** The obvious next
   step looked like training on this generator's output, and the data comes free:
   `train_labels.csv` gives the true value for every field, the detector gives
   the line box, so 3,155 genuinely-degraded line crops can be harvested with
   exact labels and no annotation. For the closed-vocabulary fields the target is
   a *class*, not a character sequence, which is a far easier problem — 12 species
   codes rather than arbitrary text. I trained a small CNN per field on a GPU,
   splitting by packet so no case straddled the split.

   It lost on every field, against the same held-out packets:

   | Field | Trained classifier | PP-OCR + vocabulary snapping |
   | --- | ---: | ---: |
   | species_code | 81.7% | **98.3%** |
   | home_world | 68.6% | **92.8%** |
   | visa_class | 54.8% | **81.7%** |
   | declared_purpose | 54.1% | **85.9%** |
   | fee_status | 64.7% | **70.8%** |

   The ceiling is data volume: ~500-900 crops per field is roughly 50 examples
   per class, against a recogniser pretrained on millions of images.

   **I then tried the follow-up this pointed at, and it also lost.** Genuine
   CTC fine-tuning from the PP-OCRv4 pretrained weights (not from scratch),
   on 80,000 synthetic line crops rendered in the generator's four fonts
   (Helvetica, Helvetica-Bold, Times-Roman, Helvetica-Oblique) plus 3,839 real
   crops harvested the same label-free way as the classifier attempt, using
   real train-packet pages this time so the transcription is exact rather than
   guessed. Training itself worked — 91.0% exact-match accuracy on a held-out
   slice of that data after 12 epochs on a GPU — but measured end to end on
   150 packets held out of *both* the crop harvest and training, against the
   same off-the-shelf pretrained model:

   | Field | Fine-tuned | PP-OCR (shipped) |
   | --- | ---: | ---: |
   | declared_purpose | 81.2% | **84.6%** |
   | sponsor_id | 78.5% | **81.2%** |
   | home_world | 88.6% | **90.6%** |
   | risk_flags | 73.2% | **74.5%** |
   | species_code | 94.6% | **95.3%** |
   | **Extraction points** | 42.09 | **42.57** |

   It lost on 7 of 9 fields net -0.48 points, despite 91% accuracy on its own
   validation split. The 91% figure was measured on data drawn 95% from my own
   synthetic renderer, so it mostly says the model learned my degradation
   pipeline, not the real one — degrading the model's general-purpose
   robustness in exchange for specializing on a reconstruction that doesn't
   quite match the actual generator. This is exactly the risk I flagged before
   starting ("I would be training against my reconstruction... not the real
   one") and built the 150-packet holdout specifically to catch; it caught it.
   I did not ship this model. Rebuilding it with the real-to-synthetic ratio
   inverted (thousands more genuine crops, a smaller synthetic share used only
   to fill vocabulary gaps) is the one variant of this idea I haven't
   falsified, but at that point the honest framing is "collect more real
   labelled data," not "fine-tune the model."

2. **Multi-hypothesis OCR with vocabulary-constrained decoding.** Keep PP-OCR's
   top-N per line and score candidates against the closed vocabularies, rather
   than snapping a single noisy string after the fact.
3. **Per-field confidence, not just per-decision.** Extraction is scored per
   field; knowing which fields are shaky would let me choose between emitting a
   low-confidence reading and leaving it blank.
4. **Cross-validate the policy constants.** The revoked-sponsor list now
   self-updates per batch (`batch_revoked_sponsors`), but the embargo world and
   the frequency-outlier threshold itself are still fitted on all 1,000 training
   packets with no held-out estimate of how much they generalise.
5. **A trained classifier under the expected-value framework — tested, not shipped.**
   I tested a plain per-path frequency lookup (fit each policy branch's outcome
   distribution, decide by expected value under the payoff matrix) against the
   shipped rules, honestly with 5-fold cross-validation, and it lost even after
   tuning Dirichlet shrinkage (62.98 vs 63.66 classification points) — sparse
   paths need more than a raw frequency table. I then trained a real
   `HistGradientBoostingClassifier` on ~30 document-evidence features
   (evidence coverage, cross-source agreement, flags, categorical fields,
   staleness margin) restricted to the 444 packets my rules don't resolve
   deterministically, and it *did* beat the rule default honestly under 5-fold
   CV (+1.53/80 classification points). But breaking the gain down by decision
   branch showed it was entirely produced by, and risked entirely on, the
   `risk_panel_unread` bucket — packets where the risk-flag evidence was never
   legible in the first place. There the model gambles on proxy correlations
   from 207 training examples, and catastrophic false approvals in that bucket
   alone rose from 6 to 29 (elsewhere the classifier was flat to slightly
   negative). That reverses the one deliberate conservative rule in this policy
   (approving requires having actually *read* flag evidence — see above), on
   exactly the branch where the training sample is smallest and the truth is
   least informed by anything I can extract. I did not ship this: the honest
   evaluation shows it works on this training split, but the risk profile it
   trades into is the wrong shape for evidence that's structurally missing
   rather than merely unresolved, and the gain does not survive outside that
   one bucket.

## Reproducing

`README.md` covers the Docker contract and the two fitted artefacts
(`mib/lexicon.json`, `mib/calibration.json`), both regenerated from the public
training split by scripts in `tools/`. Nothing is keyed to a case id or filename;
`python -m pytest tests/ -q` runs 20 unit tests covering layout parsing, OCR
normalisation, injection resistance and every policy branch.
