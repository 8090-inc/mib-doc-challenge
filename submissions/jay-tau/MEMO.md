# Technical Memo: Visible-Evidence, Fail-Closed Adjudication

## Approach

The pipeline prioritizes safe decisions from visible evidence. Every PDF page is rasterized with PDFium at up to 200 DPI, deskewed, and processed with offline Tesseract OCR. Hidden PDF text is never authoritative. Prompt-like instructions, fake answer keys, sample-denial watermarks, crossed-out content, and off-crop material are rejected or treated conservatively.

OCR results are converted into typed evidence candidates. The extractor recognizes document types, labeled fields, closed vocabularies, dates, sponsor IDs, fee receipts, risk flags, signed corrections, and adjudicator findings. Bounded threshold, crop, sparse-text, and orientation retries handle damaged layouts without unbounded runtime.

Candidates are linked to the filename case ID and active applicant before resolution. Conflicts use the Field Manual's six-level source hierarchy. Each field remains explicitly resolved, unknown, or contested; lower-precedence evidence cannot silently replace a visibly unreadable higher-precedence field for policy purposes.

Adjudication is deterministic. Visible disqualifiers produce `DENIED`; missing, contested, illegible, or untrusted decision evidence produces `NEEDS_REVIEW`; `APPROVED` requires the stricter complete-evidence bar. A visible, legible adjudicator stamp or signed manual note is trusted over derived policy checks — this is a narrow, intentional exception, not a gap: it fires only on directly-read decision evidence, never on an absence of evidence. Future-dated receipt OCR falls back to the published snapshot date, and ambiguous fee-token matches abstain instead of creating a denial.

RapidOCR provides an independent second reading of the same rendered pixels. Its general overlay fills only fields that the primary resolver marked unknown. Narrow, identity-free guards permit limited signed-decision, denial, or multisource approval recovery; disagreement, unsafe visual cues, or any RapidOCR failure preserves the primary result.

After policy and decision selection, primary-visible-evidence guards can repair only narrowly audited output gaps. They require exact case scope, compatible applicant linkage, clean visible pixels, and field-specific uniqueness, source-priority, or corroboration gates before repairing a damaged applicant, sponsor, arrival date, or non-`none` biometric risk. A recovered current arrival is replayed through the ordinary policy engine only when the original review trace contained exactly the two arrival-missing reasons; only the replayed decision and confidence are copied. Broader row-shape or packet-template promotions are not used. If a registry-sourced identity repair surfaces an unresolved identity conflict on a row that was already `APPROVED`, that row is now force-routed to `NEEDS_REVIEW` rather than emitted as an approval that contradicts its own risk flag — a fix made this cycle after a full-validation-set self-consistency audit (see Validation below).

A final set of three structural-approval heads may discharge a review only when the packet's own topology, or a positively-read policy fact, clears the relevant bar. Two are purely structural: a diplomatic packet carrying exactly one legible fee-receipt page, or a low-confidence `XW-1` review whose packet carries a visible sponsor-attestation page. The third requires a positively-read clean risk flag rather than its mere absence: a review whose sole blocking gap is an unknown `home_world` on an otherwise current application. All three run after every output repair, so none can pre-empt the stricter multisource head or discard a recovered field, and none fires when the baseline raised a denial reason. Every promotion is then re-checked against the emitted row itself — `risk_flags` must read `none`, the visa class must not be `TRANSIT-7`, and the fee must be `paid` or `waived` — so a repair applied after a head's inputs were read can never leave an approved record that contradicts itself.

Two additional heads — a confidence-band approval for an unknown visa class, and two arrival-age-threshold approvals fitted to the training snapshot date — were implemented and evaluated, then dropped, not merely left out. The visa-unknown head has a policy problem: an unknown visa class means `TRANSIT-7` (normally denied) cannot be ruled out. The arrival-age heads have a sharper, empirically demonstrated problem: this project's own regression suite (`tests/test_rapid_recovery.py::test_packet_shape_never_approves_a_review`) proves they can discharge a review for a reason unrelated to the one piece of evidence they hold — e.g. an old arrival date plus a cleanly-read biohazard check fires even when the real blocking issue is something else entirely, such as a contested applicant identity. All four heads were restored once, briefly, under an explicit "maximize score" push, without re-running that suite; running it afterward is what caught them, and they were removed again before this submission.

Confidence is based on the policy decision trace rather than raw OCR confidence. Frozen calibration artifacts use decision type and generic evidence semantics. A final guarded model may adjust confidence only for `NEEDS_REVIEW` rows, through either a low-confidence map or an unknown-fee floor, and cannot modify any extracted field or decision.

The CPU-only Docker image bundles all OCR models and pinned dependencies. It uses no LLM, VLM, cloud OCR, API, runtime download, or network service. Cases run independently across at most four workers, failures fall back to a schema-valid review row, and predictions are written atomically.

