# MIB Doc Challenge — Technical Memo

**Solution:** https://github.com/AdvaithCodes/mib-doc-solution

## Results

| Split | Total | Extraction | Classification | Calibration | Catastrophic |
| --- | ---: | ---: | ---: | ---: | ---: |
| Held out (n=700, never tuned on) | **122.38** | 43.69 | 63.04 | 15.65 | 1 |
| Public train (n=1000, shipped image) | 123.87 | 43.71 | 64.18 | 15.98 | 1 |

Rules and tables were fitted on the first 300 training cases only; the 700-case
row is the honest figure and the one I would forecast from. The shipped image
refits the calibration tables on all 1,000 cases, which changes no decisions.
Runtime is 1.3-3.6 s/PDF against the 6 s budget, offline, CPU-only.

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

## Failure modes

Extraction misses were audited by rendering the pages rather than inspecting OCR
strings. Of 880 misses audited across six fields: **403 have no source document
in the packet at all**, **409 sit on pages whose ink is destroyed** — 6–12% of
the printed template survives, affine registration to a clean template fails to
converge, and neither engine nor any contrast, threshold or deblur variant
recovers them — and only **68 sit on legible pages**.

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

Extraction moved 43.04 → 43.69 across these fixes. About 158 such misses remain,
worth roughly +0.9.

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
| as shipped | 64.18 / 80 |
| + true `risk_flags` | 71.49 (+7.31) |
| + true `fee_status` | 65.73 (+1.55) |
| + both | 73.93 (+9.75) |

Perfect risk-flag detection alone would lift this pipeline above the strongest
published legal score. The gap is not adjudication quality, evidence resolution
or calibration — it is one field.

It resists closing because of the arithmetic: a flag is worth 8 raw points when
right and corrupts a field worth 8 raw when wrong, so a detector must clear ~50%
precision to break even and ~75% to be worth having. Every derived-flag signal
measured here lands between 15% and 30% — cross-document name disagreement
predicts `identity_conflict` at 27% against a 4% base rate, a 6.8x lift that is
still 73% false positives. Implementing the best of them cost 0.48 points. And of
117 missed `illegible_biometrics`, 75 packets contain no biometric slip at all.

## What I would do with another week

**Resolution, not reading.** Higher resolution with deskew, image preprocessing
and template-aligned cell matching each returned zero or negative — the pages
that need them retain 6-12% of their printed ink, so there is nothing to register
against. But roughly 213 misses still hold the correct value in text already
extracted, worth about +1.2, and every fix in that class so far has paid. That is
where I would spend the first days: candidate provenance and conflict states,
so that choosing between readings is a first-class operation rather than a
by-product of document precedence.

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
