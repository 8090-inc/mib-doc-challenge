# MIB Doc Challenge — Technical Memo

## What this system does

It reads a directory of adversarial PDF case packets and emits one schema-valid
JSONL record per case: nine extracted applicant fields, an adjudication
(`APPROVED` / `DENIED` / `NEEDS_REVIEW`), and a calibrated probability that the
adjudication is correct.

It runs fully offline on CPU. No LLM, no VLM, no cloud OCR, no network at
runtime. The only models are a 55-feature multinomial logistic regression and an
11-bucket reliability table, both shipped as JSON totalling a few kilobytes.

## Headline results

Measured with the organizer's `scripts/evaluate.py` on the 1,000 labelled
training cases.

| section | score |
| --- | ---: |
| Field extraction | 37.39 / 50 |
| Classification | 62.02 / 80 |
| Confidence calibration | 14.59 / 20 |
| Missing-case penalty | −0.00 / 10 |
| **Deterministic score** | **113.99 / 150** |

Progression: 50.77 (organizer baseline) → 87.17 → 98.54 → 103.35 → 105.26 →
110.97 → 113.99.

**The number to trust is not that one.** The final two components were fitted on
a development split, so the full-training figure is partly in-sample. On the
199-case holdout that nothing was fitted against, the system scores **116.01**
versus **112.42** for the rules alone. A 199-case fold carries real variance, so
treat +3.59 as indicative rather than exact.

Runtime under the submission contract (4 vCPU, 8 GiB, `--network none`,
`--read-only`): **1.31 s/PDF**, 1,313 s for 1,000 PDFs. Image is 435 MB.

## The central finding: the text layer is a trap

These PDFs have a rich, well-labelled text layer. Reading it naively is the
single worst thing you can do.

21.7% of packets embed an "answer key" twice per page — once as white-on-white
text, once as black text at `x0 ≈ 692` on a 612 pt page, outside the crop box.
The key's *field values* are often correct. Its *adjudication is always
`APPROVED`*, including for cases whose truth is `DENIED` with `biohazard_red`.

It is a honeypot: it buys extraction accuracy and pays for it with the −4
catastrophic false-approval penalty. Measured directly, a naive "first regex hit
over all text" scored 82% on `visa_class` against 63% for visible-only —
entirely by reading the injection.

Two consequences shaped the architecture:

1. **Hidden-text filtering is a correctness requirement, not hardening.**
   `solution/textlayer.py` is the single choke point where visible and hidden
   text are separated, by fill colour and crop box. Everything downstream
   consumes visible text only.
2. **Rendering is structurally immune.** White-on-white text renders invisible
   and off-crop text is not rendered at all, so OCR of a rendered page sees the
   visible document and nothing else. Where OCR is used, the injection cannot
   reach it even in principle.

## Architecture

A staged, inspectable pipeline. Each stage is separately testable and every
field carries provenance.

```
textlayer  → visible/hidden separation (the security boundary)
extract    → document typing, label-anchored candidates, prose scanning
ocr        → render + tesseract, only for pages the text layer left unread
normalize  → closed vocabularies, OCR-confusion repair inside ID slots
resolve    → evidence precedence, cross-page conflict, applicant attribution
policy     → deterministic rule engine from FIELD_MANUAL.md
decision   → cost-sensitive override of the rule engine's weak branches
confidence → empirical reliability table
writer     → schema-safe single-writer JSONL
```

**OCR is adaptive, not blanket.** Only 13.3% of cases can be decided from the
text layer alone and 58.5% of pages carry imagery the text layer does not
describe, so OCR is mandatory — but a page that already yielded fields is never
re-read, because the text layer is exact there and OCR would only add noise and
cost. 300 DPI was chosen by measurement: at 150 DPI tesseract misread
`SPN-3551` as `SPN-3554`.

**Evidence precedence is enforced, not assumed.** Candidates are resolved by the
manual's ranking (adjudicator note > intake form > biometric slip > sponsor
attestation > registry extract > text layer), with an exact text-layer read
beating a noisier OCR read at equal rank. Pages carrying a different `case_id`
are attributed away, because packets contain decoy applicants.

**`risk_flags` is unioned, not selected.** Flags are distributed across
documents — the biometric slip reports `illegible_biometrics` while the registry
reports `planetary_embargo` — so a single-source winner structurally cannot
reproduce a multi-flag truth.

## Cost-sensitive adjudication

The largest single loss was 241 cases hedged to `NEEDS_REVIEW` against a
decisive truth, worth 14.46 points.

The obvious fix — hedge less — is wrong, and the payoff matrix says so. For the
bucket driving those hedges, truth splits roughly evenly three ways, and
expected payoff per case is 4.18 for `NEEDS_REVIEW` against 2.90 for `DENIED`
and 1.63 for `APPROVED`. Hedging was already optimal *given that distribution*.

So the fix is not to hedge less but to condition better. `solution/decision.py`
estimates class probabilities and picks the action maximising expected payoff
under the official matrix:

```
commit to DENIED   when  8d > 2 + 5r          (d > 0.44 at r = 0.30)
commit to APPROVED when  6a > 6d + 7r
prefer APPROVED to DENIED when  a > 1.5d
```

There is no single commit threshold; it moves with how the residual probability
splits. The model is applied *only* to the rule engine's weak branches.
`adjudicator_note` and `disqualifying_flags` are 100% correct on training and
are left untouched — a model has nothing to add there and everything to lose.

