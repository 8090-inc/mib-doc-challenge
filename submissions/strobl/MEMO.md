# Technical Memo: Evidence-Linked, Fail-Closed MIB Document Pipeline

## Approach

This submission is a deterministic, CPU-only document pipeline designed for
the challenge's offline Docker contract. It discovers PDF inputs, isolates
case-level failures, processes at most four cases concurrently, validates each
prediction against a typed schema, and writes canonical JSONL in stable case-ID
order. The public solution repository contains the full implementation,
pinned runtime dependencies, OCR artifacts, licenses, tests, and
reproducibility instructions.

The pipeline is render-first: every page is rasterized at a bounded resolution
and evidence is extracted from visible pixels. Embedded PDF text is retained
only as a diagnostic side channel and is never allowed to become prediction
evidence. This prevents hidden white text, off-crop instructions, fake answer
keys, and similar prompt-injection material from overriding the visible
document.

Visible extraction starts with Tesseract in sparse-text mode. Bounded image
refinements, layout-aware row ordering, label/value pairing, aliases, and
conservative field normalizers recover identifiers, dates, fees, visa and
sponsor facts, policy fields, decisions, and pipe-delimited risk flags.
Candidates retain provenance: page and region, OCR confidence, source type,
visibility, and active case/applicant hints. A linking and resolution layer
then applies source authority, visibility, negation, strike-through, and
same-rank conflict rules before adjudication. Lower-ranked pages cannot silently
replace the active intake applicant, and decorative or crossed-out decisions
are excluded.

The latest version adds an independent fail-closed RapidOCR path for genuinely
unresolved visible evidence. It is not a second vote over already resolved
fields. The fallback is invoked only for bounded unknowns and is accepted only
when it independently satisfies field-specific validation and evidence
requirements. This improves recovery on visually difficult scans without
weakening the primary provenance or conflict model.

Adjudication is identity-free and deterministic. Published visa, sponsor, fee,
risk, date, stay, biohazard, waiver, and decision-authority rules are encoded as
inspectable predicates. Visible authoritative denials take priority. Unknown or
contested critical facts route to `NEEDS_REVIEW`; visible disqualifying facts
route to `DENIED`; `APPROVED` requires either a valid top-authority visible
decision or the strict policy bar. No case IDs, filenames, answer tables, split
membership, labels, or evaluation artifacts are present in the runtime.

Confidence estimates adjudication correctness rather than raw OCR quality. The
final change is calibration-only: the decision output is frozen first and its
confidence is then mapped through a pinned monotone calibration. Sentinel dates
such as `1900-01-01` are treated as missing/invalid placeholders rather than as
stale adverse evidence, closing a failure mode where placeholders could alter
policy outcomes.

Development used the public 1,000-case training set with a frozen,
adjudication-stratified 700/150/150 tuning/calibration/release protocol. Cases
examined during early OCR diagnosis were forced into tuning before new holdouts
were created. Calibration used only the calibration split, and the final
candidate was evaluated once on the release split. The final full-public-set
run scored **130.37/150**: field extraction **44.88**, classification **68.52**,
and calibration **16.97**, with zero missing predictions, zero invalid records,
and zero catastrophic false approvals. Frozen split totals were 131.09 on
tuning, 129.15 on calibration, and 128.25 on release. The repository test suite
reported 232 passing tests and two optional skips. These are reproducible local
measurements on labeled public training data, not a score on the unlabeled
validation set or a private leaderboard claim.

For submission, the merged public solution was run over all 5,000 supplied
validation PDFs. The generated JSONL is checked against
`data/validation_manifest.csv` before publication so the submission contains
one valid record per expected case and no extra or missing IDs.

## What Changed and Why It Helped

The initial optimization concentrated on single-pass OCR and direct field
normalization. The final pipeline separates concerns more sharply:

1. visible evidence extraction and provenance are preserved before any policy
   decision;
2. applicant/source linking resolves authority and conflicts explicitly;
3. an independent OCR fallback recovers only true unknowns under strict gates;
4. identity-free decision recovery prioritizes authoritative denials and
   fail-closed review;
5. confidence is recalibrated after decisions are frozen; and
6. sentinel values, offline closure, and third-party licenses are verified as
   release requirements.

This layering produced the score increase while preserving the challenge's
safety constraint: improvements do not depend on labels, identities, hidden
text, or case-specific lookup behavior.

## Known Failure Modes

Severe visual degradation remains the largest weakness. Small, blurred,
rotated, heavily overprinted, or low-contrast fields can remain unreadable even
after bounded refinements. OCR may merge neighboring cells, split a value, or
confuse similar characters. Graphical stamps and occluded seals remain harder
than ordinary text. Multi-applicant packets and damaged headings can reduce
source-type certainty. In these situations the conservative resolver may lower
field recall or approval recall because it prefers `NEEDS_REVIEW` to an
unsupported guess.

The public manual is intentionally incomplete, so rare policy combinations
without sufficient held-out support are not promoted into learned exceptions.
This protects classification safety but leaves some recoverable cases on the
table.

## What I Would Improve With Another Week

I would add a bounded stamp and region detector for saturated or seal-shaped
components, rectify each crop, and run a small deterministic preprocessing
ensemble only on the uncertain region. I would also strengthen table recovery
with line/cell geometry and character-level consensus for critical names and
identifiers.

On the policy side, I would expand visible conflict derivation for sponsor,
identity, and biometric evidence and validate every generalized rule on a new
held-out partition before release. I would extend the adversarial suite around
hidden-text injection, crossed-out decisions, multi-applicant packets, and
damaged scans, then profile the exact Docker image over the full validation
distribution to spend additional OCR work only where uncertainty justifies it.
