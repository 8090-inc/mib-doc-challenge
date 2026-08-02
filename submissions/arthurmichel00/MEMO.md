# MIB Doc Challenge — Technical Memo

**GitHub:** arthurmichel00 · **Solution repo:** `https://github.com/arthurmichel00/mib-doc-solution` (MIT; PyMuPDF is AGPL-3.0 — see THIRD_PARTY_NOTICES.md)
**Runtime:** Tesseract + a bundled RapidOCR PP-OCRv6 ONNX fallback + a measured preprocessing escalation + OpenCV + deterministic rules. No LLMs/VLMs, no network, no per-case hardcoding.
**Process:** Built by AI agents in autonomous loops: every lever flag-gated and A/B-measured against gates evaluated in code (score, holdout ≥ train, single designed-trap CFA, red-team). Agents proceeded on green unattended; humans made exactly three kinds of call — goals, trust boundaries, ship decisions. Receipts: LEVERS.md and APPENDIX.md in the solution repo.

## Results

- **Official train: 128.79 / 150**, the full Docker scoring contract over all 1,000 cases.
- **Held-out 200: 130.25 / 150**, holdout ≥ train at all 8 milestones (back-scored across the build history, the arc runs 113.19 → 130.25).
- **Catastrophic false approvals: 1**, the documented designed trap MIB-000865.
- **0 fallback rows**; every recovered adjudicator note adjudicates correctly (343/343; the one prior mis-bind is fixed — see Failure modes).
- **5,000 / 5,000 validation rows**, written by the frozen image, validated against the manifest.
- **5.64 s/PDF against the 6.0 s budget, 0.36 GiB image** (gated docker_check under ambient load; the pre-guard image measured 5.52 quiet — the guard adds no OCR work).

## Why this number and not a bigger one

The challenge deliberately makes ~5–7% of cases under-determined: silent disqualifying flags with no readable evidence, whose train labels say DENIED. The organizers confirmed in issues #4/#5 that NEEDS_REVIEW is the correct output there and that systems "should not guess" a verdict. We never do: absent evidence never feeds adjudication. (Unreadable *field text* is a different, extraction-only matter — see Disclosures.) Beating ~132 on train takes one of two things: surrendering that bucket to train-label expected value, or transcribing the hidden answer key. The key is organizer-confirmed poison, its adjudication wrong in 216/216 train carriers. Both routes inflate the public number, collapse on private labels, and carry disqualification risk. We stopped at the honest maximum and optimized for the private test. The holdout trajectory is the proof.

## How this was built — the operating model

One human directed this: I set the goals, drew the trust boundaries, and made the ship calls; gated agent loops did everything else. Verification was machinery, not meetings. Every lever was built behind a feature flag and A/B-measured on the full train set. The gates were evaluated *in code*: score ≥ baseline, holdout ≥ train, single designed-trap CFA, zero fallback rows, red-team green. Agents proceeded on green and killed on red without waiting for me, in unattended overnight stretches of 8–12 hours. Dead ends went to an append-only ledger with their evidence, so later loops never re-litigated them. More than thirty levers were measured this way; ten survived every gate to ship enabled. The build took under two weeks of calendar time, most of it in those overnight runs. A funnel of 30+ built and 10 shipped is portfolio management, not indecision.

## Approach

The pipeline is built around one idea: decide the trust boundary before reading anything.

1. **Redact-then-render.** Hidden spans (render-mode-3, opacity-0, sub-6pt, near-white fill, off-cropbox) are classified from the PDF appearance stream and redacted *before* rasterization. No contrast step can then resurrect a white-on-white injection. Non-footer text-layer content on scan pages is untrusted by construction, and the hidden "answer key" is never read as evidence.
2. **OCR ensemble, adopted by measurement.** Scans render at 288 DPI into a pooled Tesseract ladder (binarization, deskew, orientation retries) that pools passes per line by confidence. A bundled RapidOCR PP-OCRv6 ONNX fallback fires only when a decision-relevant field is still unread (v6 measured +0.81 and shipped; v5 was a wash at +0.07). A final preprocessing escalation may only fill unread fields, never out-vote a read one.
3. **Extraction.** Label-anchored parsing, closed-vocabulary weighted-Levenshtein correction, and precedence-weighted cross-page reconciliation where an exact digital line beats any OCR vote-sum (with a decoy-aware guard for names). Trusted note Reason lines are mined for field values, each template verified 100% against gold. A deterministic truth table resolves fee status across all 449 digital receipts.
4. **Adjudication.** A deterministic policy engine with **positive-evidence gates**. Deny rules fire only on affirmative reads; APPROVED requires flags, visa, world, sponsor (unless DIP-1), fee, and arrival to each be read affirmatively. Absent evidence is never clean evidence.
5. **Decision + calibration.** A per-path posterior feeds an expected-value argmax under the scorer's 8/−4/2/1 payoff. Confidence is each path's empirical accuracy with shrinkage (m=10), fit out-of-fold (seed-8090 800/200) and refit at freeze from in-container OCR. Clamped [0.05, 0.97].

