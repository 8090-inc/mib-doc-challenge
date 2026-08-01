# MIB Doc Challenge — Technical Memo

**Submission:** midasavocado · **Solution:** https://github.com/midasavocado/mib-doc-challenge-solution

## Approach

The pipeline is render-first. Every page is rasterized and read with Tesseract and
RapidOCR before anything else happens; the native PDF text layer is never a decision
input. Extraction resolves fields against the packet's active `case_id`, so pages
belonging to a second applicant in the same packet cannot contribute. Unresolved
fields get bounded, targeted retries — a 90° rotation pass for pages with a packet ID
but no recognizable heading, a 360 DPI narrow retry for names and dates, and a faded-ink
recovery pass — each of which may only fill a sentinel, never overwrite a value that
was actually read.

Adjudication is fail-closed and follows the field manual's precedence order: signed
adjudicator findings, then visible intake fields, then biometric slip, sponsor
attestation, and registry extract. Evidence that is missing, contradictory, or
illegible resolves to `NEEDS_REVIEW` rather than to a guess. A second, independently
authored pixel-evidence engine (`evidence_audit.py`) re-reads packets the primary left
uncertain using a different renderer/OCR path. It is allowed to do exactly three
things: fill an unresolved output field, enforce a visible active-case policy witness,
or preserve review when the second read proves conflict. It cannot manufacture an
approval.

**Trust boundary.** Hidden text layers, injected `SYSTEM:` spans, fake answer keys and
barcode instructions are treated as adversarial. The decoy key in the public corpus is
90–98% truthful on individual fields and wrong on the adjudication in 188 of 188 cases —
it is bait, and the private extraction maximum excludes fields recoverable only from it,
so reading it costs risk and buys nothing that scores. Every path that consumed it has
been removed; `runtime_mode()` reports `visible-evidence-only` and a test in the suite
fails the build if an untrusted-evidence default is reintroduced.

## The measurement that matters

Development used a frozen 800/200 split of the public train set, assigned by
`SHA256("mib-prospective-v1:" + case_id)` with both ID-list digests published in
`RULES.md` so the boundary is auditable without exposing the holdout. All rule
discovery, error analysis and PDF inspection used the 800. The 200 stayed sealed.

We froze a candidate and opened the holdout **once**:

| | development (800) | **sealed holdout (200)** |
|---|---:|---:|
| extraction | — | **46.47** / 50 |
| classification | — | **68.85** / 80 |
| calibration | — | **15.81** / 20 |
| **total** | 144.29 | **131.14** / 150 |
| catastrophic false approvals | 0 | **2** |

**That is a failed generalization audit, and it is the most useful number in this
submission.** The 13-point gap sits almost entirely in classification. Extraction held
at 93% — parsing generalizes. The families that did not transfer were roughly thirty
hand-promoted approval rules with median support of about five development cases each,
several keyed on categorical program hypotheses. They were individually defensible and
collectively overfit.

We did not inspect which holdout cases failed, did not tune against them, and did not
re-open the split. The response was a **subtractive** patch containing only changes
identified before the holdout score existed: default every untrusted-evidence and
low-support synthetic path off, delete them from the submission dataflow, and remove
verdict-to-risk invention. No new rule or threshold was added. The development score
falls as a result; that is the trade working.

Post-patch development score: `<TBD — rerun on the 800 after the patch settles>`.
Runtime `<TBD>` s/PDF against the 6 s budget; image `<TBD>` GiB against 4 GiB.

## Failure modes

- **Two catastrophic false approvals on the holdout**, against zero in development. This
  is the honest weak point. The subtractive patch removes the machinery most likely to
  have produced them, but that hypothesis is untested — the holdout is spent.
- **Calibration was fit against development accuracy**, which is higher than out-of-sample
  accuracy, so Brier degrades exactly where confidence matters most. 15.81/20 reflects
  that, and it is the component with the clearest remaining headroom.
- **Extraction is near its honest ceiling.** Of the residual, roughly 85% is evidence the
  organizers destroyed — fields cut out, washed out, or present only in hidden text. A
  strong-oracle probe (400 DPI, deskew, background division, four orientations, two OCR
  engines) recovered 4 of 45 sampled destroyed fields at ~30× the per-page cost.
- **Batch-coupled imputation.** Closed-vocabulary fallbacks learn modes from the current
  input batch, so output depends on batch composition. Deterministic and tie-broken by
  value, but not independent per packet.

## With another week

1. **A second sealed holdout**, and a nested loop that refits the calibrator inside it.
   The current calibrator is out-of-fold with respect to its own mapping but not with
   respect to the classifier it calibrates — that is the flaw the holdout exposed.
2. **Re-derive the removed approval families source-free.** Several plausibly capture a
   real multi-source quorum; expressed as "N independent visible source types agree"
   rather than as a species/visa cell, they would carry a mechanism instead of a cohort.
3. **Region-local biometric recovery.** `illegible_biometrics` is the single largest
   extraction bucket. Whole-page quality metrics do not separate it; the detector has to
   be local to the biometric row.
4. **Property tests on the packet grammar** rather than only on the output contract.
