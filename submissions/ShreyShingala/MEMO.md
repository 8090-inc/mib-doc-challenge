# Technical Memo — MIB Doc Challenge

**Shrey Shingala.** Deterministic, fully offline pipeline. No LLM, VLM, cloud OCR or network at
runtime, no hardcoded answers, nothing keyed on case id.

Measured inside the submission image under the published scoring contract on the public
1,000-packet training set.

| Section | Score | Out of |
|---|---:|---:|
| Classification | 70.46 | 80 |
| Extraction | 45.75 | 50 |
| Calibration | 17.44 | 20 |
| **Total** | **133.65** | **150** |

11 catastrophic false approvals, 0 missing cases, 0 invalid records, 2.32 s/PDF against a 6 s
budget. Held-out total (five-fold, refitting the calibration table inside each fold): **133.54**,
so almost none of this is in-sample optimism.

## Approach

**Two passes.** About half the pages carry a clean text layer. Pass 1 reads only those and pulls
out three corpus-level facts no single packet has on its own: the OCR lexicon (species codes, home
worlds, purposes and all 144 applicant-name tokens, learned rather than hardcoded), the staleness
cutoff, and the imputation modes. Pass 2 reads every packet across 4 workers and adjudicates.

The staleness cutoff is worth calling out. The field manual says a packet is stale 180 days before
receipt, but the receipt date isn't printed anywhere. Fresh packets bunch up inside the receipt
window and stale ones trail off in a thin tail going back about a year, so I take the cutoff to be
where the arrival-date distribution goes dense. That reads the parameter off the shape of the data
instead of fitting it to labels.

**I throw hidden text away before anything reads it.** Some packets hide content: white ink on a
white background, text pushed outside the visible page area, fake system prompts. All of it gets
dropped while I'm still parsing the PDF, before any of it reaches the code that makes decisions.
There's nothing downstream to trick.

That turned out to matter a lot, because of what's hidden in there. 843 of the 1,000 packets
contain a planted "answer key", and the field values in those keys are mostly right: 98% correct on
fee status, 95% on sponsor ID. The verdict, though, is wrong every single time. All 843 of them.
And 489 say APPROVE where the real answer is DENY, which is the one mistake that costs -4. The
correct-looking fields are the bait. Trusting the keys scores 118.89 with 77 false approvals.

**Scanned pages** go through RapidOCR (PP-OCRv4 mobile detector, PP-OCRv5 mobile English
recogniser, ONNX Runtime, weights vendored). Word boxes are regrouped into rows and cells and every
value is fuzzy-snapped to a closed vocabulary, so an OCR near-miss turns into a correct value
rather than a wrong one. If a page withholds a field its own document type should carry, that
triggers an escalation ladder I only pay for on the pages that need it: a second view at 260 dpi, a
PP-OCRv6 second engine, a fine-tuned Tesseract LSTM, a contrast-equalised read, a 600 dpi re-read
of just the value row, and vocabulary-anchored recovery when the label is gone.

**Two kinds of damage are just the page being moved around, so I move it back.** Sometimes a strip
of the page is shifted sideways; sometimes a line is cut in half with the top offset from the
bottom. The letters are perfectly intact, which is why OCR fails and a human reads them instantly.
The form has a vertical line down its left edge, so I use it as a reference: work out where it
should be, then slide every row back until it lines up. For the cut lines I try a few split heights
and slide the halves until the ink matches. Repaired cells are read at two zoom levels and only
believed when both agree. Worth about +1.4 points.

**Decisions hedge instead of guessing.** A correct call is +8, hedging to `NEEDS_REVIEW` on
something that was really approve-or-deny is +2, and falsely approving a denied case is −4. So
approving something you should have denied costs 12 points against getting it right. When the
evidence isn't there, the engine routes to review.

**Policy rules are read off the documents, not hardcoded.** Notes say things like "Reason: Revoked
sponsor: SPN-0007", so instead of hardcoding banned sponsors I read the whole input folder and
collect whichever ones the documents name. That finds all six on the training data with no
mistakes, and the score is identical with my hardcoded list deleted — which matters because the
private set will have different IDs.

## Why it isn't a model

