# Technical memo

Author: Sidharth Rajmohan (`dumko2001`)

Solution repository: <https://github.com/dumko2001/mib-doc-solution>

Public-train result: 101.930/150 on all 1,000 cases. The sections were 35.703
for extraction, 52.710 for classification and 13.516 for calibration. The run
produced no catastrophic false approvals. It averaged 1.84 seconds per PDF in
the challenge Docker runner.

This is a conservative baseline. It does not clear the usual 105-point
interview bar, and I do not want to dress it up as a leaderboard solution. The
useful part is the evidence boundary: the runtime never trusts the PDF text
layer, OCR text cannot appoint itself as an authoritative source, and conflicts
fall back to review.

## Approach

The container rasterizes each page with Poppler. Tesseract then reads the
renderer-owned PNG at 180 DPI and returns TSV boxes. Python never reads native
PDF text or passes a PDF path to OCR.

Page type and source authority are separate decisions. A page needs a visible
heading and an active case identifier in canonical geometry. A
conflict-checked packet footer is allowed as a fallback. Foreign identifiers,
mixed bindings and ambiguous geometry invalidate the source.

The extractor pairs labels and values using row and column geometry. Closed
fields use a 1,258-byte spelling lexicon built from the public training labels
and locked by hash. Applicant names, dates and sponsor identifiers use stricter
grammars. Output priors can fill low-value extraction gaps, but they never enter
adjudication or confidence.

Sources are resolved by precedence. Equal-rank contradictions abstain. A
manual finding needs its own heading, case binding and one typed finding. Sample,
revoked, cancelled and mixed findings do not count.

Adjudication follows the public rules and fails closed when identity, sponsor,
fee, visa or risk evidence is incomplete. A small train-fitted policy can only
change an otherwise complete non-diplomatic approval into a denial. It cannot
create an approval. Confidence is assigned after the decision.

The image contains Poppler, Tesseract English and standard-library Python. It
contains no cloud client, API key, LLM, VLM, native-PDF text extractor or
teacher annotation.

## What failed

The remaining errors are often complete-looking OCR states rather than obvious
missing text. In `MIB-000884`, the runtime reads visible sponsor `SPN-3592` as
`SPN-0007`, misses `illegible_biometrics`, and confidently denies a true review
case. More policy rules do not solve that class of error.

The hardened source checks also cost coverage. On public train, 222 true
approvals and 215 true denials fall back to review. That keeps false approvals
at zero but limits the classification score.

The train-fitted denial overlay is unstable under sponsor-grouped
cross-validation. I kept it as a one-way safety veto and do not claim that its
public-train behaviour will transfer to private test.

## What I would do with another week

I would replace more of the rule stack with a compact visible-state verifier.
Its job would be to verify page family, case binding, field ownership, stamps,
damage and contradictions before any text can affect adjudication.

I would also add selective high-resolution ROI recovery for uncertain sponsor,
risk and fee fields. The current 180-DPI pass would remain the fast path.
Every learned component would be selected inside fixed document-family and
sponsor-grouped folds, with zero catastrophic approvals as a hard gate.

I would rather submit an honest 101.930 with reproducible failure evidence than
hide an unsafe 104.409 behind a better headline. The latter produced 3 false
approvals of denied cases in the same full-train runner.