An internal red-team broke the trusted Finding line four ways; all four are closed, and the attack corpus re-runs green after every pipeline change.

## Failure modes

- **One accepted catastrophic false approval, MIB-000865.** The scanned intake *visibly* prints "Visa Class: XW-2"; the truth is TRANSIT-7 (DENIED), and nothing in the packet contradicts it. The pixels lie by design. Guarding would mean distrusting every single-source scan read, converting ~45 legitimate approvals into reviews to save one −4. We took the loss and documented it.
- **One misread note, MIB-000497 — found post-freeze, fixed in this build.** A legible note reads "Finding: NEEDS_REVIEW"; damage truncates the line, and under the image's Tesseract 5.3 the fuzzy matcher mis-bound the fragment to DENIED. The fix is a truncation-ambiguity guard (the winner must also win a junk-stripped label-zone re-scoring, else the matcher abstains); it was shipped only after the full battery — suite, red-team, trap corpus, and a 23,066-line matcher sweep with exactly two changed lines, both verified benign — and it changes zero verdicts on the 5,000 validation cases.

## What I would improve with another week

The next week's agenda is already evidenced — each item below has a measurement behind it, and ships when it earns its gates:

- **Make the note-rescue channel version-portable:** a measured one-line padding fix (the image's Tesseract clips glyphs at the crop edge, truncating the Reason sentence ~22 points below the template bar). The channel is currently redundant in-container — the ordinary ladder already reads the known case — so the pad is private-set insurance that ships only behind its own A/B.
- **Constrained-menu field matching:** corpus-swept behind a prefix-fit confidence gate — 92% gated precision, zero fires on 26 decoy rows, but net yield measured at ~+0.12 points against the runtime budget's last 0.2 s/PDF; parked with its measurements until the locator reuses the pipeline's existing OCR geometry.
- **Harden fragment reassembly's detector** to pass its own safety gate. The general solver is already built (its narrow two-fragment case shipped as the strip-weld) and recovers gold values on audit pages; what keeps it out of production is the damage detector false-firing on two thirds of clean pages — precision work, not research.
- **Grow the red-team corpus** past the injection mechanisms observed in train (it grew 4 → 10 attacks during this build); crack **MIB-000538's undocumented second deny pattern** (unsolved field-wide); build the honest-nulls output mode.

And one thing I would *not* retry: sponsor-digit shape recovery on degraded scans — measured at chance (rank 52/200; every SPN-#### shares glyph geometry) and ledgered so no future loop re-litigates it.

## Disclosures

- **Extraction-only imputation + emission-time consistency guard.** Unreadable fields print corpus-mode fallbacks for schema completeness — the scorer treats wrong and blank identically, so the mode is free expected value — and these imputed values are quarantined: the decision layer never reads them. Where a trusted note decides a case, a contradicting low-trust read is replaced from that note's entailed set.
- **Prior-art overlap.** The fee geometry, the render-first trust boundary, and the name syllable grammar circulate in public MIT-licensed solutions; we re-derived and extended each independently.
- **Learned entity lists.** Our rule miner mined the policy table from train labels (1000/1000 given true fields). The revoked-sponsor list is 3 documented IDs plus 3 mined from train recurrence.
- **No per-case logic.** Case ids appear in comments as evidence citations only: no id-keyed lookups, no allowlists, no per-case edits, and a grep for case-id comparisons comes back empty.
- **Dev-time VLM cross-check, diagnostic only.** GPT and Gemini read rendered pages during development to locate our OCR failures. No VLM output entered predictions; the runtime is offline.
- **Third-party components.** RapidOCR, the bundled PP-OCR ONNX models, onnxruntime, and Tesseract are Apache-2.0; PyMuPDF is AGPL-3.0 and governs the combined work; our code is MIT.

Evidence, measurements, and the full build ledger: [APPENDIX.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/APPENDIX.md) and [LEVERS.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/LEVERS.md) in the solution repo.
