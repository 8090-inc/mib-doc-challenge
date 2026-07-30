# MIB Doc Challenge — Technical Memo

## Approach

The pipeline is built on one premise: in a corpus with planted decoys, hidden answer keys, and
labels that sometimes have no evidence at all, the winning move is to read only what is provably
trustworthy, never guess, and spend the residual uncertainty optimally against the scoring
function. Architecture:

`PDF → trusted-evidence ingest → constrained-decoding OCR → deterministic FIELD_MANUAL rules → EV-argmax residual layer → isotonic confidence`

**Trusted-evidence ingest.** Every text span is visibility-classified; hidden/white/off-crop/
answer-key/barcode text is usable as a risk signal only. Critically, untrusted regions are
redacted from page rasters *before* any OCR engine sees them, so a planted answer key provably
cannot leak into the pipeline — `tests/test_ocr.py::test_hidden_key_invisible_to_ocr` plants a
white-on-grey key that RapidOCR reads off the raw raster and asserts it does not survive
redaction. **Constrained-decoding OCR** (tesseract + RapidOCR) never emits free text: every value
snaps onto closed vocabularies (a 21-template adjudicator-note reason set, 10 purposes, 13 worlds,
12 species codes, 5 visa classes, 144 name tokens); below-threshold means *unread*, never guessed.
**Deterministic rules** handle definitive evidence — the native note `Finding:` line is
label-truth 140/140 on the 800-case tune split (162/162 corpus-wide); transit/fee/embargo/staleness deny paths measure 95–100% where they
fire. The **EV layer** adjudicates the 286-case residual, and an isotonic curve calibrates
confidence after the policy. Runtime is fully offline and LLM-free (rules, two OCR engines, an
8 KB logistic artifact); LLM tooling was used at dev time for analysis per challenge rules. Runs
are byte-identical and average ~1.5–1.6 s/PDF against the 6 s budget.

## Decision theory

Per-case utility ∝ classification_raw − 4·Brier, with confidence = P(chosen class correct):

| predicted \ truth | APPROVED | DENIED | NEEDS_REVIEW |
|---|---|---|---|
| APPROVED | 8 | **−4** | 1 |
| DENIED | 0 | 8 | 1 |
| NEEDS_REVIEW | 2 | 2 | 8 |

This gives EV(A)=8p_A+p_N−4p_D−4p_A(1−p_A), EV(D)=8p_D+p_N−4p_D(1−p_D), and
EV(NR)=2+6p_N−4p_N(1−p_N), with three non-obvious consequences. NEEDS_REVIEW is *dominated* when
p_N≈0 — the reflexive "punt when unsure" is often wrong. DENIED, which never scores −4, is the
safe hedge whenever an approval is blocked and p_D>0.366; below that, punt. And punts must carry
*low* confidence (≈P(truth=NR)) or Brier claws back the 2 points. The residual layer is a
multinomial logistic regression over ~80 evidence-quality features (read states, decoy indicators,
scan structure, OCR confidence aggregates), fit strictly 5-fold out-of-fold, feeding the EV argmax
with a CFA guard p_D<τ. τ=0.05 was chosen under a hard OOF-CFA≤2 constraint; the unconstrained
optimum (τ=0.366) buys ~2 more points at ~21 catastrophic false approvals and was rejected.

## Silent denials and the structural CFA defense

