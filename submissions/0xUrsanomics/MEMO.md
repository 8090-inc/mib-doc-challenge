# MIB Doc Challenge: technical memo

**Deterministic score on the labelled train split: 101.42 / 150** (fields 40.37/50, classification
48.94/80, calibration 12.11/20, missing-case penalty 0/10), measured with the challenge's own
`evaluate.py`. Validation predictions in `predictions.jsonl` were produced by the submitted image
under `--cpus 4 --memory 8g --network none --read-only`: 5,000 of 5,000 cases, 0.091s per PDF against
a 6s budget, peak 1,516 MiB.

## Approach

No model at runtime. PyMuPDF for text, tesseract for scan pages, hand-written rules for adjudication.
The task rewards being *right about what the document says* and being *honest about uncertainty*, and
both are more tractable with deterministic code than with a generative layer I would then have to
audit. The whole pipeline is four files.

**A record for every case, always.** A missing case forfeits its classification points *and* takes
the penalty, and a blank confidence scores Brier 1.0 rather than being skipped. So every failure path
still emits a row with a numeric confidence, and any extraction exception degrades to `NEEDS_REVIEW`
rather than to nothing.

**Confidence is derived from the decision path, not estimated separately.** The rubric scores
calibration against adjudication *correctness*, and the abstention policy already encodes how sure
the rules are, so a second independent estimate would be two copies of one signal. Each decision path
carries its empirical hit rate measured on train and shrunk toward the global accuracy (K=15) so a
small bucket cannot swing to a confident extreme. The gain comes from *separation*: disqualifying-flag
denials run near 100% while abstention paths run 30 to 40%, and no single number says both. Reported
out-of-sample: flat-0.5 floor 10.00, in-sample 12.11, 5-fold OOS 11.96.

## The trust layer, which is most of the interesting work

The packets are adversarial. Five channels can carry text that a human adjudicator would never act
on: colour-matched hidden text, off-crop text, sub-2.5pt text, barcode payloads, and a planted "fake
answer key". Each extracted field records its source, and the adjudicator strips any field whose
evidence came from an untrusted channel *before* applying policy. A disqualifying flag that exists
only in hidden white text must not deny, and must not be silently ignored either; it is removed and
the visible evidence decides.

**The measurement I would lead with in an interview.** Across the 188 train packets carrying a planted
answer key, the key's **field values agree with ground truth 93.1% of the time** (89.9% to 97.9% per
field) while its **adjudication agrees 0 times out of 188**. Truth `DENIED` is claimed `APPROVED` 106
times, `NEEDS_REVIEW` claimed `APPROVED` 51, `APPROVED` claimed `DENIED` 31. The attack budget is
spent making everything correct *except* the one field it wants you to act on, which is precisely what
makes spot-checking it feel safe.

That split drove the final design. The verdict is refused unconditionally and permanently. The field
values are read as a *last resort*, only where the document yields nothing else, and they are filled
into the output **after** adjudication has already returned. This matters because an earlier version
merged them into the packet and relied on the untrusted-source gate to strip them downstream: measured,
that moved 27 verdicts and pushed false approvals from 91 to 115, because populating a field changes a
packet's *completeness* even when its value is later distrusted, sliding packets out of safe abstention
into scored decisions. A downstream gate cannot undo an upstream write. The final version parses only
the first ten CSV columns, so the `adjudication` and `confidence` the injection wants planted are
unreachable rather than reachable-and-discarded.

For 121 of the 143 worst-extracting packets the injection *is* the entire document, 806 characters of
key line repeated per page with no form, receipt or labels underneath, so blanket refusal there falls
back to no evidence rather than to visible evidence.

## Failure modes I know about

- **Classification is the weak component: 48.94/80.** Better extraction moved packets out of safe
  abstention into scored decisions, and false approvals rose with it. That is a policy-threshold
  problem, not an extraction one, and I did not get to re-tune the threshold against the improved
  field coverage.
- **Calibration 12.11/20** against a 10.00 floor for emitting flat 0.5 everywhere. The path-hit-rate
  approach beats the floor honestly but only just; it has no signal for *why* a path is uncertain.
- **22 packets are unrecoverable and I verified that rather than assuming it.** 135 of their 143
  missing values are not present in the document text at all, so the ceiling from further parser work
  is 0.06 of 50. I stopped.
- **Local and container output differ on 3 of 1,000 train cases**, all on OCR pages, from tesseract
  nondeterminism rather than logic.
- **Peak memory is sampled at 2s**, so it is a floor. Two runs of near-identical code reported 2,675
  MiB and 1,516 MiB; I plan against the higher one.

## With another week

1. **Re-tune the abstention threshold against current field coverage.** Classification is 80 of 150
   and the -4 asymmetry means the threshold matters more than the classifier. It is currently tuned
   for a version of the pipeline that extracted materially less.
2. **Give calibration a real uncertainty signal**, e.g. per-field extraction agreement across
   independent channels, rather than deriving everything from the path identity.
3. **Cross-validate the trust layer against a held-out attack split.** Every rule was written against
   the same 1,000 train packets that measured it, so I cannot currently separate "the trust model is
   right" from "the trust model is fitted".
4. Attack my own submission: generate new injection variants and check the rules degrade gracefully
   rather than cliff.

## Reproducing

`docker build -t mib-submission .` then run with `--cpus 4 --memory 8g --network none --read-only`
and a tmpfs at `/tmp`. Entrypoint is `run.sh <input_pdf_dir> <output_path>`. Everything is baked into
the image; there is no network call and no model download at runtime.
