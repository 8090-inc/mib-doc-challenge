# Technical Memo — MIB Offline Intake Pipeline

**Author:** Abhishek Enaguthi  
**Solution repo:** https://github.com/Abhishek21g/mib-doc-challenge-solution  
**Train score (local):** 113.7 / 150 (extraction 37.1, classification 63.6, calibration 13.0)

## Approach

The pipeline is classical document engineering, not an LLM. That matches the offline Centauri-I contract and keeps the image small.

1. **Trusted text pass.** PyMuPDF span walk keeps only non-white, non-tiny spans and drops `SYSTEM:` / answer-key decoys. Label→value pairing recovers intake, fee, registry, biometric, and sponsor fields when the text layer is intact.

2. **Selective OCR.** Pages with almost no trusted spans (full-page scans) are OCR’d with Tesseract. Embedded page rasters are preferred over re-rasterizing. Header crops recover fee status under stamps; a mid-band + plain (unsharpened) pass recovers `Observed flags` lines that sharpening otherwise destroys.

3. **Evidence precedence.** Manual adjudicator findings override forms. Otherwise: intake → biometric → sponsor letter → registry → fee. Conflicting sponsor IDs / applicant names become `sponsor_mismatch`.

4. **Adjudication.** A deterministic tree inferred from the public field manual plus train labels:
   - Hard deny: disqualifying flags, embargo worlds (`TRAPPIST-1e`, `Eris Relay`, non-DIP `Wolf-1061c`), `TRANSIT-7`, revoked sponsors (listed + `SPN-9090`/`7331`/`2718`), unpaid fees, stale non-DIP arrivals (>180d vs 2026-07-01).
   - Review: unknown fee, review-only flags, unreadable arrival, identity gaps, weak OCR.
   - Else approve.
   - `SAMPLE DENIAL` watermarks and barcode “force approve” payloads are ignored.

5. **Confidence.** High when a manual finding or hard rule fires; lower when OCR or evidence gaps drove `NEEDS_REVIEW`.

## Failure modes

- **Invisible risk stamps.** Some train denials carry `biohazard_red` / `memory_tampering` / `active_warrant` with no recoverable text or OCR string—only a pictorial stamp or generation-side label. Those become false approvals if the rest of the packet looks clean (~2% of train).
- **Destroyed scans.** Heavy COPY/ARCHIVE overlays sometimes leave fee status unreadable; we then emit `unknown` → `NEEDS_REVIEW` (soft classification miss, correct under the manual).
- **Rescinded denials.** Crossed-out DENIED stamps without accompanying text are under-detected.
- **OCR noise.** Species/world strings and mangled flag tokens need fuzzy repair; residual extraction error caps the field score.

## What another week would buy

1. A tiny offline stamp/symbol classifier (red/blue rubber stamps → risk flag priors) under the 250 MiB artifact cap.
2. Deskew + morphological stamp suppression before OCR for fee headers.
3. Isotonic calibration of confidence on a held-out train slice to lift the Brier-based 20 points.
4. Stronger multi-applicant packet binding (active `case_id` header vs decoy pages).
5. Runtime profiling to cut average OCR work on clean text-layer PDFs while keeping scan recall.

## Engineering judgment

Classification is weighted higher than extraction, and false approval is penalized hardest. The system is therefore biased toward `NEEDS_REVIEW` when trusted evidence is thin, and it never trusts hidden text—even when that text contains a gold CSV. Reproducibility is the product: one Dockerfile, no network, no API keys, same code path for validation and private test.
