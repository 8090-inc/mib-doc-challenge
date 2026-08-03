# MIB Doc Challenge — Technical Memo

## Authorship and release scope

The prediction implementation documented below was authored by Calling
Moonshots and has technical origin at
[`callingmoonshots/mib-doc-challenge-solution@9ed5ed360ae40053dfee80bff09eef29a83a3980`](https://github.com/callingmoonshots/mib-doc-challenge-solution/tree/9ed5ed360ae40053dfee80bff09eef29a83a3980).
It is used under the preserved MIT license and upstream notices. Calling
Moonshots in turn derives the system from Brian Pridgen's MIT-licensed
`handemanai` baseline at commit
`4b37a7815bea79de0a01beca6eb6566e1611af73`.

The executable baseline prediction source is
`7da47773b39609a4e162a5e1b448d5f5657436bc`. Its prediction logic is unchanged
from the attributed technical origin; the later source identity closes build
and provenance handling used by V6-S2/V6-S3.

Luka Jurisic's contribution is a prediction-neutral release adaptation: pinned
image construction, deterministic 16-task orchestration, exact parity gates,
provenance receipts, validation, and submission packaging. Luka did not author
or alter the OCR, evidence extraction, rules, thresholds, routing,
adjudications, confidence values, models, or final serialization. First-person
technical descriptions in the preserved approach narrative refer to the
Calling Moonshots implementation.

An independent complete 1,000-row run of the frozen commit scored
**134.71776441333333 / 150**: 45.47333333333333 extraction,
71.92999999999999 classification, and 17.314431080000002 calibration. It had
**12 catastrophic false approvals** and prediction SHA-256
`79e05c3c1ea8639d4cb3a5b97036fdff2fc2ed5492b4818b56d2e536eb2f78d5`.

## Approach

Six layers, with every decision reconstructible from a per-case evidence ledger.
The upstream MIT derivation and the Luka release boundary are recorded above
and in `docs/V6_S_SOURCE_AND_LICENSE_LEDGER.json`.

**Forensics before rasterization.** 21.6% of training packets carry a fake
"answer key" as white-on-white or off-crop text. We classify spans by render
mode, opacity, colour and crop position, then delete hidden text before
rasterization so contrast enhancement cannot resurrect it into OCR. All 216
injections lie about adjudication; 106 would flip a denial to approval. Hidden
content is never evidence and can push only away from approval.

**Trap-masked OCR, then closed-vocabulary parsing.** RapidOCR with the
en_PP-OCRv5 mobile recognizer (7.9 MB, selected in a four-model bake-off) runs
at low resolution; packets missing deny-relevant fields earn a full-resolution
second pass. NFKC sanitization blocks homoglyph tricks. Fields snap to legal
vocabularies—12 species, 13 worlds, 5 visa classes, and a compositional name
grammar—with margins and cross-page agreement feeding confidence. We also read
vector strike-throughs as cancellations and treat `Registry Status: EMBARGO
REVIEW` as an approval blocker; `CLEAR` is deliberately not evidence.

**Direction-asymmetric ROI readers.** Five template-anchored readers recover
values from pixels that whole-page OCR abandons. Deny/review-only readers—a
flag reader that never emits "none", an embargo-world reader limited to embargo
worlds—cannot create a false approval and may be aggressive. Approval-adjacent
reads face a higher bar: "paid" requires the `un` prefix region to be positively
clean, not merely unreadable. Each direction shipped only at 100% dev precision.

**A deterministic policy engine.** Field-manual rules plus mined hard-embargo
worlds, revoked sponsors, and unpaid-fee behavior reproduce 97.3% of training
adjudications from true fields with zero approve/deny confusions. The staleness
epoch is shift-tracked from the batch's 90th-percentile arrival date with a
deadband and garble-filtered clamp, preventing a few bad year reads from
mass-denying a regenerated batch.

**Evidence-only terminal guards.** A frozen final guard bundle can only move a
terminal decision to `NEEDS_REVIEW`; it cannot change extracted fields or create
an approval or denial. It catches a condition-only denial whose visa is visibly
destroyed, an approval with an unresolved exact case-ID conflict, and an
approval whose benign visa appears only on fully superseded pages. Isolated
`SAMPLE DENIAL` text is explicitly excluded, as required by the field manual.
The statistical resolver is forbidden from reopening a guarded review.

**Decision theory and calibrated confidence.** Approve only when P(approved) >
1.5×P(denied) and that beats the review hedge; never omit a case. An out-of-fold
logistic calibrator uses 18 evidence-quality features with per-class isotonic
correction. Hidden-content features are forced to zero at inference. A narrow
five-seed forest may resolve only `NEEDS_REVIEW / insufficient_evidence`; its
visible evidence/layout features exclude case IDs and open identity values.
The exported JSON forest runs through a dependency-free evaluator.

## Measure before modelling

The dominant residual was "field never read." Before building a learned
extractor, we asked whether truth already existed in visible OCR. Between 31%
and 41% of fallbacks were parser-limited. Six deterministic fixes added about
2.4 points.

An early broad ML gate scored −4 out-of-fold and caused 32 false approvals, so
we rejected it. The shipped resolver is restricted to one deterministic review
reason and visible evidence/layout features; grouped out-of-fold and disjoint
checks preceded calibration and sealed evaluation. It improves expected score
by accepting more false approvals—an explicit utility trade, not a zero-false-
approval claim. A 2.6M-parameter OCR-correction transducer gained +0.04 on dev
but −0.05 sealed, so it ships disabled; grammar-constrained rapidfuzz decoding
shipped instead.

## Robustness

We paired clean documents with QR instructions, under-image text, hidden OCG
layers, render-mode-3, microtext and hidden-only fields; every trap twin must
produce identical output. We never decode barcodes. Perturbation tests exposed
a rotation cliff; form-content anchoring kept false approvals at zero across
degradations. SIGALRM deadlines, a parent heartbeat watchdog, worker recycling,
and atomic five-minute checkpoints prevent one native-library hang from losing
the batch.

## Failure modes

The original deterministic image had one catastrophic false approval where the
visible visa was wrong and truth was absent from every channel. The final
score-optimal resolver converts a bounded subset of structurally incomplete
packets using evidence-layout priors. It raises full-set classification from
66.20 to 71.93 and total score by 5.8907, while increasing catastrophic false
approvals to 12; the evaluator charges all of them.

When decisive fields are physically absent, the system must preserve
`NEEDS_REVIEW` or make a probabilistic bet. We bet only for
`insufficient_evidence` through the audited resolver. A harder operational
safety target can set `MIB_REVIEW_MODEL=0`; the deterministic path remains.

## With another week

Add precision-gated faint-ink restoration, per-field confidence, extend the
CTC-glyph second view to more closed vocabularies, and census deny-direction
reader precision across validation as private-shift insurance.

---

_Luka's V6-S3 pipeline independently generated 5,000 complete validation rows
with SHA-256
`08ba6fb615129dccd78ce29025d8d3945b7bea1b1e5bec4a0093fb8e7ec8e71f`.
This is Luka's regression hash, not an organizer truth oracle. No participant
prediction rows were downloaded or compared. Luka's untouched local baseline
hit the 30,000-second limit after
4,755 observed states without a valid terminal artifact; a later affinity run
was stopped after 707 states in 6,082.654 seconds, projecting approximately
43,017 seconds. The local runtime gate failed and organizer-host performance is
unresolved. The distributed Actions receipt establishes prediction parity and
artifact validity, not organizer runtime eligibility. Full disclosure is in
`docs/V6_S_LOCAL_RUNTIME_DISCLOSURE.md`; licenses and model provenance remain in
`LICENSE` and `NOTICE.md`._