The organizers ruled (issues #4/#5) that some DENIED labels have zero recoverable in-packet
evidence; NEEDS_REVIEW is the correct output there. I measured this directly: the *cleanest*
evidence bucket — zero scan pages, all core fields natively read, registry CLEAR, fee paid — is
89 tune cases with truth 61 A / 10 D / 18 NR. Roughly 10% of every clean-looking shape is
contaminated, and every contaminated case carries a truth flag with no textual trace in the PDF.
These packets are feature-identical to true approvals: the two OOF catastrophic false approvals
sit at p_D 0.028 and 0.015, below any usable threshold — no probability guard can separate them
without blocking the approvals that share their feature vector byte-for-byte.

The holdout gate confirmed this is the binding failure mode. Run **once** as a final gate, the
probability-guard configuration scored **119.76 with 5 CFAs** in 200 cases — all five consistent
with the silent-denial pattern. In response I implemented a structural guard: approvals
additionally require *positively-read clean evidence* — a decoded `Observed flags: none` B-13
line or an approving note — precisely the document silent-denial packets structurally lack. To be
exact about what the holdout influenced: the design principle ("never approve on absence of
evidence") predates the holdout run and had governed the deterministic approval path all along;
the holdout result was used once, to decide that the EV layer must also obey it. No threshold,
model, or rule was fit to holdout cases, and the guard's cost/benefit was measured on tune/OOF
only. Cost on tune: 127.95 → 127.02. Expected
value on unseen data is positive: each blocked CFA recovers +6 raw against −6 per lost approval,
and the holdout counts favor blocking.

## Honest self-forecast

| checkpoint | tune score | CFA |
|---|---|---|
| Contract-valid stub | 53.69 | 0 |
| Text-layer rules | 108.22 | 0 |
| + constrained OCR | 123.26 | 0 |
| + EV residual layer | 127.79 | 0 |
| + fee-line recovery grind | 127.95 | 0 |
| + structural approval guard | 127.02 | 0 |
| **Final (receipt-consistency + output-fill round)** | **128.32** | **0** |
| Holdout run 1 (probability-guard config) | 119.76 | 5 |
| **Holdout run 2 (shipped config, final SHA)** | **121.97** | **2** |

127.02 is in-sample-flattered: the shipped EV artifact is refit on all 800 tune cases, and while
the refit shows +327 classification raw, the leakage-free OOF estimate of the same layer is +167
(~2.1 points less). I forecast ~120–125 on unseen labeled data — and then measured it: a
second, final holdout run on the shipped configuration (disclosed as the holdout's second and
last use; nothing was changed afterward) scored **121.97 with 2 CFAs**, inside the forecast band,
with the structural guard converting the first run's 5 CFAs into 2 — both residuals consistent
with the irreducible silent-denial pair the OOF analysis predicted. Calibration (17.2/20, mean
Brier 0.069) is near its mathematical ceiling — with residual-pool accuracy around 58%, honest
confidences cannot push Brier much lower.

## Final round: reading and filling harder, adjudication guard untouched

The last pre-ship round (127.02 -> 128.32, CFA still 0) attacked extraction only
through CFA-risk-free channels, several adapted from public MIT-licensed
solutions with attribution (AUDIT.md "Attribution"): (1) the receipt's
redundant Amount/Waiver rows outrank its printed Fee Status cell — measured
242/242 + 83/83 + 40/40 on tune, this also un-denied two truth-APPROVED/NR
packets whose receipts carried planted "unpaid" status cells against an
$809.00 amount; (2) watermarked SAMPLE pages, excluded from all adjudication
evidence, print the true field value 76-100% of the time (measured per field)
— their constrained-decode reads now serve as last-resort *output-row fills
only*, in a channel policy/EV code never consults; (3) hard-embargo home
worlds imply the planetary_embargo output flag (36/36), name conflicts imply
identity_conflict (7 fixes / 2 breaks), and the OCR-detected rescission
marker — 0/6 against truth flags where the native marker is 8/8 — no longer
emits a flag. Conditional fills from label correlations were measured and
rejected as noise. The EV layer was refit (OOF utility 921 vs 912, same two
irreducible silent-denial CFAs, tau_d unchanged at 0.05).

## Failure modes and audit notes

Three defects were caught only by full-contract rehearsal, each fatal in production: (1) rapidocr
silently pulled full `opencv` needing `libGL`, which would have crashed the `--network none`
container — forced headless, plus a loud stderr warning on mass exception-fallback; (2)
tesseract's OpenMP pragma ignores `OMP_NUM_THREADS`, oversubscribing the 4 vCPUs —
`OMP_THREAD_LIMIT` fixed it, 11.4 → ~1.4 s/PDF with byte-identical predictions; (3) one
calendar-impossible OCR'd date would have exit-2'd the *entire submission* — both date decoders
now reject invalid dates and an output-side sanitizer guarantees every row validates.

Learned constants, disclosed with their generalization basis:

| constant | evidence basis | why it generalizes |
|---|---|---|
| 6 revoked sponsors (3 named in manual + SPN-2718/9090/7331) | mined from in-packet adjudicator revocation lines / signatures | runtime check is a 6-ID constant list, applied to the post-correction sponsor, only with a non-DIP-1 visa positively read |
| Embargo worlds — hard: Eris Relay (13/13 D), TRAPPIST-1e (24/24 D); soft: Wolf-1061c (non-DIP-1 only) | in-packet "Embargo home world" notes + registry `EMBARGO REVIEW` | deny-only (can never cause a CFA); a blanket Wolf-1061c rule would have false-denied 11 approved diplomats — measured and rejected |
| Closed value vocabularies incl. arrival year ∈ {2025, 2026} (948/52, zero others) | value-level priors, not case-keyed | constrain OCR snapping; an out-of-range year is provably a digit misread ('6'→'8') |
| Staleness cutoff = PDF `creationDate` − 180d | no receipt date printed on any page; metadata proxy measures 28/28 | fixed 2026-06-29 fallback if metadata is absent |

Negative results I measured and rejected: relaxing the B-13 requirement to "no flag evidence
found" added 75 approvals and 18 CFAs; corroborated approval for B-13-absent packets bought 6
CFAs; both unshipped. Remaining known weaknesses: 3 double-print/ghosted B-13 scans unreadable by
both engines; the ~10% silent-denial contamination is irreducible by any in-packet reader; and
staleness keys off PDF metadata — if the private set's creation dates differ from the corpus
convention, the fallback constant takes over.

## With another week

Distill a small character-recognition model targeted at double-print/ghosted scans (the 3
unreachable B-13s and the residual fee lines); region-level ensemble reconciliation between the
two OCR engines instead of value-level voting; a proper document-set consistency model across the
six form types (cross-page agreement as a first-class probability, not a bonus term); and
active-learning annotation of the 286-case residual pool, where labeling effort concentrates
exactly where the EV layer is least certain.

## How this was built

I used LLM tooling from day one, as the challenge rules permit — first to get oriented in an
unfamiliar problem (reading the evaluator source, the field manual, and the organizer's issue
rulings, and pulling apart the scoring math), then to shape a plan, and then as agents doing the
heavy implementation work. The part I consider my actual contribution is the process wrapped
around them: the plan was torn apart by independent adversarial review twice before any code was
written (the second round caught a real bug in the first round's fix), every workstream's output
was re-verified against the code and the official evaluator before merging, the memo itself went
through a blind forced-rank review against two competitors' memos with identities stripped, and
the holdout/ledger discipline exists precisely because generated code and analysis are
untrustworthy until independently checked. Every architectural decision, risk trade-off, and
rejected shortcut in this memo — including declining the answer-key channel that tops the
self-reported leaderboard — was a call I made and can defend.

---
*Extended audit trail — every learned constant with its in-packet evidence basis, per-gate
measurements, and the EV model card — is in `AUDIT.md`.*
