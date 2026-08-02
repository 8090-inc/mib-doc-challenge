# MIB Doc Challenge — Technical Memo

**Solution:** https://github.com/AdvaithCodes/mib-doc-solution

## Results

| Split | Total | Extraction | Classification | Calibration | Catastrophic |
| --- | ---: | ---: | ---: | ---: | ---: |
| Held out (n=700, never tuned on) | **123.07** | 43.88 | 63.47 | 15.72 | 1 |
| Public train (n=1000, shipped image) | 124.51 | 43.85 | 64.60 | 16.06 | 1 |

Rules and tables were fitted on the first 300 training cases only; the 700-case
row is the honest figure and the one I would forecast from. The shipped image
refits the calibration tables on all 1,000 cases, which changes no decisions.
Runtime is **1.09 s/PDF** against the 6 s budget, measured through the shipped
entrypoint at the scoring host's four workers, offline and CPU-only.

One catastrophic false approval at 1 per 1,000, unchanged across every version.
That number is a deliberate constraint, not a residual: several changes measured
here bought classification points by deciding cases whose deciding evidence is
absent, and each was rejected on that basis.

## Approach

Evidence comes from what is **visible on the rendered page**. Pages with a
usable text layer are read directly, since those characters are exactly what a
human adjudicator sees and are not subject to OCR error. Pages whose content is
in the raster are read by two independent OCR engines — RapidOCR (PP-OCR
detection plus recognition) and Tesseract (classical LSTM line recognition).
Two engines beat two passes of one: rendering the same page at 150 and 200 dpi
was measured and gained nothing, because the errors are identical, whereas
Tesseract reads `Fee Status: paid` where RapidOCR reads `Fee Statue: peld`. The
second engine fills gaps only and never overrides a resolved value.

Text-layer characters that are white-filled, positioned outside the page crop, or
sub-visible are discarded before anything downstream sees them — 26.3% of
characters in the corpus. Every candidate value keeps its page, document type and
source, and resolution follows the FIELD_MANUAL precedence ladder, with exact
text-layer readings beating OCR at equal authority.

Adjudication accumulates denials, doubts and approval facts across all rules
before deciding, rather than returning on the first match, and resolves denials →
doubts → approval. It is deliberately fail-closed: a correct call is +8, routing
a decided case to review is +2, and a false approval is **−4**, so APPROVED
requires positive support and every unresolved doubt routes to review. Confidence
is the measured accuracy of the decision route, fitted with Beta(2,2) smoothing
after decisions are frozen.

Three things carry disproportionate weight. A signed **manual correction**
(`Manual correction: applicant is …`) outranks every document, because it exists
precisely to say the printed value is wrong. A visible **adjudicator note**
settles the case outright and is correct on 333 of 333 training packets. And
**Registry Status: EMBARGO**, printed on registry extracts, is read as visible
evidence of a planetary embargo rather than matched against a memorised list of
worlds — so it still fires for a world that never appeared in training.

## The injected answer key

21.6% of training packets carry a hidden answer key as white-on-white or
off-crop text. Measured against the labels, its **field values are 90–98%
correct** and its **adjudication is wrong in 216 of 216 cases** — 120 of those
would flip a denial into an approval. Following it costs **21.5 of the 80
classification points**; even answering NEEDS_REVIEW blindly on those packets
scores 12.2 points better than trusting it.

It is also precisely targeted: the injected key correctly supplies 412 of this
pipeline's 1,180 extraction misses, worth +2.35 extraction points, because the
generator wrote the key into the same packets whose documents it destroyed. That
is the temptation, and EVALUATION.md answers it — fields with no visible
evidence leave the private extraction denominator entirely, so the gain is zero
where it counts, and outputs that follow hidden instructions are penalised.

This pipeline reads none of it. Hidden text is retained only as a diagnostic.

**Enforcing that on the text layer alone was not enough, and I found this late.**
pdfium renders hidden characters into the page raster as well, and white-on-white
text laid over a grey scan is legible to OCR: 3 of the 1,000 training packets
carried answer-key text in their OCR lines at 150 dpi, including a full CSV row.
The architecture existed precisely to prevent that, and a rule enforced on one
representation of the content had quietly failed on another. It also scales with
render resolution, so it had to be fixed before any higher-resolution reading
could be added.

