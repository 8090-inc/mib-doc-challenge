# MIB Doc Challenge — Technical Memo

**Approach:** deterministic generator inversion. No LLM, no VLM, no trained adjudicator.
**Train:** 131.40/150 (extraction 45.80, classification 68.79, calibration 16.81).
**Held out:** 132.40/150 on 300 cases the fitted tables never saw.
**Runtime:** 2.90 s/PDF on the 5,000-case validation set under the official flags; image 0.23 GiB by `docker image inspect` (limit 4 GiB).

## 1. Thesis, and the number that tests it

Every packet is the output of one deterministic program. Model *that program* and you
transfer; fit statistics of the training labels and you do not.

The test: refit both fitted tables on a 700-case dev split, score the 300 cases they never
saw. Fitting on all 1,000 instead is worth **+0.16 points** on those same cases. That is the
entire quantity of train-fitting in this system. Published entries scoring ~135 on train
report out-of-fold scores of 119–128.5.

**On scale.** `EVALUATION.md` says private labels carry an `unrecoverable_fields` column —
generator-destroyed fields are removed from that case's extraction maximum — and that public
`train_labels.csv` omits it. We therefore pay full price on train for fields that no longer
exist in the document. Scored under the private semantics using a destroyed-field oracle from
our generator reconstruction, this system estimates **~135/150**. We quote the public number
because it is the one anyone can reproduce.

## 2. Architecture

1. **Visibility-filtered scan** — every span classified visible/hidden (white fill, off-crop
   bbox, sub-legible size). Hidden text never enters a prediction (§4).
2. **Dual-engine OCR** on raster pages: RapidOCR (raw + a flatten→ghost-gate→sharpen
   restoration) and Tesseract. They fail differently; the union beats either.
3. **Matched-filter reader** where both engines fail: deskew, anchor on known text (the Case
   ID comes from the filename, so each page carries its own calibration target), correlate
   rendered closed-vocabulary candidates. Gated at 100% precision on train (117/117 note
   verdicts, 98/98 biometric flag sets).
4. **Analysis-by-synthesis** on degraded form pages — label-anchored shape matching. Output
   only: it can fill a field nothing else read, but never reaches the rule engine, so it
   cannot move a verdict.
5. **Fusion** by *measured* source precedence, not the manual's ladder. The intake form is a
   deliberate decoy channel: 89% accurate on names and 90% on sponsor IDs, against 100% for
   the sponsor letter. Cross-page consensus overrides a single-support pick.
6. **Rule engine** reproducing the generator's adjudication function, plus mined rules —
   staleness against the PDF `creationDate`, Wolf-1061c as a third embargo world for
   non-diplomatic visas (51/51), DIP-1 as a blanket exemption, and the subtlest: **the
   generator adjudicates the *damaged* packet, not the underlying record.** If the intake
   Arrival Date slot is destroyed the verdict is never APPROVED (11/11, zero false positives
   across 316 clean cases). Ten packets prove it directly — a visible note reads "Arrival date
   missing from trusted visible evidence" while the label file records a date. The engine
   consumes only a typed field dict, so document bytes can never become control flow.
7. **Decision layer** — EV-argmax per stratum under the exact scoring matrix. Only
   DENIED→APPROVED is negative, so DENIED is the correct hedge for A/D uncertainty, never
   NEEDS_REVIEW. Confidence is the stratum's measured accuracy with an n≥8 support floor;
   singleton strata are memorisation and cost 2.5 calibration points out of sample.
8. **Defended constants** — the revoked-sponsor set is a union of three independent sources:
   the IDs published in `FIELD_MANUAL.md` (plus three more confirmed by frequency analysis),
   a frequency-signature miner run over whatever batch the container is actually given
   (revoked IDs recur 13–86×, legitimate ones ≤4× — exact 6/6 on both public splits, no false
   positives), and a leading-digit guard, since the generator draws legitimate IDs with
   leading digit 1–8 and reserves 0/9. The miner catches a redrawn table; the shipped set
   covers a batch too small to mine from. Staleness is computed per packet from the PDF
   `creationDate`, not a wall-clock constant.

## 3. The ceiling

A compiler + semantic decompiler regenerate packet content streams **token-for-token
byte-identical across all 6,000 public packets** (25,574/25,574 pages), recomputing every
coordinate from Helvetica metrics and layout rules. That instrument settles what the residual
errors are:

- **Scan templates carry strictly fewer fields than born-digital ones.** A rasterised fee page
  contains only Case ID and Fee Status — the `$809` / `$0 + DIP-WAIVER` geometry that
  deterministically resolves fee status is *deleted*. Registry scans drop Registry Status;
  biometric scans drop Biometric confidence. Risk flags appear on biometric pages only.
- Rasterisation therefore **removes evidence at generation time**: 89% of our risk-flag false
  negatives have no flags line anywhere in the packet.
- Independently confirmed by known-plaintext PSF fitting (each page's own label block as a
  guide star): the damage kernel measures p90 14.1 px against a 6.8 px x-height. On a quarter
  of pages the destruction is wider than the glyphs.
- The born-digital channel is *provably* exhausted — round-trip equality means a complete
  reader cannot miss visible content, and it recovers zero fields we get wrong.

Three independent instruments converge: the residual is missing information, not perception
failure.

## 4. The trap

