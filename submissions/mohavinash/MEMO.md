# MIB Doc Challenge — Technical Memo

## Summary

An offline, CPU-only, visible-evidence ensemble. On the 1,000 labeled training
packets the submitted configuration scores **135.2622 / 150** with **1
catastrophic false approval** (extraction 45.0411, classification 71.5800,
calibration 18.6411, evaluated by the official `evaluate.py`). This is an
in-sample development replay, not an unbiased private-test estimate. The retained
exact-contract Docker receipt is **4.46 seconds/PDF** on a representative
100-case run (4 vCPU, no network, read-only root); the measured incremental
raster-note and JSON-calibration stages plus the latest operator timing place
the complete refreshed route at **~5.5–5.6 seconds/PDF**, against the 6-second
budget. The reviewer stage is
additionally bounded at 3 seconds/PDF *by construction*. The 5,000 refreshed
validation predictions pass the organizer validator with 0 missing case IDs
and carry SHA-256
`c3c7098ff75921d2217bc473bb666a6c0fa467ff36160971b895e73dea85c137`.

No LLM, VLM, cloud OCR, network call, label file, case-ID lookup, or hidden
answer text is used at runtime.

## Trust boundary

The rendered page is the trust boundary. The PDF text layer in this dataset is
adversarial: ~18–21% of packets carry a hidden white/off-crop "answer key"
whose adjudication is poisoned toward APPROVED. Native text spans are kept
only when visibly rendered and template-consistent; everything else must come
from pixels via OCR. Values are accepted only when spatially anchored to a
visibly rendered form label — bare or CSV-style lines are never evidence.
Hidden content can push a decision only *away* from approval, never toward it.
We deliberately do not transcribe answer-key field tokens, although that
measurably raises public-train scores: it is the planted trap, and it fails
the "visible evidence beats hidden text" rule that the private set can enforce
at will.

## Architecture

1. **Render-first primary.** Every page is rasterized and read with Tesseract
   layout OCR; fields resolve by label anchoring, closed-vocabulary snapping,
   and the field manual's document-precedence order; adjudication follows the
   manual's rules plus verified revoked-sponsor/embargo/staleness policy.
2. **Applicant-gated RapidOCR.** Full-page RapidOCR recovery runs only when
   the primary `applicant_name` is unresolved — a label-blind visible-damage
   signal. (Universal Rapid was measured at 7.5–9.8 s/PDF: rejected.)
3. **Frozen visible finalizer.** Conservative field repairs and layout, damage,
   stamp, watermark, fee, and terminal-decision guards; approval heads were
   discovered on one hash fold, replicated on a second, and frozen before a
   third. Full-train purpose/page-signature exception tables were excluded as
   non-transferable. A final policy invariant prevents any approval from
   serializing a public disqualifying or mandatory-review risk flag unless a
   later visible signed finding supplies the manual's higher-precedence
   decision.
4. **Selective independent reviewer with monotone terminal votes.**
   Cases still `NEEDS_REVIEW` may be re-read by an independently derived MIT
   pipeline. Selection is label-blind: only packets whose primary row looks
   clean (no risk flags, resolved fee, ≤1 unresolved field) and which have ≤2
   full-page-raster pages — across all 1,000 training packets the excluded
   stratum contains zero true approvals, and the excluded scan-heavy packets
   consume timeout budget without ever producing a vote. Each selected case
   gets 60 seconds (measured sufficient: raising the cap to 90/150 s produced
   no additional votes), under a global budget of 3 seconds per input PDF that
   degrades unprocessed cases to their conservative NEEDS_REVIEW rows. The
   merger permits two narrowly bounded mutations:

   ```text
   NEEDS_REVIEW + independent APPROVED at confidence >= 0.695 -> APPROVED
   NEEDS_REVIEW + independent DENIED + shared public-manual cause -> DENIED
   ```

   The denial route has no learned threshold: both readers must serialize the
   same causal `TRANSIT-7`, public revoked sponsor, unpaid fee, or public
   disqualifying risk token. Inferred sponsor IDs, learned-only denials,
   reviews, low-confidence approvals, and failures abstain. Reviewer fields are
   always discarded and primary terminal decisions are never reopened.
5. **Explicit adjudicator finding.** A bounded post-vote pass applies a
   decision only from a unique, conflict-free visible `Finding:` line. Text
   findings are handled without extra OCR; raster findings use the existing
   note reader only on current approvals/reviews. Extracted fields never
   change.
