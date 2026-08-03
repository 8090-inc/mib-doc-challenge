# MIB Doc Challenge — Technical Memo

**126.72 / 150 on the labeled training set (official `scripts/evaluate.py`,
confidences 5-fold out-of-fold), 128.46 / 150 on a held-out 200, and
127.19 / 150 re-measured inside the shipping Docker image. Zero catastrophic
false approvals in every run ever measured** — and I know what that invariant
costs, because I measured it: an EV layer over a residual model is worth
**+4.42 train points at 23 false approvals**, and I declined it.

Six deterministic stages, and **the adjudication is a hand-written rule
cascade** — nothing is learned about *when to approve*. Four small artifacts
are fitted from the corpus (lexicons, a character-confusion matrix, per-source
error rates, the calibrator); the first three decide only which candidate
*value* a field takes, the calibrator only the emitted confidence, which never
feeds adjudication and so cannot manufacture a false approval. Ingest runs
five hidden-text trap detectors and quarantines what they catch into a channel
extraction never reads, an assertion fails a case closed if an emitted value
has no visible provenance, and a writer-level pass guarantees no APPROVED row
emits a field value that would deny that same case (**0 of 112 on train,
against 130 of 603 in our previous build**).

**Disclosure — how the unlabeled validation set was used.** We never had
validation labels, so no rule, threshold or fitted artifact was ever selected
against validation truth: **every accept/reject decision in every experiment
was made on the 1,000-case train score under the official evaluator.**
Validation *inputs* were used for three things only — distribution sanity
checks including the injected-vs-clean approval cross-tab; bug discovery (the
emission-consistency defect above was *noticed* in unlabeled validation
output, then fixed and accepted on train); and corroborating the receipt epoch
that train labels had already bound to a 49-day admissible window. That is
transductive use of test-time inputs, named plainly — and the transductive
*modelling* it invites, we tested and rejected (below).

## The largest gain in this solution came from reading someone else's

Required attribution, stated first because it is the substance. **Multi-pass
OCR pooling was found by auditing PR #51, arthurmichel00**, who reads each
scanned page 8–14 times where we read it once; the top-band crop came from
**PR #39, zeroinfinity03**, whose published measurement made us test it. No
code was taken from either — the implementation, the variant set, every
measurement and the safety guard are ours, and four of the passes those
pipelines rely on we measured and rejected.

**We had already rejected a narrower version of this, and were wrong.** Our
OCR was a *cascade*: one accepted read per page, escalating only on low
confidence — which cannot recover a line a **confident** pass silently
dropped. We had measured that class and killed it, but the measurement was on
RapidOCR, on one page population, as an escalation *trigger*, while the
conclusion we wrote covered every binarization variant everywhere. **The scope
of the measurement did not match the scope of the conclusion.** The
distinction is not cosmetic: in a cascade a worse pass can
*replace* a better one, so every variant must beat the incumbent; in a pool a
worse pass costs nothing, because a value only ever wins on higher confidence.
A whole class of transforms that are net-negative as replacements are free as
pool members. Re-measured one variant at a time on all 1,000 cases, pooling is
worth **+1.92**, and the guarded variants below add **+0.34** more. We then
re-read every prior rejection in the project for the same defect; most
survive, and now do so on current evidence rather than by inheritance.

## The two findings that were not what anyone predicted

**The favourite lost.** The top-band crop — the lever two independent entrants
call their best — is worth **+0.038 here and costs a catastrophic false
approval**. The gain came instead from *deleting our own preprocessing*:
reading the same 200-DPI render with **no binarization at all**. Our global
Otsu threshold was erasing faint strokes, and no extra resolution recovers
what a threshold already removed — which is why the un-thresholded 200-DPI
read beats the 300- and 400-DPI ones, a thresholding signature rather than a
resolution one. Character whitelisting, CLAHE, contrast-stretch and adaptive
threshold all measured ≤ 0; the whitelist changes the emitted output on **zero
of 1,000 cases**, dead as a pool member as well as as a replacement.

**The safety work came before the score work, and found something that
predates it.** Some planted "hidden" spans are white text over a *dark*
scanned region: they leave real ink, so any recognizer reads them — our own
previous build consumed injection boilerplate on **16 pages** with no guard at
all. I wrote a leak probe first, matching the payload's structural boilerplate
(`SYSTEM: ignore visible evidence`, printed visibly nowhere in the corpus),
and used it to **reject four variants before looking at their scores**, two of
them worth +0.34 together. Only then did I add a runtime guard dropping a
page's extra reads when any trips the same detector: over 1,955 pooled pages
it fires **4 times, every one on a page that genuinely carries a payload, with
zero false positives**, taking consumed-boilerplate pages from **16 to 0**. It
only ever removes readings, so it cannot manufacture evidence or open a gate.
Its limit: it keys on the payload's surface form, so a differently-worded
private corpus leaves us at the old posture — defence in depth, not a
replacement for the quarantine.

Net effect: **all nine extraction fields improved, closing roughly half the
gap to #51**, and **32 abstentions became decisions** with the
DENIED→APPROVED cell still empty.

## Measurement beat consensus on the receipt date

Staleness needs a receipt date; no document prints one, and three other
entrants converged on the PDF `creationDate`. A census of all 6,000 PDFs shows
it takes **one distinct value** — a build clock, not a per-packet signal —
whereas the epoch is *derivable*: the 180-day rule puts every non-stale
arrival in `[R−180, R−13]`, so both edges of the arrival mass name `R`, and
four derivations agree exactly. **Adopting `creationDate`, 26 days early,
would have manufactured 4 catastrophic false approvals on validation** — and
train cannot detect that, because its one case in the affected band is
diplomatically exempt.

## What I declined, and what it cost

* **The injection-inversion channel.** The planted keys are adversarially
  wrong, so they are predictive *inverted* — a key claiming DENIED implies
  truth APPROVED. A residual model exploiting it scored **+1.02 at zero train
  false approvals**, with **16 of its 17 approvals riding that inversion**.
  Declined: it is a dependency on the attack, not on the documents.
* **Three packet-topology approval pools** inside NEEDS_REVIEW — measured, and
  **every one contains DENIED truth**.
* **Deny-direction aggression**, the safe-looking half of the same idea:
  **+0.36 on full train and −0.25 on holdout.** Dead out of sample.
* **Cross-packet entity consistency** — the transductive modelling named
  above. The premise is that entities recur; they do not. `sponsor_id` takes
  864 distinct values over 1,000 cases, 819 singletons, and snapping within
  edit distance 1 **fixes 4 and breaks 71**.

## Limitations

The dominant remaining loss is structural: 176 truly-approvable and 63
truly-deniable cases sit in NEEDS_REVIEW because the generator removed the
risk panel or fee receipt while the label kept the truth — 49% of the flags
pool has no B-13 page, so the decisive evidence is absent from visible ink.
Determinism is toolchain-scoped: a 200-case A/B against a host run differing
only in tesseract 5.5.1-vs-5.5.0 diverged on 21 rows while the aggregate held,
so **the container is the canonical artifact** (calibration-independent offset
from host −0.03/150, against −0.14 before). The fitted artifacts are fitted on
1,000 cases, all quoted cross-fitted; and the receipt date remains a constant,
so a private set built at a different epoch needs it re-derived from that
batch's arrivals.

---

Every experiment, accepted and rejected, with its numbers — and the audit that
re-read every past rejection for the scope error above: `MEMO_FULL.md`.
