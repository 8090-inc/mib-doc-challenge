# Technical Memo — Multi-Page Packet Intake

## Where I started

I come from a computer vision / deep learning background, so my first pass on MIB was representation learning on rendered pages: compact CNNs for packet-level decisions, stamp and region heads for fee/risk cues, autoencoder-style denoising for washed-out scans, and fine-tuned VLM probes for illegible stamps and fee receipts. Those experiments were real exploration and useful for building intuition about where the hard packets live. They were not what won once I measured the metric that actually moves this leaderboard: **catastrophic false approvals**.

LLM/VLM runtimes are also out of bounds in the submitted image, so that stack stayed experimental. What I shipped is a document-engineering system: multi-page evidence fusion, conflict detection, adversarial text filtering, and safety-critical adjudication under the contest Docker contract.

## What the data forced

Packets mix clean digital forms, scan-only pages, sponsor prose, fee receipts, and inspection stamps. The PDF text layer is adversarial as well as incomplete—white/tiny spans can inject false fields. Approving a true deny is punished much harder than a cautious `NEEDS_REVIEW`.

Lessons from the CV/DL detours that mattered more than the models:

- **Silent stamps are a trap.** Many gold denies/reviews have no recoverable risk wording. Stamp CNNs and color/shape heuristics never produced a safe signal; blue/red/wax stamps also failed to correlate with fee or adjudication in a full-train audit. When the flag is visual-only, `NEEDS_REVIEW` is the honest answer.
- **Illegible fees look like a vision problem and often are not.** Targeted OCR crops and typo repairs recovered a real batch; past that, receipts are missing or unreadable. More model capacity mostly added confident wrong guesses.
- **Waiver shortcuts hurt.** Inferring approve from a visible waiver-style code raised CFAs. Reverted.

That pushed the design toward trusted evidence fusion over classifier confidence.

## What shipped

**Evidence hygiene.** Keep spans that look like real ink; discard white/tiny hidden text. Rank candidates by document role (intake → registry → attestation → fee) so a supporting letter cannot overwrite the intake form. OCR fills pages without meaningful native text; a unique high-trust value always wins over OCR at the same rank.

**Conflict as signal.** Disagreeing names or sponsor IDs become review flags. OCR debris (`Ixokesh`/`Ikokesh`, trailing `|`, glued next-row labels) was inventing false `identity_conflict`. Fixes: name canonicalization, edit-distance near-duplicates, gutter cleanup, and treating manual corrections as authoritative.

**Attestation is high-value and high-risk.** Sponsor letters often carry the only clean prose when the intake scan is wrecked. Filling visa/sponsor from attestation while OCR “completed” species/home world produced an approve over a silent warrant page. Approvals that lean on attestation now require trusted intake fields from the native text layer—caught only via CFA diffs.

**Field-manual adjudication.** Hard denies for disqualifying flags, unpaid fees, transit, and revoked sponsors (with the DIP-1 carve-out). Missing fee/visa → review. Non-DIP waived → review unless diplomacy is independently established. Confidences follow decision class for stable calibration.

Runtime stack in the image: Tesseract + Poppler + PyMuPDF/Pillow, four parallel workers. No network, no cloud OCR, no LLM/VLM.

## Engineering judgment

Decision quality dominates field greed. Inventing fees or stamps to chase extraction points loses on CFAs; prefer unknown + review when evidence is thin. The highest-leverage late win was cleaning false identity conflicts without reopening a CFA hole, after tightening the attestation intake gate.

## Still open / another week

Illegible receipts; OCR digit substitutions on sponsor IDs; waived non-DIP packets that gold somehow approves; transit/unpaid tokens that never OCR cleanly.

Next: receipt-only enhancement when fee is unknown; a **review-only** vision head that may demote approve→review but never approve/deny alone; sponsor digit reconciliation; OCR-quality-aware confidence. A small VLM remains interesting for the illegible tail under different runtime rules.

## Compliance

Docker entrypoint: `<input_pdf_dir> <output_predictions_path>`, `--network none`, scratch under `/tmp`, four workers for the four-vCPU host.
