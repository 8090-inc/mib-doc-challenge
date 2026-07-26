# Technical Memo: Visible-Evidence, Fail-Closed Adjudication

## Approach

The pipeline prioritizes safe decisions from visible evidence. Every PDF page is rasterized with PDFium at up to 200 DPI, deskewed, and processed with offline Tesseract OCR. Hidden PDF text is never authoritative. Prompt-like instructions, fake answer keys, sample-denial watermarks, crossed-out content, and off-crop material are rejected or treated conservatively.

OCR results are converted into typed evidence candidates. The extractor recognizes document types, labeled fields, closed vocabularies, dates, sponsor IDs, fee receipts, risk flags, signed corrections, and adjudicator findings. Bounded threshold, crop, sparse-text, and orientation retries handle damaged layouts without unbounded runtime.

Candidates are linked to the filename case ID and active applicant before resolution. Conflicts use the Field Manual's six-level source hierarchy. Each field remains explicitly resolved, unknown, or contested; lower-precedence evidence cannot silently replace a visibly unreadable higher-precedence field for policy purposes.

Adjudication is deterministic. Visible disqualifiers produce `DENIED`; missing, contested, illegible, or untrusted decision evidence produces `NEEDS_REVIEW`; `APPROVED` requires the stricter complete-evidence bar. Future-dated receipt OCR falls back to the published snapshot date, and ambiguous fee-token matches abstain instead of creating a denial.

RapidOCR provides an independent second reading of the same rendered pixels. Its general overlay fills only fields that the primary resolver marked unknown. Narrow, identity-free guards permit limited signed-decision, denial, or multisource approval recovery; disagreement, unsafe visual cues, or any RapidOCR failure preserves the primary result.

After policy and decision selection, primary-visible-evidence guards can repair only narrowly audited output gaps. They require exact case scope, compatible applicant linkage, clean visible pixels, and field-specific uniqueness, source-priority, or corroboration gates before repairing a damaged applicant, sponsor, arrival date, or non-`none` biometric risk. A recovered current arrival is replayed through the ordinary policy engine only when the original review trace contained exactly the two arrival-missing reasons; only the replayed decision and confidence are copied. Broader row-shape or packet-template promotions are not used.

A final structural-approval head may discharge a review only when the packet's own topology clears the policy bar: a diplomatic packet carrying exactly one legible fee-receipt page, or a low-confidence `XW-1` review whose packet carries a visible sponsor-attestation page. It runs after every output repair, so it cannot pre-empt the stricter multisource head or discard a recovered field, and it never fires when the baseline raised a denial reason. The promotion is then re-checked against the emitted row itself — `risk_flags` must read `none`, the visa class must still be one of the two eligible classes, and the fee must be `paid` or `waived` — so a repair applied after the head's inputs were read can never leave an approved record that contradicts itself. The head is deliberately not extended to `MED-3`, where a sponsor page is no evidence about the required biohazard check, nor to packets whose visa class is unknown, nor to `TRANSIT-7`. On the training packets it declined all 167 review cases where promoting would have been wrong, including every truly denied diplomatic packet.

Confidence is based on the policy decision trace rather than raw OCR confidence. Frozen calibration artifacts use decision type and generic evidence semantics. A final guarded model may adjust confidence only for `NEEDS_REVIEW` rows, through either a low-confidence map or an unknown-fee floor, and cannot modify any extracted field or decision.

The CPU-only Docker image bundles all OCR models and pinned dependencies. It uses no LLM, VLM, cloud OCR, API, runtime download, or network service. Cases run independently across at most four workers, failures fall back to a schema-valid review row, and predictions are written atomically.

## Training Evaluation

The resulting 1,000 predictions were evaluated with the challenge evaluator.

| Metric | Result |
| --- | ---: |
| Total score | **128.710915 / 150** |
| Field extraction | 44.966667 / 50 |
| Classification | 66.330000 / 80 |
| Calibration | 17.414248 / 20 |
| Submitted valid rows | 1,000 / 1,000 |
| Catastrophic false approvals | **0** |

There were 773 exactly correct adjudications. Of the remaining cases, 223 were conservative deferrals of a true approval or denial to `NEEDS_REVIEW`. Only four emitted a wrong non-review decision, and none was a false approval.

## Failure Modes

The main weakness is excessive deferral. The approval bar prevents unsafe approvals, but it also routes many valid packets to review when a required field is missed or lacks sufficiently strong visible provenance.

Risk flags are the weakest extracted field, matching 823 of 1,000 training cases. Applicant names, sponsor IDs, fee status, and arrival dates also remain vulnerable to faint scans, damaged labels, unusual layouts, and multi-applicant packets.

The general RapidOCR path intentionally repairs unknown values rather than overwriting plausible primary readings. Consequently, a confident but incorrect Tesseract value may survive unless it matches one of the narrowly audited correction paths.

Several rules and confidence artifacts were frozen from public training subsets. Although they contain no case IDs or identity lookups, unfamiliar templates, corruption patterns, or policy combinations may not satisfy their evidence gates. Calibration may also shift on the private distribution.

## With Another Week

- Improve risk-field page routing and crop-level OCR consensus, then address applicant, sponsor, fee, and date errors in measured order.
- Analyze the 232 conservative deferrals and add only template-held-out, multisource evidence gates that safely discharge review cases.
- Re-evaluate rules and confidence using template-grouped cross-validation and synthetic scan corruption, with separate safety reporting for false approvals.

## Provenance

This solution derives from Chris Strobl's MIT-licensed `strobl/mib-doc-solution` at commit `d6752ecd88220e8fcd07f6d6825d2b8d642c9edc`. A narrow fee-token repair was informed by Yusuf Afifi's MIT-licensed solution at commit `2e6c4b2499040b3615a13331a0c4101c2aa98e23`. The source-priority output-repair structure was informed by Arjun Shah's MIT-licensed `arjunkshah12345-hash/mib-doc-solution` at commit `edc0ed14b405beda7290b1b1bac47d52df95e31c`; this fork narrows those repairs with explicit scope, corroboration, authority, and conflict gates. Git history, attribution, model provenance, and third-party licenses are preserved.