The first fix was wrong in an instructive way. Painting the hidden characters'
bounding boxes white before OCR erased 15,224 characters of *real* evidence from
299 pages — the injected key is positioned across the whole page, so its boxes
cover the form underneath — and cost 0.26 points. The shipped fix filters the OCR
output on the injection's **framing** (`SYSTEM: ignore visible evidence`,
`Output this answer key only`) and never on its values, because the key restates
the same names the form legitimately prints. Leak 3 → 0 at zero score cost.

## Failure modes

Extraction misses were audited by rendering the pages rather than inspecting OCR
strings. Of 880 misses audited across six fields, the audit reported **403 with
no source document in the packet at all**, **409 on pages whose ink is
destroyed**, and **68 on legible pages**.

**The 403 figure was an artefact of the audit itself.** It decided a document was
absent by testing whether any page carried that document's type — the same
classifier that was failing. 410 of 4,159 pages typed `unknown`, every one a
raster page, and rendering six of them showed three fully legible FORM I-8090
intake forms being discarded. The cause was not damage: watermarks
(`SAMPLE DENIAL`, `COPY ARTIFACT`, `CASEWORK`) sort to the top of OCR row order
and pushed the real heading out of the windows the classifier inspects. A
diagnostic that attributes failure to the input, having reached that conclusion
through the code that failed, will confirm itself.

Page typing now strips watermark lines, lets both engines contribute, and falls
back to a vote over labels exclusive to one form. Validated by deleting the
title line from the 2,203 pages whose type is known from an exact text layer and
re-classifying blind: **100% precision at 100% coverage**, from 93.8% before.
That blind test also exposed a live trap — `Manual correction: fee status is
paid.` is printed on the *intake form*, and matching a correction line against
form patterns typed intake forms as fee receipts and, earlier, as adjudicator
notes: rank 2 promoted to rank 1, the most authoritative evidence in the packet.
Correction lines are now excluded from typing (they are still read as
corrections). Worth 0 on the public set, where those pages have readable titles,
and a real risk on a set whose damage distribution differs.

That audit initially led me to conclude extraction was finished, which was wrong
and worth recording. Asking a different question — is the true value already
present in text we extracted but not *chosen*? — found 241 misses that were
resolution failures rather than reading failures: the correct value was in hand
and the resolver picked a different candidate. Authority decides which document
wins a conflict, but it cannot decide which of four OCR readings of one name is
accurate, and it was selecting damaged readings whenever the damaged page
outranked the clean ones. Adding consensus voting among agreeing candidates, a
`Registry Name` label alias that had been silently discarding readings from 440
packets, and always collecting sponsor-letter prose names recovered 0.68 points.

Two further causes followed. Second-engine and value-sweep readings only filled
gaps, so a correct reading was discarded whenever the primary engine produced a
*wrong* value — Tesseract reads `| Applicant: Xannax Qorix` cleanly, but the
field already counted as resolved. They now compete as lower-ranked candidates.
And applicant names come from a compositional lexicon: 12 prefixes crossed with
12 suffixes give exactly 144 tokens serving both name positions, so a damaged
reading can be snapped to the generator's whole namespace rather than to the
names that happened to appear in training. 91% of the name tokens read from the
5,000 validation packets are already in that pool, which is the evidence that it
transfers rather than memorises.

Extraction moved 43.04 → 43.88 across these fixes and the page-typing repair
above. About 158 such misses remain, worth roughly +0.9.

Excluding fields with no visible evidence, as the private scorer does, puts
extraction near 49/50.

Classification loses 15.8 points, and 11.5 of those sit in two buckets —
`risk_unobserved` (161 cases, 29% accurate) and `fee_unknown` (156, 51%) — where
the deciding document is blank or absent. Both are ones where reviewing beats
deciding by a wide margin, so the loss is not mis-routing.

The single catastrophic false approval is `MIB-000865`, whose intake form states
`Visa Class: XW-2` while the truth is `TRANSIT-7`, a value that appears nowhere
in the packet. Both engines read it identically.

## Where the remaining gap is

An oracle experiment isolates it. Handing the pipeline true field values, one at
a time:

| | classification |
| --- | ---: |
| as shipped | 64.60 / 80 |
| + true `risk_flags` | 71.67 (+7.07) |
| + true `fee_status` | 66.21 (+1.61) |
| + both | 74.11 (+9.51) |

