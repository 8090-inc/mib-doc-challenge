# MIB Doc Challenge — Technical Memo

The final candidate was developed on a frozen 700/150/150 split of the public
training set; the sealed 150 was opened once after lock. It beat the original
image by **+2.8128 on calibration**, **+6.3245 sealed**, and **+5.4619 on all
1,000 cases**. A final rules-compliance pass reached **134.7171/150** on a fresh
full-1,000 Docker run: 45.4722 extraction, 71.9300 classification, and 17.3149
calibration. That score includes the safety cost: catastrophic false approvals
rose from 1 to 12.

## Approach

Six layers, with every decision reconstructible from a per-case evidence ledger.
This entry is derived under MIT from Brian Pridgen's public `handemanai`
baseline at commit `4b37a781`; the original license is preserved and the
changes below are ours.

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

_Final verification used the organizers' own `run_docker_submission.py` with
`--network none --cpus 4 --memory 8g --pids-limit 512 --read-only` and a 2 GiB
`/tmp`. The fresh 1,000-case run completed in about **72 m 36 s (4.36 s/PDF)**.
The same immutable image then processed all **5,000 validation PDFs** in
**6 h 36 m 46 s (4.761 s/PDF)** against the 8 h 20 m cap. The organizer
validator and an independent second invocation both reported **5,000 valid
records and zero missing case IDs**. The final prediction SHA-256 is
`2d52fae3e8d0f85b9668fa6301440f73854ef6c0aef9ee64abb1903302091529`.
The image is **0.27 GiB** with **14,144,822 bytes** of model artifacts. The
fresh training output matched the frozen replay case-for-case; the changed
surface passed **374 tests plus 20 subtests** inside the exact runtime. No
torch, LLM or VLM runs at inference. Licenses and provenance are in
`NOTICE.md`._
