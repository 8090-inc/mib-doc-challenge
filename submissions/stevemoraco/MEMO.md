# Technical Memo — stevemoraco

## Approach

The solution is a fully deterministic, offline document pipeline — no LLMs, VLMs, or network access at runtime — built in three layers:

**1. Trust-aware extraction.** Each PDF's content streams are decoded directly (text operators with exact fill colour and position), and every text run is classified before it may be used: ordinary visible text, hidden text (near-background colour), and text positioned outside the page's visible area are tracked separately. Pages whose text layer is absent or content-free fall back to OCR (Tesseract), with orientation chosen by OCR yield rather than metadata, because page-rotation flags in this corpus are unreliable. Extraction is deliberately shape-tolerant: labels arrive truncated or clipped, so field anchors match by pattern shape anywhere in a line rather than by anchored literals.

**2. Adversarial-content quarantine.** Everything inside a document is treated as data, never as instruction. Injected "answer key" rows, barcode caption payloads, decoy stamps and watermarks, and page-scope disclaimers that attempt to suppress neighbouring evidence are detected and quarantined: they may be *reported* (e.g., as an extraction observation) but are structurally barred from ever satisfying an approval precondition. Struck-through values with corroborated handwritten corrections resolve to the correction; struck values with no replacement resolve to `unknown` rather than either candidate.

**3. A distilled rule engine with provenance gates.** Adjudication is a hand-built rule table distilled offline from the 1,000 labeled training cases, applied to extracted fields plus per-field source signals. Deny-bearing rules (embargo worlds, revoked sponsors, disqualifying risk flags, fee state) fire only on trusted evidence; approval additionally requires that no deny-bearing field rests on quarantined or placeholder values — an unresolved sponsor, for example, routes to review rather than approval. Sponsor revocation is corroborated two ways: stated evidence in the documents and a corpus-level frequency check computed over the full input set at runtime (never a hardcoded list). Per-row confidence is calibrated from measured per-rule accuracy on held-out data.

## Measured performance

All numbers are from a blind 200-case holdout (20% stratified split, fixed seed, scored with the challenge's own `evaluate.py`; the holdout was excluded from rule fitting and threshold tuning):

- Internal rule-engine harness (canonical split): **120.69 / 150** — extraction 43.01/50, classification 61.70/80, calibration 15.98/20, **0 catastrophic false approvals** (1/431 truth-DENIED on the full training split).
- Packaged container, end-to-end on the same blind holdout via the exact Docker entrypoint: **113.55 / 150** — extraction 39.49/50, classification 59.25/80, calibration 14.80/20, **0 catastrophic false approvals**. (During final verification we isolated and repaired an extraction-trust regression — a pixel-based hidden-text classifier was discarding legitimate field values on image-backed pages; the fix routes page-body trust through content-shape stripping instead, which also hardened the pipeline's injection handling.)
- These predictions: 5,000/5,000 schema-valid rows over the validation manifest, 0 missing, 0 inference failures (adjudication mix: 411 APPROVED / 1,545 DENIED / 3,044 NEEDS_REVIEW). Sponsor-revocation statistics computed over the validation input set at runtime resolved a clean bimodal frequency gap (5.75×), consistent with the training corpus structure.

## Failure modes

Residual error is dominated by perception, not judgement: a majority of pages in this corpus are scanned images with heavy synthetic damage, and the highest-value evidence (adjudicator findings, risk-flag sources, fee receipts) is often only present there. Where that evidence is unreadable the pipeline hedges to NEEDS_REVIEW by design, which caps classification score but protects the false-approval record. Extraction emits explicit unknown-sentinels rather than guesses when no evidence is found, which costs extraction points on degraded packets.

## With another week

Priorities, in order: (1) selective OCR routing that spends aggressive multi-pass OCR only on pages proven text-free, with damage-aware preprocessing; (2) recovery of adjudicator finding sentences from degraded note pages, which are near-ground-truth where readable; (3) risk-flag derivation from note prose and cross-document structure for the majority of packets that never print a flag source; (4) distilling additional tie-break rules from disagreement analysis against stronger reference judgements, encoded as explicit offline rules.
