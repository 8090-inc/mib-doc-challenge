# Technical Memo

**Dinuda** · <https://github.com/Dinuda/mib-solution>

Offline Docker runtime. Tesseract, PyMuPDF, OpenCV, and two small models fit
only on the public training set. No LLM in the box, no network, no hardcoded
answers.

## What I shipped

On the full 1,000 public train cases, under the official scorer:

**129.16 / 150** — extraction 44.71, classification 67.33, calibration 17.12 —
with **zero** catastrophic false approvals and a row for every PDF.

I also ran a 900/100 split where template families stayed together and I refit
vocab, the manual gate, and the calibrator on the 900 only. The 900 scored
129.02; the held-out 100 scored **131.16**. Both CFA=0. I’m not calling that a
clean holdout — I’d already looked at the whole public set while building —
but it didn’t fall apart either.

Validation is 5,000 predictions from the same frozen image, offline, 4 vCPU /
8 GiB. It finished in about 6h 14m (**4.48 s/PDF**, under the 6s budget). 8090
has the labels; I don’t.

## How I actually worked

I didn’t start from “train a classifier on the CSV.” I started by watching how
a careful visual reader solves these packets.

I rendered pages at 200 DPI and ran isolated vision-LLM audits: one case at a
time, images only, closed vocabularies, no tools, no other packets in context.
When I cheated — contact sheets with several cases on one canvas — I got a
flashy **137.9** on ten cases. That number was fake; the model could leak
context across packets. When I did it properly, the score sat around **132**:

- isolated blind passes on a 30-case panel: about **128.8 → 132.0 → 132.3**
- three-pass consensus: **132.1**
- a 10-case validation proxy against the model’s own labels: **132.1**

So ~132 wasn’t a dream score. It was what a disciplined reader got when it
refused to invent evidence.

More useful than the number was *how* it got there. The model ignored hidden
PDF garbage and white-on-white junk. It trusted signed notes and stamps before
intake grids. It only called a fee `paid` when it could see a receipt — not
because “most training rows say paid.” When the biometric page wasn’t there, it
said `NEEDS_REVIEW` instead of soft-approving a clean-looking packet. And when
it failed, it failed on a specific strip of the page — risk header, fee band,
Finding line — not “needs a bigger model.”

That became the brief for the offline system: reproduce that discipline without
calling a model at score time.

## What the pipeline does

Treat every PDF as hostile until a claim is visibly grounded.

Native text only counts if it sits in the visible crop and survives the usual
traps (tiny text, watermarks, white fill, strike-through). Raster pages go
through selective Tesseract; I allow at most two boring restoration views
(deskew, contrast, band alignment) — no generative cleanup. Claims keep their
word boxes so I can audit where a value came from.

Fields resolve in the field-manual order: manual note, intake, biometric,
sponsor, registry, then other visible text. Vocabularies and a few sponsor /
embargo lists come from the public 1,000. Priors can fill an empty output slot
for schema completeness; they are not allowed to decide approve vs deny.

Adjudication prefers a readable manual finding. Otherwise it runs the published
policy on evidence it actually recovered. Approval is picky on purpose: risk,
fee, visa, sponsor, and arrival have to be there and not fighting each other.
If the controlling page is missing or unreadable, I emit `NEEDS_REVIEW`.

After that, two small train-only pieces:

- a deny-only gate that can turn some `NEEDS_REVIEW` rows into `DENIED` when two
  independent logistics agree (no case IDs, names, or filenames as features)
- a path calibrator that only moves confidence

The Docker image carries three artifacts: `vocab.json`,
`manual_finding_gate.joblib`, `path_calibration_bundle.joblib`.

## How I used the training labels

I never “memorized” the 1,000 answers. At build time I run
`tools/build_artifacts.py` on `train_labels.csv` and that is almost the entire
label story.

From the CSV I collect the closed menus the scorer already expects: every
species, world, visa class, purpose, risk-flag string, fee status, and
adjudication value that shows up in train. OCR and fuzzy matching are forced to
land on those strings so the model can’t invent `bioscan_red` or a new planet.
I also split applicant names into the known alien-name prefixes and the
suffixes that actually appear, and I split `risk_flags` into atoms so a damaged
line can still contribute `biohazard_red` without needing the whole pipe string
perfect.

For each field I store the **mode** — the single most common train value — as a
prior. That prior is only allowed to fill an empty output cell when extraction
came up blank. It is explicitly not proof. Early versions emitted `fee_status=
paid` because that was the mode; the LLM audits and a pile of false confidence
taught me that was cheating when no receipt was visible. Same rule for risk:
mode `none` does not mean the applicant is clean if I never saw a biometric
page.

A couple of policy lists are mined with boring recurrence rules, still only on
train:

