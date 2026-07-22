# Technical Memo: Earning Approvals from Trusted Evidence

## Where I started

I come from a computer vision and deep learning background, so my first pass at MIB was representation learning on rendered pages: compact CNNs for packet-level decisions, stamp and region heads for fee and risk cues, autoencoder-style denoising for washed-out scans, and VLM probes on illegible stamps and receipts. That exploration was worth the time. It showed me where the hard packets live, and it showed me that the metric that decides this leaderboard is catastrophic false approvals, not average accuracy. A classifier that guesses well on average still approves the occasional true deny, and one of those costs more than a dozen cautious reviews.

What I shipped is a document-engineering system built around that insight: multi-page evidence fusion, conflict detection, adversarial text filtering, and safety-critical adjudication, all inside the offline Docker contract.

## What the data forced

Packets mix clean digital forms, scan-only pages, sponsor prose, fee receipts, and inspection stamps. The PDF text layer is adversarial as well as incomplete; white or tiny spans can inject false fields. Approving a true deny is punished far harder than a cautious `NEEDS_REVIEW`.

Three lessons from the vision detours mattered more than the models themselves:

- **Silent stamps are a trap.** Many labeled denies and reviews have no recoverable risk wording at all. Stamp CNNs and color and shape heuristics never produced a safe signal, and a full-train audit showed that blue, red, and wax stamps do not correlate with fee or adjudication. When the flag is visual-only, `NEEDS_REVIEW` is the honest answer.
- **Illegible fees look like a vision problem and often are not.** Targeted OCR crops and typo repair recovered a real batch of receipts. Past that point the receipts are simply missing or unreadable, and more model capacity mostly added confident wrong guesses.
- **Waiver shortcuts hurt.** Inferring approval from a visible waiver-style code raised false approvals, so I reverted it.

Those results pushed the design toward trusted evidence fusion over classifier confidence.

## What shipped

**Evidence hygiene.** Keep spans that look like real ink and discard white or tiny hidden text. Candidate values are ranked by document role (intake, then registry, then attestation, then fee) so a supporting letter can never overwrite the intake form. OCR fills pages that have no meaningful native text, and a unique high-trust value always beats OCR at the same rank.

**Conflict as signal.** Disagreeing names or sponsor IDs become review flags. OCR debris such as `Ixokesh` versus `Ikokesh`, trailing pipes, and glued next-row labels was inventing false identity conflicts. The fixes were name canonicalization, edit-distance near-duplicate merging, gutter cleanup, and treating manual corrections as authoritative.

**Attestation is high-value and high-risk.** Sponsor letters often carry the only clean prose when the intake scan is wrecked. At one point, filling visa and sponsor from the attestation while OCR "completed" species and home world produced an approval over a silent warrant page. Approvals that lean on attestation now require trusted intake fields from the native text layer. I caught this only through false-approval diffs between runs.

**Field-manual adjudication.** Hard denies for disqualifying flags, unpaid fees, transit visas, and revoked sponsors, with the DIP-1 carve-out. A missing fee or visa goes to review. A waived fee outside DIP-1 goes to review unless diplomacy is independently established. Confidence follows decision class, which keeps calibration stable.

Runtime stack: Tesseract, Poppler, PyMuPDF, and Pillow with four parallel workers, fully offline.

## Results

On the public train set with the official `evaluate.py`: **117.73 / 150**, from 63.58/80 classification, 39.30/50 extraction, and 14.85/20 calibration, with zero missing cases. The residual false approvals on train are 18 of 431 true denies, concentrated in packets whose disqualifying flag has no recoverable text evidence. Throughput in the Docker image is roughly one second per PDF on 4 vCPUs, well inside the 6-second budget.

## Engineering judgment

Decision quality matters more than squeezing out extra extracted fields. Inventing fees or stamps to chase extraction points loses on false approvals, so the system prefers unknown plus review when evidence is thin. The highest-leverage late win was removing false identity conflicts without reopening a false-approval hole, which required tightening the attestation gate first.

## With another week

The open tail: illegible receipts, OCR digit substitutions inside sponsor IDs, waived non-DIP packets that the ground truth approves anyway, and transit or unpaid tokens that never OCR cleanly.

Next steps: receipt-only image enhancement when the fee is unknown; a review-only vision head that can demote an approval to review but never approve or deny on its own; sponsor digit reconciliation; and OCR-quality-aware confidence. A small VLM remains interesting for the illegible tail.

## Compliance

The Docker entrypoint takes `<input_pdf_dir> <output_predictions_path>`, runs with `--network none`, writes scratch under `/tmp`, and uses four workers to match the four-vCPU host. The image is about 115 MiB against the 4 GiB limit, with no network calls, no external services, and no LLM or VLM inside.
