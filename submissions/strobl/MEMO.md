# Technical Memo: Visible-Evidence MIB Document Pipeline

## Approach

The submission is a deterministic, CPU-only document pipeline built for the
challenge's offline Docker contract. It discovers PDF inputs, processes cases
independently with at most four workers, validates every result against a typed
prediction model, and writes canonical JSONL in stable case-ID order. A failure
in one document is isolated rather than terminating the batch.

The pipeline is deliberately render-first. Every PDF page is rasterized at a
bounded resolution and OCR operates on the visible pixels. The embedded PDF
text layer is retained only as a non-authoritative diagnostic side channel; it
never becomes prediction evidence. This prevents hidden white text, off-crop
content, fake answer keys, barcode instructions, and similar prompt-injection
material from overriding what is actually visible on the page.

For OCR, Tesseract runs in sparse-text mode, which handles the challenge's
forms and separated table cells materially better than treating a page as one
uniform text block. OCR regions are reordered into visual rows, then from left
to right, before labels and values are paired. Field aliases and conservative
normalizers cover identifiers, dates, fee states, visa fields, policy-only
fields, decisions, and pipe-delimited risk flags. Visible narrative decisions
and mildly corrupted risk wording are recovered with bounded deterministic
matching. Confidence thresholds preserve unreadable values as unknown rather
than guessing them.

Candidate evidence carries page location, OCR confidence, source type,
visibility status, and active case/applicant hints. Resolution applies the
manual's precedence hierarchy: visible adjudicator or signed-note evidence,
then intake form, biometrics, sponsor attestation, registry extract, and only
last the untrusted text layer. Same-rank conflicts remain contested;
struck-through values and decorative sample denials are excluded. Applicant
linking is also precedence-aware so lower-ranked conflicting pages cannot
silently replace the active intake applicant.

Adjudication is deterministic and evidence-aware. Published visa, sponsor,
fee, risk, date, stay, biohazard, and waiver rules are encoded as inspectable
predicates. Unknown or contested critical evidence routes to `NEEDS_REVIEW`.
Visible disqualifying facts route to `DENIED`; `APPROVED` requires either a
valid rank-one visible decision or the strict policy bar. Generalized learned
exceptions are permitted only when they make policy stricter, use visible
features, have held-out support, and contain no case identity.

Confidence estimates the probability that the emitted adjudication is
correct, not OCR quality. The raw signal is derived from the policy trace and
mapped through a pinned isotonic calibration. Development used a frozen,
adjudication-stratified 700/150/150 tuning/calibration/release split. Cases
inspected during an early OCR diagnosis were explicitly forced into tuning
before fresh holdouts were generated. Calibration used only the 150-case
calibration split; the final candidate was evaluated once on the fresh release
split. On that local engineering benchmark, the candidate scored 100.11/150
versus 45.46 for the pre-change baseline, with zero catastrophic false
approvals in both runs. These are local public-training measurements, not an
official leaderboard score.

The runtime image includes only pinned packages and runtime artifacts. It has
no labels, split assignments, evaluation reports, case IDs, filenames, or
answer lookup tables, and it requires no network access.

## Known Failure Modes

The largest remaining weakness is severe visual degradation. Small, blurred,
rotated, or heavily overprinted fields can be unreadable even after bounded
deskewing, especially names and compact stamps. Sparse OCR is strong on clean
tables but can still merge neighboring labels, split a value across regions,
or confuse visually similar characters. The conservative fallback protects
safety but can lower extraction and approval recall.

Some risk indicators are graphical stamps or low-contrast marks rather than
ordinary text. The current lightweight visual cues and OCR recover many of
them, but tiny or occluded stamps remain difficult. Multi-applicant packets and
damaged page headings can also reduce source-type certainty. Finally, the
public manual is intentionally incomplete, so rare policy combinations without
enough public held-out support remain `NEEDS_REVIEW` instead of being promoted
to an unverified exception.

## What I Would Improve With Another Week

I would add a bounded stamp/region detector that locates saturated or
seal-shaped components, rectifies each crop, and runs a small OCR ensemble over
the crop only. I would also add layout-specific table recovery using line and
cell geometry, plus character-level consensus across two deterministic image
preprocessing variants for critical identifiers and names.

On the policy side, I would expand visible conflict derivation for sponsor,
identity, and biometric evidence, then validate each generalized rule on a new
held-out partition before publication. I would build a larger golden/adversarial
suite around injection attempts, crossed-out decisions, multi-applicant pages,
and damaged scans. Finally, I would profile the exact Docker image over the
entire validation distribution and tune render resolution and crop scheduling
to spend additional OCR work only on uncertain pages while preserving the
offline runtime and memory limits.