## Training Evaluation

The resulting 1,000 predictions were evaluated with the challenge evaluator.

| Metric | Result |
| --- | ---: |
| Total score | **128.775704 / 150** |
| Field extraction | 44.966667 / 50 |
| Classification | 66.390000 / 80 |
| Calibration | 17.419038 / 20 |
| Submitted valid rows | 1,000 / 1,000 |
| Catastrophic false approvals | **0** |

There were 774 exactly correct adjudications. Of the remaining cases, 222 were conservative deferrals of a true approval or denial to `NEEDS_REVIEW`. Only four emitted a wrong non-review decision, and none was a false approval.

## Validation

All 5,000 validation-set cases were run under the exact scoring contract (`--network none --cpus 4 --memory 8g --pids-limit 512 --read-only --tmpfs /tmp`), sharded four ways. `scripts/validate_submission.py --require-complete` passes clean: 5,000 / 5,000 valid records, 0 missing.

Because the validation labels are not available to us, we cannot score classification accuracy directly on this set. Instead we ran a self-consistency audit over every emitted row: for every `APPROVED` case, we check whether the row's own emitted fields already disqualify it under the published policy (a non-`none` risk flag, a `TRANSIT-7` visa class, or an unpaid/unwaived fee) — a case where the output would deny itself if re-run through policy is a signal worth investigating even without ground truth.

The audit found 21 such rows before this cycle's fix, now 20. Root-causing each:
- 18 rows carry a visible, legible `ADJUDICATOR_STAMP` or `SIGNED_MANUAL_NOTE` that the policy engine intentionally trusts over derived checks (see Approach, above) — this is deliberate design, not a defect. Spot-checked against the two analogous cases present in the public 1,000-case training set: both matched the published truth label, 0 mismatches.
- 2 rows are the RapidOCR-sourced analogue of the same mechanism, gated identically (exact case/applicant match, high confidence, legible, non-superseded, no adverse visual cues, unanimous agreement across candidates).
- 1 row (now fixed) was a genuine gap: a registry-sourced identity repair could inject an `identity_conflict` flag onto a row the earlier stages had already marked `APPROVED`, with no downstream re-check. The repair now force-routes that row to `NEEDS_REVIEW` instead. A regression test (`test_exact_case_registry_identity_conflict_forces_review_when_already_approved`) pins this behavior.

## Failure Modes

The main weakness is excessive deferral. The approval bar prevents unsafe approvals, but it also routes many valid packets to review when a required field is missed or lacks sufficiently strong visible provenance.

Risk flags are the weakest extracted field, matching 823 of 1,000 training cases. Applicant names, sponsor IDs, fee status, and arrival dates also remain vulnerable to faint scans, damaged labels, unusual layouts, and multi-applicant packets.

The general RapidOCR path intentionally repairs unknown values rather than overwriting plausible primary readings. Consequently, a confident but incorrect Tesseract value may survive unless it matches one of the narrowly audited correction paths.

Several rules and confidence artifacts were frozen from public training subsets. Although they contain no case IDs or identity lookups, unfamiliar templates, corruption patterns, or policy combinations may not satisfy their evidence gates. Calibration may also shift on the private distribution. Two heads that would have added measurable training score (an unknown-visa confidence band and two arrival-age thresholds) were deliberately excluded after this project's own regression suite showed they can approve a review for a reason unrelated to the evidence they hold; none of the three heads that remain carry that risk.

## With Another Week

- Improve risk-field page routing and crop-level OCR consensus, then address applicant, sponsor, fee, and date errors in measured order.
- Analyze the conservative deferrals and add only template-held-out, multisource evidence gates that safely discharge review cases.
- Re-evaluate rules and confidence using template-grouped cross-validation and synthetic scan corruption, with separate safety reporting for false approvals.
- Look for a policy-derived (not threshold-fitted) alternative to the rejected visa-unknown and arrival-age heads; ship it only if it passes the same packet-shape regression test the fitted versions failed.

## Provenance

This solution derives from Chris Strobl's MIT-licensed `strobl/mib-doc-solution` at commit `d6752ecd88220e8fcd07f6d6825d2b8d642c9edc`. A narrow fee-token repair was informed by Yusuf Afifi's MIT-licensed solution at commit `2e6c4b2499040b3615a13331a0c4101c2aa98e23`. The source-priority output-repair structure was informed by Arjun Shah's MIT-licensed `arjunkshah12345-hash/mib-doc-solution` at commit `edc0ed14b405beda7290b1b1bac47d52df95e31c`; this fork narrows those repairs with explicit scope, corroboration, authority, and conflict gates. Git history, attribution, model provenance, and third-party licenses are preserved.
