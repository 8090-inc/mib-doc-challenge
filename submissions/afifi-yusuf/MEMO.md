# Technical Memo: Earning Approvals from Trusted Evidence

## Where I started

I come from a computer vision and deep learning background, so my first pass at MIB was representation learning on rendered pages: compact CNNs for packet-level decisions, stamp and region heads for fee and risk cues, autoencoder-style denoising for washed-out scans, and VLM probes on illegible stamps and receipts. That exploration was worth the time. It showed me where the hard packets live, and it showed me that the metric that decides this leaderboard is catastrophic false approvals, not average accuracy. A classifier that guesses well on average still approves the occasional true deny, and one of those costs more than a dozen cautious reviews.

What I shipped is a document-engineering system built around that insight: multi-page evidence fusion, conflict detection, adversarial text filtering, typed field evidence, and safety-critical adjudication, all inside the offline Docker contract.

## What the data forced

Packets mix clean digital forms, scan-only pages, sponsor prose, fee receipts, and inspection stamps. The PDF text layer is adversarial as well as incomplete; white or tiny spans can inject false fields. Approving a true deny is punished far harder than a cautious `NEEDS_REVIEW`.

Three lessons from the vision detours mattered more than the models themselves:

- **Silent stamps are a trap.** Many labeled denies and reviews have no recoverable risk wording at all. Stamp CNNs and color and shape heuristics never produced a safe signal, and a full-train audit showed that blue, red, and wax stamps do not correlate with fee or adjudication. When the flag is visual-only, `NEEDS_REVIEW` is the honest answer — including any “approve when risk is silent” shortcut.
- **Illegible fees look like a vision problem and often are not.** Targeted OCR crops and typo repair recovered a real batch of receipts. Past that point the receipts are simply missing or unreadable, and more model capacity mostly added confident wrong guesses.
- **Waiver shortcuts hurt.** Inferring approval from a visible waiver-style code raised false approvals, so I reverted it.

Those results pushed the design toward trusted evidence fusion over classifier confidence.

## What shipped

**Evidence hygiene.** Keep spans that look like real ink and discard white or tiny hidden text. Candidate values are ranked by document role (intake, then registry, then attestation, then fee) so a supporting letter can never overwrite the intake form. OCR fills pages that have no meaningful native text, and a unique high-trust value always beats OCR at the same rank.

**Typed risk (`FieldEvidence`).** The submission schema may emit `risk_flags=none` when risk is still unknown. That string is not clearance. `APPROVED` requires risk evidence in state `RESOLVED` (flags or explicit clearance) or a trusted text-layer Finding. Fail-closed demotion cut catastrophic false approvals to zero before any reclaim unlocks.

**Conflict as signal.** Disagreeing names or sponsor IDs become review flags. OCR debris such as `Ixokesh` versus `Ikokesh`, trailing pipes, and glued next-row labels was inventing false identity conflicts. The fixes were name canonicalization, edit-distance near-duplicate merging, gutter cleanup, and treating manual corrections as authoritative.

**Attestation is high-value and high-risk.** Sponsor letters often carry the only clean prose when the intake scan is wrecked. At one point, filling visa and sponsor from the attestation while OCR "completed" species and home world produced an approval over a silent warrant page. Approvals that lean on attestation now require trusted intake fields from the native text layer.

**Layout proofs and CFA-safe reclaim.** After fail-closed adjudication, two identity-free unlocks may promote `NEEDS_REVIEW` → `APPROVED` when visible proofs exist:

1. **Clean packet** — explicit risk clearance in the *trusted text layer* (`Observed flags: none` / equivalent), layout-agreeing fee (`Amount $809` or waived receipt), and a real arrival date. OCR-only clearance is refused: it approved a silent deny when decoys and missing arrival skipped the stale-arrival deny.
2. **Layout consensus** — DIP-1 or XW-2 only (XW-1 excluded), serialized `fee_status=paid`, visible `Amount $809`, unique Registry Name ↔ Applicant match, and no layout risk tokens. Medical-consult purposes are skipped.

**Visible field repairs.** Injection-stripped layout may repair weak/unknown fee, name, visa, arrival, sponsor, purpose, home world, and species. SYSTEM / `answer key only` lines are never used for fields or adjudication.

**Field-manual adjudication.** Hard denies for disqualifying flags, unpaid fees, transit visas, and revoked sponsors, with the DIP-1 carve-out. RapidOCR fills UNKNOWN fee/risk/visa only; forensic OCR retries large/footer scan slips for clearance and hard flags only — never negative-audit approve.

Runtime stack: Tesseract, RapidOCR, PyMuPDF, and Pillow with four parallel workers, fully offline.

## Results

On the public train set with the official `evaluate.py`: **120.14 / 150**, from 64.09/80 classification, 40.84/50 extraction, and 15.20/20 calibration, with zero missing cases and **zero catastrophic false approvals**. Relative to the prior fail-closed / forensic baseline (118.21, CFA 0), layout repairs and consensus unlocks recover a slice of true approvals without reopening silent-stamp CFA. Extraction remains the open gap versus render-first public baselines (~45/50).

Throughput stays inside the 6-second-per-PDF Docker budget on 4 vCPUs / 8 GiB.

## Engineering judgment

Decision quality matters more than squeezing out extra extracted fields. Inventing fees or stamps to chase extraction points loses on false approvals, so the system prefers unknown plus review when evidence is thin. The highest-leverage late wins were fail-closed `FieldEvidence` to kill CFA, then reclaiming only packets with *visible* fee and identity proofs — not silent risk.

I deliberately do not transcribe SYSTEM “answer key only” spans. That channel can inflate public-train extraction, but the challenge treats it as decoy / prompt injection.

## With another week

The open tail: illegible receipts (largest extraction miss), OCR digit substitutions inside sponsor IDs, waived non-DIP packets that the ground truth approves anyway, and form-typed ROI OCR on native embedded pixmaps for Amount / Waiver bands only.

## Compliance

The Docker entrypoint takes `<input_pdf_dir> <output_predictions_path>`, runs with `--network none`, writes scratch under `/tmp`, and uses four workers to match the four-vCPU host. The image is about 115 MiB against the 4 GiB limit, with no network calls, no external services, and no LLM or VLM inside. No train-label lookups, case-ID allowlists, or answer-key field transcription at inference.
