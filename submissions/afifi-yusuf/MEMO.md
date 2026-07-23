# Technical Memo: Earning Approvals from Trusted Evidence

## Where I started

I work in computer vision and deep learning, so the first attempts looked like that: compact CNNs on rendered pages, stamp and region heads for fee and risk, denoising for washed scans, VLM probes when OCR failed. That pass mapped the hard packets. It did not yield a shippable adjudicator. Stamp and packet heads never separated clean approvals from silent or icon-only denies with any margin I trusted, and unlocking approvals when risk text was absent produced catastrophic false approvals on train. I kept the diagnostics and rebuilt the runtime as a classical stack: filter adversarial text, rank candidates by document role, type risk so schema `none` is not clearance, and follow the field manual with review as the default when the page is quiet.

## What the data forced

Packets mix clean digital forms, scan-only pages, sponsor prose, fee receipts, and inspection stamps. The PDF text layer is adversarial as well as incomplete; white or tiny spans can inject false fields. Approving a true deny is punished far harder than a cautious `NEEDS_REVIEW`.

Three dead ends from that vision work:

- **Stamps.** Many labeled denies have no recoverable risk wording. Stamp CNNs and color or shape cues never separated clean approvals from silent denies on a full-train audit. Quiet stamps stay in review.
- **Illegible fees.** Targeted OCR crops and typo repair recovered some receipts. Past that, more model capacity mostly added confident wrong guesses.
- **Waiver shortcuts.** Inferring approval from a visible waiver-style code raised false approvals, so that path was removed.

## What shipped

**Evidence hygiene.** Keep spans that look like real ink and discard white or tiny hidden text. Candidate values are ranked by document role (intake, then registry, then attestation, then fee) so a supporting letter can never overwrite the intake form. OCR fills pages that have no meaningful native text, and a unique high-trust value always beats OCR at the same rank.

**Typed risk (`FieldEvidence`).** The submission schema may emit `risk_flags=none` when risk is still unknown. That string is not clearance. `APPROVED` requires risk evidence in state `RESOLVED` (flags or explicit clearance) or a trusted text-layer Finding. Fail-closed demotion cut catastrophic false approvals to zero before any reclaim unlocks.

**Conflict as signal.** Disagreeing names or sponsor IDs become review flags. OCR debris such as `Ixokesh` versus `Ikokesh`, trailing pipes, and glued next-row labels was inventing false identity conflicts. The fixes were name canonicalization, edit-distance near-duplicate merging, gutter cleanup, and treating manual corrections as authoritative.

**Attestation is high-value and high-risk.** Sponsor letters often carry the only clean prose when the intake scan is wrecked. At one point, filling visa and sponsor from the attestation while OCR "completed" species and home world produced an approval over a silent warrant page. Approvals that lean on attestation now require trusted intake fields from the native text layer.

**Layout proofs.** After fail-closed adjudication, two unlocks may change `NEEDS_REVIEW` to `APPROVED` when visible proofs exist:

1. **Clean packet.** Explicit risk clearance in the trusted text layer (for example `Observed flags: none`), a layout-agreeing fee (`Amount $809` or waived receipt), and a real arrival date. OCR-only clearance is refused.
2. **Layout consensus.** DIP-1 or XW-2 only (XW-1 excluded), serialized `fee_status=paid`, visible `Amount $809`, matching Registry Name and Applicant, and no layout risk tokens. Medical-consult purposes are skipped.

**Visible field repairs.** Injection-stripped layout may repair weak/unknown fee, name, visa, arrival, sponsor, purpose, home world, and species. SYSTEM / `answer key only` lines are never used for fields or adjudication.

**Field-manual adjudication.** Hard denies for disqualifying flags, unpaid fees, transit visas, and revoked sponsors, with the DIP-1 carve-out. RapidOCR fills UNKNOWN fee/risk/visa only; forensic OCR retries large/footer scan slips for clearance and hard flags only — never negative-audit approve.

Runtime stack: Tesseract, RapidOCR, PyMuPDF, and Pillow with four parallel workers, fully offline.

## Results

On the public train set with the official `evaluate.py`: **120.14 / 150**, from 64.09/80 classification, 40.84/50 extraction, and 15.20/20 calibration, with zero missing cases and **zero catastrophic false approvals**. Relative to the prior fail-closed / forensic baseline (118.21 with zero catastrophic false approvals), layout repairs and consensus unlocks recover a slice of true approvals without reopening silent-stamp errors. Extraction remains the open gap versus render-first public baselines near 45/50.

Throughput stays inside the 6-second-per-PDF Docker budget on 4 vCPUs / 8 GiB.

## Engineering judgment

Decision quality matters more than squeezing out extra extracted fields. Inventing fees or stamps to chase extraction points loses on false approvals, so the system prefers unknown plus review when evidence is thin. The highest-leverage late wins were fail-closed `FieldEvidence` to stop catastrophic false approvals, then reclaiming only packets with visible fee and identity proofs, not silent risk.

I deliberately do not transcribe SYSTEM “answer key only” spans. That channel can inflate public-train extraction, but the challenge treats it as decoy / prompt injection.

## With another week

The open tail: illegible receipts (largest extraction miss), OCR digit substitutions inside sponsor IDs, waived non-DIP packets that the ground truth approves anyway, and form-typed ROI OCR on native embedded pixmaps for Amount / Waiver bands only.

## Compliance

The Docker entrypoint takes `<input_pdf_dir> <output_predictions_path>`, runs with `--network none`, writes scratch under `/tmp`, and uses four workers to match the four-vCPU host. The image is about 115 MiB against the 4 GiB limit, with no network calls, no external services, and no LLM or VLM inside. No train-label lookups, case-ID allowlists, or answer-key field transcription at inference.