- a sponsor is treated as revoked if it shows up on at least three non-DIP-1
  cases and every one of those is `DENIED`
- a home world is treated as embargoed if it has at least ten non-DIP-1 cases
  and all of them are `DENIED`

Those lists are small and general. They are not case-ID allowlists.

The two joblib files are the only “learned” bits beyond that table:

1. **Manual-finding gate.** I take train cases where the pipeline already found
   a manual-note path but could not read the Finding line (`NEEDS_REVIEW` /
   unreadable). Structural packet features only — page roles, damage, coverage,
   that kind of thing — go into two small logistics. Both have to fire before
   the row may flip to `DENIED`. It cannot approve, and it cannot see identity
   or filenames.
2. **Path calibrator.** After the decision is frozen, another small logistic
   maps eight structural features to confidence. It does not change the action.

I do not train on validation. I do not distill LLM oracle answers into labels.
When the runtime runs, those three artifacts are already baked in; the CSV is
not on the image.

## The score climb (and what I killed)

I logged every serious attempt in `score_history.json` — 88 entries. The path
that mattered on full train looked roughly like this:

| When | Score | Notes |
| --- | ---: | --- |
| Organizer baseline | 50.8 | Always review |
| First evidence compiler | 113.7 | Firewall + bounded OCR |
| Geometry / OOF work | ~120 | Boxes and variants |
| Clean runtime after ripping out Fold-3 tricks | 122.5 | CFA=0 |
| Fee + sponsor authority | 123.4 | Stop treating prior as proof |
| Finalizer / pillars | 125.0 → 125.2 | Promoted gate |
| Rotation / damage work | 127.3 | |
| Pre–failure-fix “current” | 126.6 | CFA=1 |
| Failure-fix pass | 129.0 | Still CFA=1 |
| **Frozen submission** | **129.16** | CFA=0; removed a dumb year-rewrite |

Things that looked clever and lost: always-on RapidOCR (−7.4), broad OCR-recall
rewrites, latent “approve when risk page is absent” models (AUC basically
chance), and rewriting every OCR year to 2026 because the public set liked that
year. That last one was especially tempting and especially wrong.

## Why I stopped around 129 instead of chasing 135

After the LLM panels, I split the 1,000 cases by whether controlling evidence
could exist on the page:

| Slice | Cases | Score |
| --- | ---: | ---: |
| Recoverable | 671 | **132.17** |
| Irreducible (risk/fee absent by template) | 329 | **110.40** |
| Full set (shipped) | 1000 | **129.16** |

On the irreducible bucket, there is often no biometric page at all. A 60-feature
model trying to guess APPROVED vs DENIED there was coin-flip. Approving the
bucket wholesale creates a pile of catastrophic false approvals. The LLM didn’t
guess those packets either — it reviewed them. So the honest “high” number on
this problem is the recoverable path (~132), not a leaderboard fantasy that
fills in silent denials.

The 135–138 figures I saw were either contaminated oracles or “what if every
recoverable case were perfect.” I want the private set more than I want a
braggy public train score.

## What’s still broken

Most wrong adjudications are still “I never saw a risk page.” Many of those
pages were never in the PDF. Cleanup and OCR cannot invent them.

Where the page *is* there but damaged, I’m still soft on fee strips, Finding
lines, and some arrivals/names. Narrow ROI work helped dates; swinging a bigger
OCR hammer made things worse.

I also still trust a clean native line too much when the generator deliberately
plants a conflicting name or visa on another page. And fee absence is awkward:
block every missing fee and you tank real approvals; ignore it and you flirt
with CFA. The frozen build stays conservative.

## If I had another week

I wouldn’t “clean up PDFs” in the Instagram sense, and I wouldn’t fine-tune a
giant vision model into the submission. The contest is offline and small.

I’d spend the week on perception and provenance for packets that still have
ink on the page:

1. A compact, layout-invariant ROI / page-role model trained with domain-
   randomized synthetic damage — so risk headers, fee bands, and Finding lines
   get the same kind of attention the visual oracle gave them.
2. A corruption-aware claim graph: rank competing values with cross-page
   agreement and uncertainty, instead of “whichever line looks cleaner.”
3. Fee presence proof that’s precise enough to stop false approvals without
   punishing every packet whose receipt is merely ugly.
4. Recalibrate on a split I haven’t contaminated yet, after those pieces freeze.

I would still refuse to learn approve/deny from template-absent risk. That’s
not humility; it’s what the measurements said.

## Disclosures

Runtime has no case-ID, filename, identity, or validation lookup. Validation
PDFs were unlabeled inputs for `predictions.jsonl` only. Vision-LLM audits were
dev-time ceiling and behavior study — none of that output is in the image.
Third-party: PyMuPDF, Tesseract, OpenCV, scikit-learn. The pipeline code is
mine.
