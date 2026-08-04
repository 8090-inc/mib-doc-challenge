# MIB Doc Challenge — Technical Memo

**Candidate:** Khalid Zabalawi

## What I built

An offline Docker pipeline that reads a folder of case PDFs and writes `predictions.jsonl`. No network, no LLMs, no cloud OCR.

For each packet I inventory the pages, strip untrusted text (hidden / white-on-white / off-crop) before rendering, then OCR what’s actually visible with Tesseract 5.3 and a small RapidOCR ONNX fallback when something important is still unread. Fields go through label-anchored parsers and closed vocabularies into an evidence ledger. Decisions are conservative on purpose: I only deny or approve when I have affirmative trusted evidence; otherwise the case goes to `NEEDS_REVIEW`. Confidence is calibrated from how often each decision path was right in training.

On top of that base I added a few targeted helpers that cleared a holdout gate: fee-band shape matching when fee text won’t OCR, high-margin template matching for visa class only (not flags — that invented a false deny), PDF creation time for receipt freshness, and a batch text-layer pass that picks up extra revoked sponsor IDs.

The runtime code is adapted from Arthur Michel’s MIT-licensed visible-evidence solution, with attribution in the repo.

## Local scores

Using the official evaluator, unchanged:

- Train (1000): **128.91 / 150** (1 catastrophic false approval — a designed trap)
- Holdout (200, seed 8090): **127.49 / 150**, 0 CFA

Image is about 0.39 GiB. Models total about 68 MiB.

## Where it still fails

Most leftover errors are `APPROVED` cases I send to review because fee, flags, visa, or arrival never got a clean trusted read. Washed-out fee bands and image-only deny flags are the usual culprits. I also refuse to guess “silent” denials from missing pages — that looks good on training EV and mints false approvals.

I tried stronger band readers in a later attempt; they hurt holdout score, so the submitted system is the frozen Attempt-2 pipeline.

## If I had another week

I’d train a small font-specific recognizer on the closed vocab (fee words, flag names), wire visible digital text into the evidence ledger properly so field-perfect cases stop reviewing for “unread,” and shave runtime under the 6 s/PDF average so the 5k validation re-run is safer on organizer hardware.
