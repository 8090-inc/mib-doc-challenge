# MIB Doc Challenge — technical memo

**Solution repo:** see `SUBMISSION.md` · **Approach:** offline OCR + classical CV + a hand-written rules cascade. No LLM, no VLM, no cloud API, no network at runtime.

**Where it scores (train, frozen 700/300 split, seed 8090):** dev **128.24 / 150** — classification 66.17 / 80, extraction 45.21 / 50, calibration 16.86 / 20, **0 catastrophic false approvals**, 0 missing rows. Holdout, read sparingly so it retains meaning — and never to justify a change being rejected: **128.28**, with the holdout-over-dev gap stable across reads. Runtime, measured on the full 5,000-case validation set under the exact contract limits: **4.62 s/PDF, 23,086 s against the 30,000 s cap**, in one uninterrupted run with zero cases hitting the per-case OCR budget. That is 1.30× headroom, and the contract fixes the vCPU count but never the vCPU speed — see `SUBMISSION.md`.

---

## 1. Approach

The pipeline is five staged transforms with an explicit record type at every seam (`mib/records.py`), orchestrated by `mib/runner.py`:

**S1 extract** — PyMuPDF text and layout. Hidden spans (white-on-white, off-crop, zero-size) are separated at this boundary and never rejoin the evidence path. This is the single most important structural decision in the repo: the adversarial content cannot be filtered later if it was never labelled as hidden in the first place.

**S2 render + OCR** — scan-only pages go through a *composition grid*: `source → orientation → deskew → deshred/local → optical`, with the detectors re-run in-frame rather than once up front. Every composition is OCR'd and **every reading crosses the seam** — the ensemble is not collapsed to a winner at S2. Roughly 47 reads per case. One gated PSM-3 layout pass fires on a page whose field label is present but whose value truncated (the large-graphic-box class that defeats PSM-11's sparse-text grouping).

**S3 parse** — label/value extraction against a closed vocabulary, with a confusion-weighted edit distance plus a runner-up margin guard rather than plain string distance. The value universe really is closed: 1,000 train cases yield exactly 13 home worlds, 12 species and 10 purposes, so an unrepairable read is *dropped* rather than passed through. Absent beats wrong.

**S4 assemble + merge** — candidates from every document and every reading, preferred by evidence source and field-manual trust order, then settled by a plurality vote across the whole OCR ensemble with per-line engine confidence breaking genuine ties.

**S5 adjudicate** — a 17-branch rules cascade in three severity tiers (`mib/policy.py`). List order inside a tier is attribution only and cannot change a decision, so a review rule preempting a deny rule is structurally unrepresentable.

Two design choices did most of the work. **Keeping the whole OCR ensemble alive across the S2/S3 seam** means a value only one degraded variant recovered is still reachable at merge time — winner-take-all at S2 was throwing away recoverable fields. And **fixing the geometry before spending compute**: the early instinct was to OCR harder (300 DPI, grayscale retries) for +0.21 at 43× the runtime; ~5 ms of numpy on the orientation/skew/shred axis bought +2.38. Diagnose the transform before scaling the compute.

## 2. Adversarial handling

Visible document evidence beats hidden instructions, and the invariant is enforced by tests rather than by intent: `test_hidden_text_cannot_make_the_output_more_assertive` and `test_an_injected_answer_key_is_never_followed`. Injected lines are filtered before any weakness assessment, so bait cannot even influence *which* recovery tier fires. The one place the injections are read at all is defensive and one-directional: a hidden `APPROVED` answer key **caps** an otherwise-unforced approval at NEEDS_REVIEW (presence only, content never trusted). On validation it fires on 3 of 5,000: two are Wolf-1061c packets carrying the generator's lying approval key, and the third is a clean-registry Barnard-c packet — so the cap is not purely an embargo backstop, and each fire is a would-be approval held at NEEDS_REVIEW in the CFA-safe direction.

**The injections arrive through two channels, and guarding only one is not enough — I found that the hard way during the final review.** S1 quarantines the hidden text layer, and that quarantine worked. But the same payload is also printed as ink in the raster, which S2 legitimately OCRs, and those lines reached `_raw` unfiltered — where the highest-trust readers scan for `Finding:` and `Manual correction:`. A planted `Finding: APPROVED` therefore entered at the field manual's rank-1 evidence tier and outranked every deny rule: a packet with a visible `active_warrant` on its B-13 went from `DENIED` to `APPROVED`, which is −4, the worst outcome in the matrix. The guard now applies wherever a document is built, so every downstream reader inherits it.