~19% of train packets (25–30% of validation) carry a hidden white 5pt "answer key" whose
extraction fields are 90–98% correct and whose adjudication column is **inverted in 188/188
cases**, aimed squarely at the −4 cell. We use none of it. Three defences:

- **Structural** — span-level visibility filtering (colour, bbox, size).
- **Content** — the key is sometimes baked into raster *pixels*, where no structural filter
  can see it. Our OCR path was turning it into extraction candidates on three train cases
  before we caught it. Injection-shaped lines are now dropped from every OCR parser, with the
  threshold set so a legitimate adjudicator line survives.
- **Decision-layer** — *whether* a packet carries a key is not a feature either. An earlier
  version used that bit in the confidence stratum: no content leaked, but a property of the
  answer key was still steering the decision. Removing it measured **+0.09 train / +0.06 held
  out** — it was not paying for itself.

`lib/scan.py` still classifies hidden spans and nothing downstream consumes them. That is the
point: we identify the key in order to exclude it. We also declined the adjacent grey
channels — the injection's *length* alone would largely recover the missing flags, and raster
skeleton variants leak its presence. Both are key-derived.

## 5. Failure modes, disclosed

**30 catastrophic false approvals on train** (3.0% of cases, 9.8% of our approvals). We report
this because `EVALUATION.md` makes it a minimum bar and the second tiebreaker.

- **25 of 30 are an unreadable risk flag** — truth carries `biohazard_red`, `active_warrant`,
  `memory_tampering`, `planetary_embargo` or `illegible_biometrics`, and no flags line exists
  anywhere in the packet. The other 5 are destroyed fee or sponsor evidence (one case's true
  sponsor is revoked SPN-7331, where nothing was readable).
- **None is asserted confidently** — max 0.752, mean 0.689, zero above 0.90. Calibration
  already prices them.
- **It is not a policy pattern.** We checked every approval sub-stratum — by fee imputation,
  missing-field count, and whether a flags line was observed — and APPROVED is the EV-argmax
  in all of them. Forcing DENIED on our approvals costs **15.4 points** to remove 30 CFAs.

Field-level: **risk_flags 79.4%** (89% of false negatives have no evidence to read; false
positives are zero). **fee_status 86.5%** (imputed `paid` is the conditional mode in every
cell tested; 79 of 121 errors have no fee page). **sponsor_id / visa_class** errors are the
intake decoy correctly read — adjudication is still right in 25/27 and 65/67 of those. Some
40 further "errors" are correctly-priced EV hedges.

The single fitted override is `no_visa → APPROVED`: 14 cases split 10/2/2, EV 5.29 for
APPROVED against 2.86 — it wins even if the whole remainder were DENIED, and a disjoint
700-case refit recovers it independently. Overrides are fitted at rule-path level only; a
finer stratum also cleared the support floor and was worth +0.08 on train but **exactly zero**
held out, so we dropped it.

## 6. Robustness

Hardened against failures that cost whole runs rather than points, each measured against
adversarial corpora synthesised from the generator reconstruction:

- **Worker crash** (SIGSEGV/SIGKILL mid-run) lost 53 of 61 rows, scoring 18/150. Now: per-case
  isolation, a reconciliation pass, and a schema-valid backstop that imports nothing, so it
  survives a broken module. Verified 61/61 rows under all three crash modes.
- **Input delivered as `*.PDF`** produced zero rows — total wipeout from one character. Now
  case-insensitive, along with nested input directories.
- **Runaway page** — per-case `SIGALRM`, a parent deadline, and a reconciliation sweep. The
  5,000-case validation run finished in 4h02m with zero backstop rows.
- For anyone building a monitor: **calibration is not a canary.** Missing cases are excluded
  from the Brier average, so a run losing most of its rows still reports healthy calibration.

## 7. With another week

1. Replace the stratum tables with a soft-evidence rule engine propagating per-field
   posteriors through the known rule function, so verdict probability and confidence come from
   one object rather than two fitted tables.
2. Push analysis-by-synthesis into the rule path under a precision gate — output-only today
   specifically so it cannot move a verdict.
3. More adversarial validation of the batch-constant miner: it is the main defence if the
   private set redraws the revoked-sponsor table, and it is deliberately conservative — on a
   batch too small to establish a frequency signature it returns nothing and defers to the
   shipped set.

## 8. Reproducing

```bash
docker build -t mib .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=<pdfs>,dst=/input,readonly \
  --mount type=bind,src=<out>,dst=/output \
  mib /input /output/predictions.jsonl
```

No network, no randomness, no model downloads; dependencies are pinned to the versions these
scores were measured with. Two honest caveats about "deterministic":

- **Record content is deterministic; row order is not.** Rows are written in worker completion
  order, so two runs of the same input produce the same 5,000 records in a different sequence.
  Sort by `case_id` and the files are byte-identical — verified across two independent 5,000-case
  runs. Scoring is keyed by `case_id`, so order does not affect the result.
- **Not bit-identical under starvation, by design.** A per-case `SIGALRM` and a whole-run
  deadline emit schema-valid backstop rows rather than lose cases, trading exactness for
  completeness on an overloaded host. Both fired zero times on the 5,000-case run.

The submitted `predictions.jsonl` was produced by an image built from this repository at the
committed revision, verified by checksumming `/app` inside the image against the working tree.