The rules forbid LLMs and VLMs at runtime, so that was closed from the start. But separately, every
learned component I tried memorised the public split. A model trained to correct the rules' own
mistakes scored **+4.65 on the data it was trained on and +0.00 on data it hadn't seen**, across 10
models with 20 accept rules each, none of them positive. Learned confidence tables all came in
below the hand-written one, 16.25–16.99 against 17.12. Two OCR recognisers fine-tuned on my
reproduction of the damage came out more careful and less useful, 580 fields right against the
stock model's 591, because the damage I can imagine isn't the damage the generator actually does.

## Failure modes

- **Damaged pages are the real limit.** Of 1,111 wrong fields, only 6 were cases where the right
  value was in my candidates and I ranked it below something else. The gap isn't bad choosing, it's
  that the value never got read.
- **A wrong value is more dangerous than a missing one.** A missing field triggers the hedge; a
  wrong one can clear a case that should have been denied. That asymmetry drives the abstain-first
  design throughout.
- **Some evidence was never printed.** 411 packets have no biometric slip, so their risk flags
  aren't on the paper. I couldn't predict them from anything else in the packet — every attempt
  returned the corpus base rate. The organisers confirmed this is deliberate: in issues #4 and #5
  they state these cases are under-determined, that systems **should not guess** the flag, and that
  `NEEDS_REVIEW` is the correct operational output when missing risk evidence decides the outcome.
  So hedging there isn't my reader falling short, it's the intended answer, and it's what the
  engine does. The scoring is built the same way — unrecoverable fields are dropped from a case's
  extraction maximum on the private set, and over the fields a packet could actually carry I score
  **47.30/50** rather than 45.78.
- **One policy constant may not transfer.** Interdicted worlds are still inferred from labels
  rather than harvested from the documents, unlike revoked sponsors. If the private set interdicts
  different worlds, that rule quietly misses.

## With another week

1. **Localise the value box geometrically, then shape-match it.** The shape matcher already works
   up to blur radius 2.0 and abstains beyond it; it just never gets a chance to fire, since it only
   runs after three other things have failed. The localiser is the piece I ran out of time for.
2. **Run shape matching as a verifier.** Runtime is 2.6x under budget, so check every value a scan
   produces and drop the ones that fail, turning wrong answers into hedges.
3. **Harvest the interdicted-world list at run time**, the way revoked sponsors already are. It's
   the one policy constant still inferred from labels rather than read off the documents.
4. **Widen the measurement instrument first.** The 200-page bench has a standard error of about 6
   fields and the full-corpus one about 22, and several changes I chased moved less than that.

## The whole thing at a glance

```text
                        a folder of PDFs
                               |
                               v
        PASS 1 - read only the pages with a clean text layer
                 (cheap, about half of them)
                               |
                               v
        learn from the whole folder at once:
          - the OCR lexicon: names, home worlds, species, purposes
          - the staleness cutoff: where arrival dates go dense
          - the imputation modes for each field
          - which sponsors the adjudicator notes say are revoked
                               |
                               v
        PASS 2 - every packet, 4 workers in parallel
                               |
                               v
                 for each page: text layer, or scan?
                     |                        |
                text layer                  scan
                     |                        |
                     v                        v
        drop hidden text, white ink,   render at 200 dpi
        anything outside the crop,     RapidOCR: find the words, read them
        fake system prompts            group them back into rows and cells
                     |                        |
                     |                        v
                     |              did a field come out missing?
                     |                        |
                     |                        v
                     |        ESCALATION LADDER - only on those pages
                     |          - second view at 260 dpi
                     |          - PP-OCRv6 as a second engine
                     |          - fine-tuned Tesseract LSTM
                     |          - contrast-equalised read
                     |          - geometry repair: slide shifted strips and
                     |            cut-in-half rows back into place
                     |          - 600 dpi re-read of just the value row
                     |                        |
                     +-----------+------------+
                                 |
                                 v
        snap every value to its closed vocabulary
        (a near-miss becomes the right value, not a wrong one)
                                 |
                                 v
        merge the pages by the field manual's precedence:
        adjudicator note > intake form / receipt > biometric slip
          > sponsor letter > registry extract
                                 |
                                 v
                          ADJUDICATE
             disqualifying flag, revoked sponsor, unpaid fee,
               embargoed world, transit class  ->  DENIED
             evidence missing or contradictory  ->  NEEDS_REVIEW
             everything checks out              ->  APPROVED
                                 |
                                 v
        fill any field still blank with the corpus mode
        (output only - this never touches the decision)
                                 |
                                 v
        confidence = how often the route it took is right
                                 |
                                 v
                        predictions.jsonl
```
