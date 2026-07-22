# Technical Memo — MIB Offline Intake Pipeline

**Author:** Abhishek Enaguthi  
**Solution repo:** https://github.com/Abhishek21g/mib-doc-challenge-solution  
**Train score (local):** **119.2 / 150** (extraction 39.9, classification 64.7, calibration 14.6; CFA 24)

Previous baseline on the same harness: 113.7 / 150.

## Approach

The pipeline is classical document engineering, not an LLM. That matches the offline Centauri-I contract and keeps the image small.

1. **Trusted text pass.** PyMuPDF span walk keeps only non-white, non-tiny spans and drops `SYSTEM:` / answer-key decoys. Label→value pairing recovers intake, fee, registry, biometric, and sponsor fields when the text layer is intact.

2. **Selective OCR.** Pages with fewer than 10 trusted spans are always OCR’d (biometric/flag/fee scans), even when other fields already look complete. Embedded rasters preferred over re-rasterizing. Fee recovery uses autocontrast header crops, light binarization, 2× upsample, and sparse PSM 11; amount+waiver lines jointly infer paid/waived (bare `$809` alone is *not* treated as paid — unpaid receipts print the same amount).

3. **Evidence precedence.** Manual adjudicator findings override forms. Native text-layer intake outranks OCR of the same form type (OCR was previously mis-tagged as `intake` and overwrote clean visas/names). Conflicting sponsor IDs become `sponsor_mismatch`; OCR name noise no longer invents that flag.

4. **Closed-vocab cleanup.** Declared purpose, species, and home world are snapped to the public closed sets with edit-distance repair. Applicant names strip `PASSPORT IMAGE` / glued next-row labels and trailing OCR debris.

5. **Adjudication.** Deterministic tree from the field manual + public train:
   - Hard deny: disqualifying flags, embargo worlds, `TRANSIT-7`, revoked sponsors, unpaid fees, stale non-DIP arrivals.
   - Review: unknown fee, review-only flags, unreadable arrival, identity gaps, attestation-only visa/sponsor without trusted intake.
   - Else approve. Never deny on `declared_purpose == transit`.
   - `SAMPLE DENIAL` watermarks and barcode “force approve” payloads are ignored.

6. **Confidence.** Bucketed by decision reason (disq deny vs fee-unknown review vs clean approve), fitted to public-train empirical accuracy — not OCR self-confidence.

## Failure modes

- **Invisible risk stamps.** ~2% of train denials carry `biohazard_red` / warrant / memory with no recoverable text; those remain catastrophic false approvals if the rest of the packet looks clean.
- **Illegible fee receipts.** Many remaining fee misses have no recoverable status even under aggressive OCR; unknown → review is the honest answer.
- **Competitor 121+ / 126.** Public Afifi repo scores ~117.5 on the same harness; an oracle merge of complementary field strengths reaches ~123. Hitting 126 needs stamp CV or a large fee-OCR breakthrough beyond Tesseract.

## What another week would buy

1. A review-only stamp/symbol head that may demote approve→review but never approve alone.
2. Held-out isotonic / hierarchical calibration (identity-free features only).
3. Stronger fee-only enhancement when status is still missing after the 2× crop.
4. Runtime profiling to keep average work under the Docker budget on clean packets.

## Engineering judgment

Classification is weighted higher than extraction, and false approval is penalized hardest. Prefer `NEEDS_REVIEW` when trusted evidence is thin; never trust hidden answer-key text. Reproducibility is the product: one Dockerfile, no network, no API keys.
