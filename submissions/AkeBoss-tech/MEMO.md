# Original visible-pixel MIB document pipeline

## Approach

This submission is an independently implemented, offline, CPU-only document
engineering system. The container renders each PDF page to pixels, runs local
Tesseract OCR, classifies pages from visible schema labels, and parses public
fields into a typed evidence ledger. It does not read embedded PDF text, call a
network service, use an LLM or VLM, or include predictions or code from another
participant.

The extraction path combines whole-page OCR with bounded, label-anchored region
proposals. Invalid native crop readings may receive a single higher-resolution
retry. Normalizers enforce the public field schema, and the ledger retains
conflicting readings rather than silently overwriting them. Packet-level
consensus is used only where multiple visible pages independently support the
same field. Common OCR damage is handled through generic edit similarity,
closed public vocabularies, and a small set of visible glyph substitutions.

Adjudication is deliberately more conservative than extraction. Explicit
manual findings have the highest authority. Visible disqualifying evidence can
recover a denial from review, while unresolved authority, conflicting evidence,
or missing affirmative requirements fail closed to `NEEDS_REVIEW`. Approval
recovery uses separate affirmative gates and denial vetoes. Output-only
normalization and sentinel recovery happen after adjudication, so a speculative
field repair cannot change the decision or its confidence.

Small task-specific text models were trained from the public training split.
Identifiers are masked before model use, and learned predictions are limited to
closed public output vocabularies or independently gated decision recovery.
Development tracked extraction, classification, calibration, runtime, grouped
changes, and catastrophic false approvals. The final public-training regression
scored above 131 out of 150 with zero catastrophic false approvals.

## Reproducibility record

The attached validation artifact contains all 5,000 required records and was
generated in the official offline Docker configuration (one 4-vCPU, 8-GiB
instance; no network; read-only input). It completed in 7,034.87 seconds, or
1.407 seconds per PDF. Its SHA-256 is
`ae774998a62e6318b5eb9a2f2ebb367535a4e75c512eba75e191a1b08dff68c0`.
Validation labels are private, so this confirms completeness and runtime rather
than a hidden validation score.

## Failure modes

The main limitation is OCR quality on heavily occluded, rotated, or low-contrast
fields. Packet-wide consensus helps when a fact is repeated, but a unique value
that is unreadable everywhere remains unresolved. Names and dates are harder
than closed categorical fields because their value spaces are much larger.
Layout shifts can also reduce anchor quality, especially when a field label and
value are separated by an image or unusual column ordering.

The conservative decision policy intentionally trades some approval recall for
safety. Missing clean biometrics, fee evidence, or sponsor authority generally
produces `NEEDS_REVIEW`; this avoids catastrophic approvals but leaves points on
the table when the underlying packet is actually valid. Learned text features
may also generalize imperfectly to unseen rendering families, so they are
bounded by typed outputs and explicit policy gates.

## What I would improve with another week

I would build a larger renderer-perturbation suite covering scale, blur,
contrast, skew, compression, and synthetic occlusion, then require improvements
to hold across those groups before promotion. I would add more generic ROI
readers for dates, sponsor attestations, and manual-note authority, with
per-reader evidence traces and conflict audits.

For approval recall, I would keep recovery isolated from the main denial path
and evaluate it on grouped packet families with a hard zero-catastrophic-false-
approval requirement. I would also calibrate confidence on held-out rendering
families rather than random rows, and profile page-level work scheduling so
expensive OCR retries are reserved for fields that can still change a useful
output.
