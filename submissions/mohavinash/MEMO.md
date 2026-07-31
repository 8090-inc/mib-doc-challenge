# MIB Doc Challenge — Technical Memo

## Summary

An offline, CPU-only, visible-evidence ensemble. On the 1,000 labeled training
packets the submitted configuration scores **135.1215 / 150** with **1
catastrophic false approval** (extraction 45.0411, classification 71.4500,
calibration 18.6304, evaluated by the official `evaluate.py`). The retained
exact-contract Docker receipt is **4.46 seconds/PDF** on a representative
100-case run (4 vCPU, no network, read-only root); the measured incremental
raster-note and JSON-calibration stages project the complete refreshed route
at **~5.27 seconds/PDF**, against the 6-second budget. The reviewer stage is
additionally bounded at 3 seconds/PDF *by construction*. The 5,000 refreshed
validation predictions pass the organizer validator with 0 missing case IDs
and carry SHA-256
`61ccaff7a252600a5e9f56a9cf5404b82407e831cf812fabd099aeefe8977dfa`.

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
   non-transferable.
4. **Selective independent reviewer with a confidence-gated approval vote.**
   Cases still `NEEDS_REVIEW` may be re-read by an independently derived MIT
   pipeline. Selection is label-blind: only packets whose primary row looks
   clean (no risk flags, resolved fee, ≤1 unresolved field) and which have ≤2
   full-page-raster pages — across all 1,000 training packets the excluded
   stratum contains zero true approvals, and the excluded scan-heavy packets
   consume timeout budget without ever producing a vote. Each selected case
   gets 60 seconds (measured sufficient: raising the cap to 90/150 s produced
   no additional votes), under a global budget of 3 seconds per input PDF that
   degrades unprocessed cases to their conservative NEEDS_REVIEW rows. The
   merger permits exactly one mutation:

   ```text
   NEEDS_REVIEW + independent APPROVED at confidence >= 0.695 -> APPROVED
   ```

   Denials, reviews, low-confidence votes, and failures are abstentions; the
   reviewer's extracted fields are always discarded; primary denials are never
   reopened.
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

## Measurement discipline

- Hash-fold splits with an untouched fold for single reads; every lever
  reported DEV vs held evidence before adoption.
- Spike-before-scale: each idea was proven or killed on a bounded sample
  before any full run.
- Measured-dead levers (kept dead with their killing measurements): reviewer
  field-union, deny votes at any threshold, both-engines-agree consensus
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
250 MB/1 GB caps; one valid JSONL row per input; **124 unit tests
pass**. Vendored MIT/Apache components and model provenance are documented in
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