## Confidence

Confidence estimates P(adjudication correct), which varies enormously by *why*
the decision was made: from 1.000 for a signed adjudicator note down to 0.238
for a decision resting on evidence we could not read. An empirical reliability
table keyed on the deciding rule, with rates shrunk toward the global mean,
takes calibration from 10.00 to **14.53** points out of fold.

Richer keys were measured and every one scored worse, because extra features
split buckets thinner without adding information. The simplest key won.

## Policy inferred from labels

`FIELD_MANUAL.md` is incomplete by design. One rule was inferred and
cross-validated:

**Three additional revoked sponsors: `SPN-9090`, `SPN-7331`, `SPN-2718`.** Of
864 distinct sponsors in training, exactly six occur four or more times — the
three named in the manual plus these three. Every other sponsor is a one-off.
All six show denial rates of 0.72–0.87 against a 0.431 baseline. A 5-fold check
derived all six in 5/5 folds with held-out denial rates of 0.63–0.87. The signal
is recurrence plus elevated denial, which is semantic rather than a filename or
case-id artefact.

## What failed

Recorded because the failures were more informative than the successes. Full
detail in `EXPERIMENTS.md`.

- **"MED-3 requires a clean biohazard check"** — not a rule. MED-3 with no
  extracted flags splits 18 APPROVED / 14 DENIED. Where the flag *is* extracted
  the existing rule is already perfect (20/20 DENIED). The gap was extraction
  recall, not policy.
- **"A DIP waiver on a non-DIP visa denies"** — not a rule. 35 DENIED / 25
  APPROVED / 20 NEEDS_REVIEW.
- **"Review-only flags are derived conditions"** — refuted across the board.
  `sponsor_id` conflict → `sponsor_mismatch` scored precision **0.000**.
- **First decision model made things worse** (56.70 vs a 58.64 baseline, false
  approvals tripling). The bug was mine: the L2 penalty was divided by `n` along
  with the gradient, making effective lambda ≈ 0.0016. The softmax saturated and
  asserted P(APPROVED) = 0.853 where the true rate was 0.395. Expected payoff
  then acted correctly on wrong probabilities. Calibrated probabilities are the
  precondition for the whole approach.
- **An instrumentation bug hid the problem for a whole cycle.** The
  "unread evidence" signal keyed on character count, but scan pages carry a
  visible header and footer, so it never fired and every misclassification
  reported zero unread pages.

## Known limitations

- **Much of the remaining extraction gap is not recoverable.** Of missed risk
  flags: 50% are absent from the document entirely, 30% exist only in the hidden
  injection. `fee_status` is unread in 445 cases, but only 6% of those packets
  contain a fee-receipt page at all. Since `scripts/evaluate.py` drops
  `unrecoverable_fields` from the denominator and the training labels carry no
  such column, the 37.39/50 likely *understates* private-set performance.
- **Folds are stratified, not grouped.** Packet layouts repeat and there is no
  template identifier to group on, so template leakage cannot be fully excluded.
  Decision features are deliberately semantic rather than layout-derived.
- **Development used a different OCR toolchain than the image.** Tuning ran on
  host tesseract 5.3.4 / poppler 24.02.0; the image ships 5.5.0 / 25.03.0, which
  changes 19 of 1,000 records. Thresholds therefore carry roughly 0.1 points of
  error. The image is self-consistent — byte-identical across two runs — but not
  identical to the development environment.
- **apt package versions are not pinned.** The base image is pinned by digest
  and installed versions are recorded in `/app/TOOLCHAIN.txt`, but a rebuild
  could still resolve different OCR packages.
- **30 catastrophic false approvals remain** on training. Of the ones examined,
  roughly half involve a disqualifying flag that appears nowhere in the visible
  document.

## What another week would buy

1. **More decision-layer features.** `missing_evidence` is still the largest
   bucket at ~0.46–0.65 correct. Which *specific* field is missing, registry
   status text, biometric confidence, and sponsor-letter agreement are all
   computed but unused as features.
2. **Rebuild the evidence cache inside the container**, removing the toolchain
   skew that every fitted threshold currently inherits.
3. **Fuzzy label matching** for OCR-corrupted labels (`amival date`,
   `sponser id`, `visa cisse`) — 206+ known occurrences, currently dropped.
4. **Grouped folds** if a layout fingerprint can be derived, to close the
   template-leakage question properly.

## Reproducing

```bash
docker build -t mib-submission .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$PWD/data/train",dst=/input,readonly \
  --mount type=bind,src=/tmp/out,dst=/output \
  mib-submission /input /output/predictions.jsonl

python3 scripts/evaluate.py --truth data/train_labels.csv \
  --submission /tmp/out/predictions.jsonl
```

Model refitting (development folds only; the holdout is never read):

```bash
python3 tools/build_evidence_cache.py data/train /tmp/evidence.jsonl
python3 tools/fit_decision_model.py /tmp/evidence.jsonl data/train_labels.csv --l2 0.01
python3 tools/fit_calibration.py /tmp/evidence.jsonl data/train_labels.csv
```

Both fits are deterministic: gradient descent initialised at zero for a fixed
iteration count, and fold assignment derived from sorted case-id order. No seeds
are involved because no randomness is.
