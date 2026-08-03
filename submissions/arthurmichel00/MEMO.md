# MIB Doc Challenge — Technical Memo

**GitHub:** arthurmichel00 · **Solution repo:** `https://github.com/arthurmichel00/mib-doc-solution` (MIT; PyMuPDF is AGPL-3.0 — see THIRD_PARTY_NOTICES.md)
**Runtime:** Tesseract + a bundled RapidOCR PP-OCRv6 ONNX fallback + a measured preprocessing escalation + OpenCV + deterministic rules. No LLMs/VLMs, no network, no per-case hardcoding.
**Process:** Built by AI agents in autonomous loops: every lever flag-gated and A/B-measured against gates evaluated in code. Humans made three kinds of call — goals, trust boundaries, ship decisions. Receipts: LEVERS.md and APPENDIX.md in the solution repo.

## Results

- **Official train: 129.05 / 150** on the full Docker scoring contract over all 1,000 cases — extraction 45.42 / 50, classification 66.67 / 80, calibration 16.96 / 20 at Brier 0.0760.
- **Held-out 200: 130.50 / 150** (Brier 0.0712), holdout ≥ train at all 9 milestones; back-scored, the arc runs 113.19 → 130.50.
- **Catastrophic false approvals: 1**, the documented designed trap MIB-000865.
- **0 fallback rows**; every recovered adjudicator note adjudicates correctly (343/343; the one prior mis-bind is fixed — see Failure modes).
- **5,000 / 5,000 validation rows**, written by the frozen image, validated against the manifest.
- **5.81 s/PDF on a quiet box against the 6.0 budget, 0.36 GiB image.** The previous build measured 5.64: the added candidate-scoring pass costs ~0.3 s on each of the ~20% of cases that trigger it, breaching our own 5.6 target. We ship the points and disclose the cost.

## Why this number and not a bigger one

The challenge deliberately makes ~5–7% of cases under-determined: silent disqualifying flags with no readable evidence, whose train labels say DENIED. The organizers confirmed in issues #4/#5 that NEEDS_REVIEW is the correct output there and that systems "should not guess." We never do: absent evidence never feeds adjudication (unreadable *field text* is a different, extraction-only matter — see Disclosures). Beating ~132 on train takes surrendering that bucket to train-label expected value, or transcribing the hidden answer key — organizer-confirmed poison, its adjudication wrong in 216/216 carriers. Both inflate the public number, collapse on private labels, and carry disqualification risk. We stopped at the honest maximum and optimized for the private test; the holdout trajectory is the proof.

## How this was built — the operating model

One human directed this: I set the goals, drew the trust boundaries, and made the ship calls; gated agent loops did everything else. Verification was machinery, not meetings. Every lever was built behind a feature flag and A/B-measured on the full train set against gates evaluated *in code*: score ≥ baseline, holdout ≥ train, single designed-trap CFA, zero fallback rows, red-team green. Agents proceeded on green and killed on red unattended, in overnight stretches of 8–12 hours, and dead ends went to an append-only ledger with their evidence so later loops never re-litigated them. More than thirty levers were measured this way; fourteen survived every gate to ship enabled.

## Approach

The pipeline is built around one idea: decide the trust boundary before reading anything.

1. **Redact-then-render.** Hidden spans (render-mode-3, opacity-0, sub-6pt, near-white fill, off-cropbox) are classified from the PDF appearance stream and redacted *before* rasterization, so no contrast step can resurrect a white-on-white injection. Non-footer text-layer content on scan pages is untrusted by construction; the hidden "answer key" is never read.
2. **OCR ensemble, adopted by measurement.** Scans render at 288 DPI into a pooled Tesseract ladder (binarization, deskew, orientation retries) pooling passes per line by confidence. A bundled RapidOCR PP-OCRv6 ONNX fallback fires only when a decision-relevant field is still unread (v6 measured +0.81 and shipped; v5 was a wash at +0.07). A final preprocessing escalation may only fill unread fields, never out-vote a read one. Behind it, for the four closed-menu fields only, a constrained-candidate channel scores every legal value against the recognizer's frame posteriors with the exact CTC forward algorithm instead of decoding its argmax — a mechanism from a MIT-licensed public solution, re-gated on our data and attributed in ATTRIBUTION.md.
3. **Extraction.** Label-anchored parsing, closed-vocabulary weighted-Levenshtein correction (with fusion/ligature edit costs and a licensed truncation-prefix rule for clipped rows), and precedence-weighted cross-page reconciliation where an exact digital line beats any OCR vote-sum, with a decoy-aware guard for names. Trusted note Reason lines are mined for field values, each template 100% gold-verified. A deterministic truth table resolves fee status across all 449 digital receipts.
4. **Adjudication.** A deterministic policy engine with **positive-evidence gates**. Deny rules fire only on affirmative reads; APPROVED requires flags, visa, world, sponsor (unless DIP-1), fee, and arrival each read affirmatively. Absent evidence is never clean evidence.
5. **Decision + calibration.** A per-path posterior feeds an expected-value argmax under the scorer's 8/−4/2/1 payoff. Confidence is each path's empirical accuracy with shrinkage (m=10), fit out-of-fold (seed-8090 800/200) and refit at freeze from in-container OCR.

