# Technical Memo — MIB Doc Challenge

**Muhammad Balawal (`muhammadbalawal`)** · Solution: <https://github.com/muhammadbalawal/mib-doc-solution>

**Training score, official `evaluate.py`, reproduced end-to-end by the shipped runtime on a 4-vCPU Linux box: 128.79 / 150** — extraction 44.29/50, classification 67.94/80, calibration 16.56/20, 0 missing cases. A late output-only addition (below) adds a measured **+0.08**, so the shipped pipeline sits at **~128.9**. Identical-code runs vary ±0.5 on this corpus; I report the banked figure, not the best draw. Validation: 5,000 predictions, 0 missing, **5.88 s/PDF** offline on 4 vCPU.

## The one claim I would most like reviewed

**No learnable function of the visible evidence beats the hand-written policy out of fold.** I gave gradient boosting and a 400-tree forest all 98 evidence features I could construct — flags, page-kind counts, all 16 stamp buckets, per-field read indicators, one-hot vocabularies, biometric confidence, registry status, waiver/amount, conflict counts — and fitted them directly on the decision under the evaluator's real asymmetric costs:

| | classification /80 |
|---|---:|
| **hand policy (shipped)** | **67.65** |
| GBM, 5-fold out-of-fold | 64.98 |
| GBM + expected-value routing, OOF | 64.32 |
| RandomForest, OOF | 62.80 |
| **GBM in-sample (overfitted)** | **71.42** |
| oracle (evidence determines truth) | 80.00 |

Two things follow. The policy beats machine learning by 2.67 because it encodes `FIELD_MANUAL.md`, which *is* the generating process — a learner must rediscover those rules from 800 examples and cannot. And **71.42 is what memorisation scores**, which is the band the strongest public submissions report (71.9–73.8). My out-of-fold-honest 67.65 sits on the one published out-of-fold column I could find (67.88). Five entrants have now published their own held-out numbers; every one fell, by 4.8 to 15.3 points. I would rather submit a number with nothing left to lose.

## Approach

**Reading.** Digital text per page from the PDF layout; scanned pages go through a Tesseract escalation ladder (sparse mode, deskew, background-division normalisation, Sauvola, slice-shift repair, raw-grayscale washout reads, a fine-tuned Tesseract model, quarter turns), with RapidOCR (ONNX) as a second engine gated to pages the ladder cannot classify. A super-resolution rescue re-reads still-empty closed-vocabulary fields, capped per packet.

**Three levers produced most of the score, and all three are the same bug:** evidence the pipeline had already obtained was being discarded downstream. (1) A degraded page's *classification* often survives when its *values* do not, so classified-but-shredded pages are escalated through the deep ladder rungs — on adjudicator notes this recovers the `Finding:` line, rank-1 evidence that decides its case outright. (2) Extraction is keyed by page *kind*, so a **misdetected** kind silently drops every field the wrong schema does not ask for; a 90°-rotated intake form reads perfectly, then files as a biometric slip because `"Species Code"` fuzzy-matches `"Species Match"` at exactly the 0.72 threshold. Fixed by re-parsing every page's best text under the field-richest schema at lowest precedence, plus a body-label hint (`"Declared Purpose"`: 165/165 intake pages, 0/347 others). Worth **+1.37**. (3) Geometric label→value pairing over Tesseract word boxes, since text-level pairing needs a reconstructed *line* and that is exactly what fails on rotated and table-ruled pages. **+0.08**, output-only.

**Fallbacks are an output-layer decision.** Unreadable fields fall back to a learned prior *after* adjudication, so the policy engine never sees them — the one channel where a better guess cannot cause a worse verdict. Conditioning each fallback on a field actually read (species given visa: 3.9% → 17.6%) was validated 5-fold out-of-fold on a frozen evidence dump, carrying no OCR variance.

**Injection defence.** Hidden text is quarantined at ingestion; adjudication consumes visible evidence only. This mattered: **18.8% of packets embed a hidden "answer record" whose fields are ~93% accurate but whose verdict is inverted — it reads "approved" on 157/157 cases whose truth is DENIED or NEEDS_REVIEW.** Trusting it forfeits the classification section. I measured what declining costs: +2.18 extraction on train. But `EVALUATION.md` removes from a case's maximum any field recoverable "only… in untrusted hidden text", and the public labels omit that column — so on the scored set the channel is worth **zero**, while my own extraction rises to roughly 46.3.

## Failure modes

- **Catastrophic false approvals: 27.** Approvals whose disqualifying flag was never legibly rendered anywhere in the packet. Every separator I could construct fails to isolate them, and every fail-closed gate costs more real approvals than it saves: the permissive path scores 1,063 raw against 640 for punting the same pool. It survives the calibration correction too — charging the Brier penalty, the clean leaf scores APPROVE 8.98 against REVIEW 5.20. A *measured* trade, not an oversight; fail-closed is right for a pipeline whose risk extraction is better than mine.
- **Some evidence is provably absent.** Of 192 risk-flag misses, 129 have the flag in neither text layer; 34 packets contain no biometric slip at all. That is a floor, not a backlog. A recogniser 7.4% better reads 7,170 fields where the shipped pipeline reads 7,168.
- **Stamps are informative and useless.** `green-lg` is 100% APPROVED and `blue-lg` 96% NEEDS_REVIEW — and the policy already decides 100% of both correctly. Every clean signal marks cases already right; every signal with headroom has no purity. A depth-2 miner over 40 predicates including all 16 stamp buckets found **zero** within-leaf splits with positive out-of-fold value.
- **Short-code fields resist recovery.** 864 unique sponsors, 819 singletons — nothing to snap to.

## Process

Every change was A/B-measured on scoring-identical hardware; the dev laptop misled twice (a numpy 2.x crash and thread oversubscription, both Linux-only). Two runs of *identical* code differ on ~25 packets' field values — page classification is perfectly stable, field reads are not — so single-run A/B cannot resolve below roughly ±0.2, and several of my own small negatives are marked *unproven* rather than refuted. Any output- or decision-layer change is therefore measured by re-adjudicating a **frozen evidence dump**: zero OCR variance by construction. Any rule fitted to the labels had to clear 5-fold cross-validation; several in-sample gains were dropped for failing it. Speed work (6.82 → 5.88 s/PDF) was proved output-neutral before shipping: 180/180 pages identical, 198/200 predictions byte-identical, classification and calibration unchanged. Output is written incrementally so a container stopped at the runtime limit still yields a scoreable file. Techniques adopted from public solutions the rules permit (strobl, MIT; thegoleffect) are attributed at the point of use in code.

## With another week

1. **Measure against the scored objective, not the train metric.** Unrecoverable-field exclusion moves my extraction ~44.3 → ~46.3 and moves answer-key pipelines by nothing. My conditional-fallback gain sharpens guesses on never-read fields — precisely the population most likely excluded — so I expect it to be worth ~0 where it counts, while the misclassified-page recovery targets legible fields and should transfer in full.
2. **A new observable, not a new rule.** Two miners over 35 and 65 predicates, all four flip directions, every one out-of-fold negative. The productive version is a demote-only stamp/seal region classifier — the one rank-1 channel the manual names that I currently reduce to a colour bucket.
3. **Candidate generation for names.** 67 of 94 wrong reads are a *different valid name* (the adjacent-applicant decoy), and an oracle re-ranker over recorded candidates is worth only +0.06. The gain must come from generating better candidates, not from ranking the ones I have.
