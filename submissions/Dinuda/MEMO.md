# Technical Memo

## Approach

This submission is an offline, CPU-only evidence compiler for damaged PDF case
packets. It does not use an LLM, VLM, network service, or validation-derived
lookup. Each PDF is treated as untrusted until individual claims pass visibility
and provenance checks.

The first stage inventories the packet, assigns page roles, and extracts native
text only when it intersects the visible crop and survives contrast, size,
watermark, white-text, and strike-through checks. Raster or low-text pages are
rendered and sent through selective Tesseract OCR. OCR restoration is bounded to
at most two non-generative views selected from the original render, deskewing,
local contrast enhancement, and horizontal-band alignment. The pipeline keeps
word boxes and evidence locations so hidden or injected PDF text cannot silently
become policy evidence.

The field resolver emits source-addressed claims and resolves conflicts using the
published authority order: signed manual findings, intake, biometric, sponsor,
registry, and then visible machine text. Closed vocabularies, name grammar,
field priors, revoked-sponsor candidates, and embargo candidates are inferred
from the 1,000 labeled public examples. Priors may fill a required output field,
but they are never treated as proof for an approval or denial.

Adjudication first honors readable manual decisions and handles rescissions,
later findings, and watermark/sample forms. Otherwise it applies the public
policy to supported evidence. Approval is deliberately conservative: risk, fee,
visa, sponsor, and arrival evidence must be sufficiently recovered and free of
material conflicts. Missing or damaged controlling evidence routes to
`NEEDS_REVIEW`.

Two small learned components operate after deterministic extraction:

- A deny-only manual-finding gate estimates an unreadable finding from structural
  generator correlations. It can only change `NEEDS_REVIEW` to `DENIED`, and two
  independent logistic specialists must both exceed threshold. Identity,
  filename, case ID, dates, hidden text, and template hashes are forbidden.
- A path-specific logistic calibrator changes confidence only. It uses eight
  structural features: initial confidence, policy posterior/margin, evidence
  coverage, damage, conflicts, and decision-path type.

Both artifacts were fit only from public training labels. Runtime code does not
load training labels or organizer reference data.

## Evaluation and anti-overfit audit

The frozen full 1,000-case public evaluation is **129.162 / 150**: extraction
44.710, classification 67.330, calibration 17.122, with **zero catastrophic
false approvals** and 1,000/1,000 valid rows.

I also performed an exact 900/100 retrospective split. Template families were
kept together, the action distribution was balanced, and all vocabulary,
archetype, manual-gate, and calibration artifacts were fit on the 900 side only.
The 900 side scored 129.020 (CFA 0); the 100 side scored 131.162 (CFA 0). There
is no measured train/test degradation on this split.

This is not presented as an untouched holdout: source rules had already received
feedback from the full public corpus during development. It is therefore a
post-selection stress test, not an unbiased private-test estimate. A code audit
found no case-ID, filename, identity, PDF-hash, or validation lookup. One
challenge-specific rule that rewrote every future OCR year to 2026 was removed
before the frozen evaluations because it was unsupported by the field manual.
The Docker image includes only the three runtime artifacts; research renders,
case traces, and reports are excluded.

## Failure modes

The system is intentionally underfit on severely damaged raster packets. Its
largest remaining error class is conservative `NEEDS_REVIEW` when a risk page or
controlling field cannot be recovered. OCR can still confuse low-resolution
dates, names, and fee values; opaque white replacement is unrecoverable once the
PDF has been flattened. Generator-derived vocabularies and page archetypes may
also shift on genuinely new private layouts. The deny-only manual gate is based
on a small eligible cohort and is correspondingly narrow.

With another week I would improve perception rather than add policy exceptions:
train a compact character/region detector on synthetic damage augmentations,
measure calibration on a genuinely sequestered corpus, expand layout-invariant
page-role features, and add metamorphic tests for rotated, rescanned, reordered,
and partially missing packets. I would preserve the current approval safety gate
and require every new action transition to pass a catastrophic-false-approval
regression suite.
