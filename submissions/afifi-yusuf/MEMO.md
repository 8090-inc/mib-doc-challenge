# Technical Memo — Offline Packet Intake

## Problem framing

MIB packets mix clean digital forms, scan-only pages, sponsor prose, fee receipts, and inspection stamps. The PDF text layer is adversarial as well as incomplete: white/tiny spans can inject false fields or “instructions.” Scoring punishes catastrophic false approvals much harder than cautious `NEEDS_REVIEW`, so the system is built for **trusted multi-page evidence fusion** and **safety-critical decisions**, not maximum field recall at any cost.

## Approach

**Evidence hygiene first.** Spans are kept only when they look like real ink (reject white/near-white and tiny type). Candidates are ranked by document role — intake → registry → attestation → fee — so a supporting letter cannot silently overwrite the intake form. OCR runs on pages without meaningful native text; a unique high-trust value always wins over OCR at the same rank. That is cross-page fusion with an explicit precedence model, not “grep the PDF.”

**Conflict as signal.** Disagreeing applicant names or sponsor IDs become review flags rather than arbitrary picks. That surfaced a real production bug: OCR debris (`Ixokesh` vs `Ikokesh`, trailing `|`, glued `PASSPORT IMAGE` / next-row labels) was inventing false `identity_conflict`. The fixes were specific — name canonicalization, edit-distance near-duplicates, gutter punctuation stripping, and treating `Manual correction: applicant is …` as authoritative over pre-correction text.

**Attestation is high-value and high-risk.** Sponsor letters often carry the only clean prose for name, purpose, or visa when the intake scan is wrecked. Filling visa/sponsor from attestation while OCR “completed” species/home world looked like a full packet and produced an approve — including over a silent `active_warrant` page with no recoverable text. Approvals that lean on attestation now require trusted intake fields from the native text layer. That failure mode only showed up in CFA diffs.

**Adjudication under the field manual.** Hard denies for disqualifying flags, unpaid fees, transit visas, and revoked sponsors (with the DIP-1 carve-out). Missing fee/visa → review. Non-DIP `waived` → review unless diplomacy is independently established. Confidences are tied to decision class so calibration stays stable under distribution shift.

Stack in the submitted image: local Tesseract + Poppler + PyMuPDF/Pillow, four-way parallel over the scoring CPUs. No network, no cloud OCR, no LLM/VLM in the runtime.

## Things we noticed (negative results matter)

- **Silent stamps are a trap.** Several gold denies/reviews have no readable risk wording. Organizer clarification matched the data: when the flag is visual-only, `NEEDS_REVIEW` is the honest answer. Color/shape heuristics and stamp CNNs did not produce a safe signal; blue/red/wax stamps also did not correlate with fee status or adjudication in a full-train audit.
- **Fee pages are often unreadable, not under-parsed.** Mid-band crops and typo repairs (`pal`→`paid`, bare `Status:` lines) recovered a real batch, then returns collapsed. Remaining `paid/waived → unknown` soft misses are mostly missing or illegible receipts — more OCR budget there mostly added noise.
- **Waiver shortcuts hurt.** Inferring approve from a visible `DIP-WAIVER`-style code looked promising and raised catastrophic false approvals. Reverted. Unverified non-DIP waivers stay in review.
- **False identity conflict was a high-leverage fix.** Cleaning OCR name conflicts recovered real `APPROVED` cases without opening a CFA hole, once the attestation intake gate was tightened.
- **Decision quality dominates field greed.** Inventing fees or stamps to chase extraction points loses on CFAs. Prefer unknown + review when evidence is thin.

## Failure modes still open

Illegible fee receipts; OCR digit substitutions on sponsor IDs (e.g. reading a revoked `SPN-4040` instead of the true sponsor); waived non-DIP packets that gold somehow approves; transit/unpaid cases where the decisive token never OCRs cleanly.

## Explored but did not ship

I prototyped a compact packet CNN and stamp-oriented vision heads for fee/risk cues. On public train they did not improve the metric that matters — catastrophic false approvals — and stamp appearance showed no reliable correlation in audit, so they stayed out of the submitted image. A fine-tuned VLM is the natural tool for illegible stamps and washed-out receipts; under this contest’s runtime rules that remains a research direction, not the entrypoint.

## With another week

Receipt-only enhancement when fee is unknown; a **review-only** stamp head that may demote approve→review but never deny/approve alone; sponsor digit reconciliation across pages; OCR-quality-aware confidence for the calibration slice.

## Compliance note

Docker entrypoint: `<input_pdf_dir> <output_predictions_path>`, `--network none`, scratch under `/tmp`, four workers for the four-vCPU host.