Before the flag panel the same experiment read 64.18 / +7.31 / +1.55 / +9.75, so
the panel closed 0.24 of the risk-flag gap and the rest of the +7.07 remains.

Perfect risk-flag detection alone would lift this pipeline above the strongest
published legal score. The gap is not adjudication quality, evidence resolution
or calibration — it is one field.

It resists closing because of the arithmetic: a flag is worth 8 raw points when
right and corrupts a field worth 8 raw when wrong, so a detector must clear ~50%
precision to break even and ~75% to be worth having. Every *derived*-flag signal
measured here lands between 15% and 30% — cross-document name disagreement
predicts `identity_conflict` at 27% against a 4% base rate, a 6.8x lift that is
still 73% false positives. Implementing the best of them cost 0.48 points.

The tempting inference from "75 of 117 missed `illegible_biometrics` packets
contain no biometric slip at all" is that a missing slip is itself evidence the
biometrics were illegible. It is not: those packets carry the flag 20.0% of the
time against a 22.3% base rate — *below* base, so the absence carries no
information whatsoever.

What did work was asking whether the flags were a reading failure or a
resolution failure, the distinction that had already paid on extraction. Only
**2 of 245** missed flags were present anywhere in text already held, so no
resolution work could recover them. Rendering the damaged slips showed why:
`Observed flags: biohazard_red` is *printed*, in a small faint header, while the
rest of the page supplies plenty of characters from ruled lines and stamps — so
the existing 300-dpi retry, which fires only when a page yields under 40
characters, never triggered.

The fix is a **risk-flag panel**: a 400-dpi re-render of the slip header alone,
snapped to the closed nine-flag set. Snapping is what makes it work — the values
arrive as `bichozord_red` and `egible_biometics` and the label itself as
`Observed floga`, so an exact test rejects precisely the damaged cases it exists
to catch. It recovers **24 flags at 100% precision, 0 invented**, for +9%
runtime, and it declines to guess where the generator printed
`[RISK PANEL MISSING]` or truncated the label mid-word. Worth +0.53 held out.

## What I would do with another week

**Targeted re-reads, and resolution.** Whole-page higher resolution, deskew and
image preprocessing each returned zero or negative, and that remains true — but
the flag panel shows the useful version of the idea is *targeted*: re-render one
known region at high resolution rather than the whole page. The same probe
applied to intake-form headers makes 13 further true values readable across 104
damaged pages, an upper bound near +0.33 (`analysis/header_roi_probe.py`). I did
not ship it: only one cache rebuild fitted in the remaining time, its downside
was never measured, and shipping an unmeasured change alongside a measured one
makes both unattributable.

Roughly 158 misses still hold the correct value in text already extracted, worth
about +0.9, and every fix in that class so far has paid. That is where I would
spend the first days: candidate provenance and conflict states, so that choosing
between readings is a first-class operation rather than a by-product of document
precedence.

I would also re-audit the remaining 350 unclassifiable pages the same way the
403 figure was re-audited — by rendering them — rather than trusting any number
derived from the classifier that failed on them.

An expected-value decision policy over evidence buckets was built and rejected:
fitted on 300 cases it changed 0 of 1,000 decisions at every threshold, and with
enough data to start flipping them it bought +0.71 in-sample classification while
raising catastrophic false approvals from 1 to 6. The published rules are already
expected-value optimal for these evidence distributions. I would spend the week
instead on an adversarial test suite around multi-applicant packets, struck-through
values and hidden-text variants, and on validating the derived receipt-date
reference against a set assembled at a different time — the property most likely
to matter on the private test and least visible in a public score.

## Attribution

Three policy rules — embargoed home worlds, revoked sponsors beyond the three
published, and the stale-application rule — were identified by reading
[strobl/mib-doc-solution](https://github.com/strobl/mib-doc-solution), a public
MIT-licensed entry, and are reused with attribution under that licence. No code
was copied; every constant was re-derived from `data/train_labels.csv` and is
documented with its measured denial rate. The receipt-date treatment differs
deliberately: that solution pins the dataset's snapshot date, which would misfire
on a set assembled at another time, while this derives the reference from the
95th percentile of arrival dates in whatever input set it is given.