6. **Post-ensemble confidence calibration.** A frozen identity-free ensemble
   is serialized as plain JSON and runs after the final decision. It changes
   confidence only; it cannot mutate fields or adjudication.
7. **Missing-row fallback.** A provenance-aware backup engine emits a
   schema-valid conservative row for any case the primary omits. Every input
   yields exactly one valid row.

## Why the vote gate is 0.695

We measured the reviewer's approval votes against truth across three
independent full-pool runs and two shard experiments. The reviewer serializes
confidence to three decimal places; accepting the complete 0.695 bin adds
three true training approvals and no denial/review promotions. The next lower
bin contains a false approval, so it remains an abstention. The one remaining
catastrophic false approval in the confusion matrix is a packet with no visible
denial evidence in any channel, not a reviewer-vote pattern.

On validation, the 0.695 threshold changes 10 decisions relative to the earlier
0.70 file. Across all refreshed channels, 69 of 5,000 categorizations change
with zero extracted-field changes.

The public-causal denial guard adds one exact-train correction and changes one
of 5,000 validation decisions. It was specified from the public manual and
cross-reader evidence agreement rather than selected by a confidence sweep.
Because its only possible transition is `NEEDS_REVIEW -> DENIED`, it cannot add
a catastrophic false approval. The merge measured 0.12 seconds for all 5,000
rows (0.000024 seconds/PDF).

The final serialized-risk consistency guard adds one further exact-train
correction, taking the development replay from 135.1858 to 135.2622. It changes
four of 5,000 validation decisions, all away from approval, and changes no
fields. It is a direct public-policy invariant over the already-produced row:
no label, fitted threshold, case ID, PDF signature, model call, or additional
OCR participates. This incremental rule cannot add a catastrophic false
approval. The full 135.2622 headline still includes the pre-existing full-fit
confidence calibrator and is not an unbiased private-test estimate.

## Measurement discipline

- Hash-fold splits with an untouched fold for single reads; every lever
  reported DEV vs held evidence before adoption.
- Spike-before-scale: each idea was proven or killed on a bounded sample
  before any full run.
- Measured-dead levers (kept dead with their killing measurements): reviewer
  field-union, broad or learned deny votes at any threshold, unconstrained
  both-engines-agree consensus
  (agreement anti-selects on this generator — packets with destroyed denial
  evidence fool both engines together), timeout arbitration of low-confidence
  denials, answer-key transcription, cross-field imputation, and post-hoc
  signature/calibration retunes whose held-fold support was absent.
- All scores quoted from saved receipts under
  `artifacts/` (exact-1,000 evaluation, cap-curve timings, end-to-end runs).

## Known failure modes and caveats

- **Evidence-absent packets.** Most residual errors are packets whose decisive
  fields are physically destroyed or absent; we return NEEDS_REVIEW at low
  confidence rather than guess. Aggressive statistical conversion of that
  stratum was measured to create false approvals and was rejected.
- **Reviewer timing nondeterminism.** The reviewer's per-case watchdog makes
  its vote set mildly load-sensitive: identical inputs produced 36 vs 45
  raw votes across two runs. The 0.695 gate uses a complete serialized bin
  that was stable across such perturbations, but re-runs may shift the final
  score by a few tenths of a point.
- **Severe scan damage** can destroy any individual field; cross-page
  redundancy recovers many instances, but exact extraction credit is lost when
  no legible instance exists.
- **OCR engine versions** (Tesseract 5.3/5.5) produce occasional borderline
  field differences across platforms; decisions were verified stable on a
  parity batch.

## Compliance

Offline (`--network none`), CPU-only, read-only root, writable `/tmp` only;
the retained image is 687 MB (cap 4 GiB); model artifacts remain far below the
250 MB/1 GB caps; one valid JSONL row per input; **18/18 focused decision-guard
tests and 129/131 full-image tests pass**. The two existing image-sensitive
failures are the synthetic 90-degree raster read and crossed-out-stamp
heuristic; neither is on the changed path. Vendored MIT/Apache components and
model provenance are documented in
`THIRD_PARTY_NOTICES.md` and under `vendor/`; the selection, gating, budget,
and merge logic described above is original work in this repository.

## With another week

We would attack the evidence-absent stratum at its source: a trained
page-restoration/denoising pass for faint verdict stamps (precision-gated in
the deny direction only), a learned per-field legibility model to sharpen
confidence on destroyed packets, and a second reviewer pass under the unused
runtime headroom with vote-union across timing perturbations. We would also
harden the reviewer against its timing nondeterminism by replacing the
wall-clock watchdog with a work-unit budget, making votes fully reproducible.