An internal red-team broke the trusted Finding line four ways; all four are closed, and the attack corpus re-runs green after every change.

## Failure modes

- **One accepted catastrophic false approval, MIB-000865.** The scanned intake *visibly* prints "Visa Class: XW-2"; the truth is TRANSIT-7 (DENIED), and nothing in the packet contradicts it. The pixels lie by design. Guarding would mean distrusting every single-source scan read, converting ~45 legitimate approvals into reviews to save one −4. We took the loss.
- **One misread note, MIB-000497 — found post-freeze, fixed in this build.** A legible note reads "Finding: NEEDS_REVIEW"; damage truncates the line, and under the image's Tesseract 5.3 the fuzzy matcher mis-bound the fragment to DENIED. The fix is a truncation-ambiguity guard: the winner must also win a junk-stripped label-zone re-scoring, else the matcher abstains. It shipped after the full battery, including a 23,066-line matcher sweep with two changed lines, both benign.
- **Three over-emitted risk flags** (MIB-000111/000376/000452), this build's cost for the clipped-flag repair: each adds one flag token gold does not carry, on cases already denied by other flags. The same repair bought two correct NEEDS_REVIEW → DENIED adjudications. Full flip audit in LEVERS.md.

## What I would improve with another week

Each item below already has a measurement behind it, and ships when it earns its gates:

- **Keep pushing the reading channel.** Constrained-candidate CTC scoring shipped in this build behind a precision gate; it and three text-level decode repairs measured +0.26 train / +0.25 holdout together, at the cost disclosed above. Next two in the same direction: the unresampled native-raster pass, and the slice-shift fragment repair whose frame-anchored gating our code audit validated as the answer to the safety objection that keeps general realignment out.
- **Make the note-rescue channel version-portable:** a measured one-line padding fix for the image's Tesseract clipping glyphs at the crop edge. Built, in the tree, default-off — the channel is redundant in-container, so the pad is private-set insurance that ships behind its own A/B.
- **Grow the red-team corpus** past the injection mechanisms observed in train (4 → 10 attacks during this build); crack **MIB-000538's undocumented second deny pattern** (unsolved field-wide); build the honest-nulls output mode.

Two I would not retry, both ledgered: sponsor-digit shape recovery on degraded scans, measured at chance (every SPN-#### shares glyph geometry), and vocabulary-constrained OCR user-words, net-negative at −0.22 and left dead in the tree.

## Disclosures

- **Extraction-only imputation + emission-time consistency guard.** Unreadable fields print corpus-mode fallbacks for schema completeness — the scorer treats wrong and blank identically — and those values are quarantined from the decision layer, as are constrained-candidate fills, capped below the affirmative-read threshold so no policy rule can consume one. Where a trusted note decides a case, a contradicting low-trust read is replaced from that note's entailed set.
- **Prior-art overlap.** The fee geometry, the render-first trust boundary, the name syllable grammar, and the CTC candidate-scoring and fusion-cost mechanisms above circulate in public MIT-licensed solutions; we re-derived, re-gated, and extended each, with per-mechanism credit in ATTRIBUTION.md.
- **Learned entity lists, no per-case logic.** Our rule miner mined the policy table from train labels (1000/1000 given true fields); the revoked-sponsor list is 3 documented IDs plus 3 mined from train recurrence. Case ids appear only as evidence citations in comments — no id-keyed lookups, no allowlists, and a grep for case-id comparisons comes back empty.
- **Dev-time VLM cross-check, diagnostic only.** GPT and Gemini read rendered pages during development to locate our OCR failures. No VLM output entered predictions; the runtime is offline.
- **Third-party components.** RapidOCR, the bundled PP-OCR ONNX models, onnxruntime, and Tesseract are Apache-2.0; PyMuPDF is AGPL-3.0 and governs the combined work; our code is MIT.

Evidence, measurements, and the full build ledger: [APPENDIX.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/APPENDIX.md) and [LEVERS.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/LEVERS.md) in the solution repo.