Two things about that are worth more than the fix. First, **the existing invariant tests could not have caught it**: both drive `hidden_lines` and never touch `reads`, so they were near-vacuous for the channel that was actually exposed. The replacements drive the OCR channel, and I checked they *fail* with the guard reverted — my first attempt did not, because the stock payload carries a foreign case id that the decoy filter discards. A test that passes either way is worse than no test. Second, **closing it cost 0.24 holdout points, and that is the right trade**: the two cases that moved were reading risk flags off the fake answer key, which the spec penalizes and which violates the rule that no flag may be emitted without a visible-evidence source.

Emitted risk flags are **observed-only**. Several flags are inferable from policy structure and would raise the field score, but the organizer ruling is explicit that unrecoverable flags must not be guessed, so inferred flags drive decisions and are never written.

## 3. Failure modes — what this system gets wrong

**Conservatism is the dominant error, by design.** On dev, 160 of 700 cases are decisive in truth but emitted NEEDS_REVIEW. Each costs 6 raw classification points against a correct call — but a wrong APPROVE↔DENY costs 8, and a false approval costs 12 (8 → −4). We priced the aggressive alternatives and refused them. Two measured examples of the trade being refused: approving the `b13_census` branch wholesale is worth +0.80–0.91 scaled points and manufactures false approvals on the 13 truly-denied cases sitting in that branch; and inside the same pool, blanket-approving the DIP-1 slice is worth about +62 *raw* points for 3 catastrophic false approvals. Both are forbidden trades at this scoring matrix, and that shape is most of the "headroom" a naive optimizer would find here.

**The under-determined cases are not extraction failures.** `fee_unknown` and `b13_census` are largely the organizer's intended NEEDS_REVIEW shape: the packet genuinely lacks the evidence. Chasing those labels manufactures false-approval risk elsewhere.

**The one uncovered false-approval route is a private-set-only embargo world.** Approvals come only from zero-predicate cases and signed adjudicator findings, so a home world we have never seen sails to `clean_approve`. No structural detector is possible — worlds are a closed recurring set of 13 with no bimodal recurrence signature of the kind that lets `mib/corpus.py` recover unseen revoked sponsors label-free. The exposure is bounded: on dev, 29 of 34 full-embargo cases are caught redundantly by an observed `planetary_embargo` flag or a signed finding, leaving 5 that rest on the world list alone. The residual ~15% is irreducible with the evidence available.

**Calibration is fitted to this corpus's damage rate.** The ignorance branches (0.26–0.50) are functions of how damaged the scans are, and the damage rate roughly halves on validation. On a cleaner private corpus those confidences will under-claim and cost Brier.

## 4. What I would do with more time

**The mixed-page channel.** The largest identified-but-unclosed gap: packets whose pages come from different sources, where the ink S2 never reads carries the deciding evidence. This was located by proving a hypothesis *wrong* — 13 name conflicts looked like planted decoy documents, and a falsification probe showed the "decoy" forms are truthful on every other field, so the poisoning is field-grain, not document-grain. That killed a document-demotion rule before it shipped and pointed at the real channel.

**Harden the values that disarm rules, not the ones that are merely wrong.** `DIP-1` alone disarms five branches, so a wrong one can carry a case that should deny. The obvious guard — demand corroboration before an OCR-sourced `DIP-1` disarms anything — measured **−14 raw points** and does not ship: the bad `DIP-1`s are not misreads (the scanner reads `Visa Class: DIP-1` verbatim four to eight times) but *document conflicts*. Only the narrow rival-visa rule shipped. The general lesson is that leverage, not error rate, is where guards belong, and the same audit is owed to the other values that disarm branches.

**A 288-DPI recipe.** The one untested branch of the render-resolution search: `288 × equalize` topped an offline set-cover but is absent from the {144, 200} dump, so it was never priced.

**Better evidence for the confidence layer.** Not more model capacity — that road is closed with evidence (seven model families, ranking by regularization strength rather than capacity, which is an information limit, not a hypothesis-class one). A learned decider beat the rules by +1.16 when the rules were weaker, then *inverted* to −0.50 with 14 false approvals once the cascade improved: it was a residual-corrector with no residual left to correct.

## 5. On the ceiling

Four independent lines of evidence say this score is near a real, generalizing ceiling rather than a tuning plateau. Read-creation reachability is airtight — expanding the read set with PSM 3/4/6, native high-DPI rendering and field crops recovered ~0 of 35 dev misses. Selection headroom is mostly already banked. The one remaining merge "improvement" was falsified on diagnosis rather than assumed. And the holdout confirms the gains generalized roughly 1:1, with no dev/holdout divergence.

The honest summary is that further points need *new evidence*, not more fitting — which is why the last week of work went into removal, verification and provenance rather than into another rule.

---

*Method note: every change in this repo is one scored row in `docs/experiments.md` — including the rejections, which are the more useful half and are kept deliberately. Changes that could move behavior are gated on a byte-identical replay against a cached substrate, not on the test suite alone. 138 tests. `docs/STATUS.md` is the front page.*
