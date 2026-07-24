# Technical Memo: MIB Intake Pipeline

## Approach

The pipeline is classical document engineering: PyMuPDF reads the native text
layer, Tesseract handles rasterized pages, RapidFuzz snaps noisy values onto
closed vocabularies, and a rule cascade mined from the training labels makes
the adjudication call. There is no ML model, no network access, and no LLM or
VLM anywhere in the runtime.

**Trusted text first.** Every span is read together with its styling. Spans
that are pure white, smaller than 6pt, injection-patterned (`SYSTEM:`, `answer
key`, `BARCODE PAYLOAD`), or watermark-sized get dropped before parsing, so
injected content never reaches field extraction or the trust cascade.

**The planted "answer key": found, measured, declined.** 18.8% of training
packets carry a hidden white 5pt CSV row styled as an answer key. Instead of
just filtering it, we measured it against the labels. Its adjudication column
is wrong in 188 of 188 carriers, a perfect inversion trap, while its
extraction fields are 90-98% accurate. Exploiting that structure is worth
+5.1 on the public training score. We ship none of it: the extraction gain is
an artifact of the public labels omitting `unrecoverable_fields`, and a
decision derived from a planted decoy contradicts the rule that answers rest
on visible evidence. The only thing the pipeline does with the hidden layer
is drop it.

**OCR only where needed.** A page whose visible text is footer-only gets
rasterized at 200 DPI grayscale and read with Tesseract PSM 11 and 6. If key
fields still resist, the page gets one 300 DPI escalation with two
binarization thresholds. Some biometric slips are printed sideways, which
defeats orientation detection under the background noise, so a budgeted
90/270 rotation pass probes stuck pages and reads cue-confirmed slips. Only
positive flag tokens are accepted from a rotated read: recovering a literal
"none" would defeat the uncertainty hedge that is correctly protecting cases
whose denial evidence is unreadable. About 30% of pages are image-only; the
rest never pay OCR cost, which keeps the run well inside the 6 s/PDF budget.

**Closed vocabularies.** Every enum-ish field is fuzzy-snapped to its
vocabulary, which turns most OCR noise into exact matches. Risk-flag tokens
are scanned order-independently across the whole page, with a digit-repair
fuzzy fallback for mangled reads and a prose form ("prior denial stamp
rescinded") for the one flag the generator writes as a sentence. Because
risk_flags is set-valued and scored as set equality, its candidates are
unioned across pages rather than resolved first-wins: an adjudicator note
names only the disqualifying flag, and letting it outrank the slip's complete
list silently drops co-occurring flags. Applicant names pass through a
144-token vocabulary mined from the training labels; a candidate survives
when exactly two tokens snap cleanly, a complete two-token name is preferred
over a higher-ranked partial or doubled-token artifact, and novel names fall
through unbroken. The name-grammar filter and the `scan_flags` recovery are
adapted from 8090's own MIT-licensed reference solution by thegoleffect; both
sites carry attribution comments in `mib.py`.

**Statistical fallbacks, disclosed.** Before any prior fires, an output-only
scavenge pass re-mines every line the run has seen (native, OCR variants,
rotated reads) for still-empty fields: looser label-anchored vocabulary
voting for the enum fields, a digit-repaired anchor search for sponsor ids
("msi 5809" recovers SPN-5809), and an in-window date vote for arrivals. Only
when scavenging also comes up empty does the pipeline emit the training-set
mode (fee: paid, visa: DIP-1, world: Wolf-1061c, species: LUNA_SECURID,
purpose: transit). The fee prior additionally requires that no fee evidence
was read at all: a positively-parsed "unknown" keeps its value, since that
reading is usually the truth. All of this runs strictly after adjudication so
it can never influence a decision. An empty answer is a guaranteed miss under
exact-match scoring; a scavenged read beats the mode, and the mode beats a
blank.

**Measured evidence precedence.** Where sources conflict, the winner was
measured on train rather than assumed: registry, then biometric, then sponsor
letter, then intake. The intake form turns out to be the corrupted source. It
loses every conflict against registry and biometric (21/21 and 13/13), so the
"primary record" is trusted last, the reverse of the manual's listed order.
Bracketed damage sentinels like `[NAME CUT OUT]` are dropped, and printed
`Manual correction: <field> is <value>.` lines override the fields they
correct (sponsor, visa class, applicant, fee status), at 100% on train.

**Adjudication as a mined cascade**, first match wins. An adjudicator-note
`Finding:` line decides outright (320/320 on train, including a fuzzy
fallback that recovers OCR-garbled findings, a strict-only read that rescues
notes whose damaged titles misclassify them as other page types, and a filter
that rejects the SAMPLE DENIAL decoy). An unambiguous colored stamp decides
next, trusted only on a recognized page type; conflicting stamps mean
NEEDS_REVIEW. After that come the deny rules: disqualifying flags, TRANSIT-7,
unpaid fee (DIP-1 is not exempt), a revoked sponsor (3 public plus 3
inferred) on a non-DIP visa, Wolf-1061c on a non-DIP visa, stale arrival, and
a junk-packet rule: world, sponsor, and flags all unrecovered plus an
unreadable OCR page is denied rather than hedged (13/17 on train, positive in
all five held-out folds, and deny-direction only, so it can never create a
false approval). Then the review gates: missing arrival, unknown fee,
review-only flags, unreadable flag evidence. Whatever passes everything is
APPROVED. One evidence-signature exception lives inside the missing-arrival
gate: a packet with the slip present, flags unread, and an unreadable OCR
page was fit at 71% DENIED and 0% REVIEW, so it is denied rather than hedged;
it survived all 5 held-out splits, and the junk-packet rule has since
absorbed most of its population (the remainder runs 3/3 on train). Embargo home worlds (TRAPPIST-1e,
Eris Relay) imply `planetary_embargo` (46/49 on train).

Two inferences deserve honest flags. Staleness is an absolute cutoff
(2026-01-02) standing in for the manual's relative 180-day rule, because
packet receipt dates are not extractable; it would need re-fitting if the
receipt epoch shifts. And the fee receipt's Amount+Waiver pair ($809 means
paid, $0 with DIP-WAIVER means waived) predicts the true fee status perfectly
on train, so it overrides misprinted status words. That is a bet that the
amount is the generator's ground truth rather than the label text.

**Uncertainty-aware approval.** A packet whose biometric slip exists but
resisted OCR cannot be safely approved, and neither can one with an unread
image-only page and no flag value read anywhere, since the slip could be
hiding in that imagery. Both route to NEEDS_REVIEW. Together with requiring
trusted-tier evidence before any deny rule fires on an OCR-derived value,
this holds catastrophic false approvals down to the residue: packets whose
deny evidence was never printed at all.

**Calibration.** Confidence is the smoothed empirical accuracy of whichever
decision path fired, keyed by an evidence signature on the uncertain paths.
That is what the Brier score rewards: honest probabilities, including 0.4-0.6
on the genuinely ambiguous buckets.

## Known failure modes

Packets whose disqualifying evidence is simply absent (no biometric slip
anywhere in the packet) get approved by policy and lost; the training set
says this is irreducible from visible evidence. Severely smeared slips still
occasionally read as flag-free. The staleness epoch and the revoked-sponsor
list are enumerated rather than derived, so novel test-only entries in either
would be missed.

## One-shot robustness

Scoring is a single offline Docker run with no retry, so a mid-run failure
cannot be allowed to cost the submission. Each PDF runs in its own worker; a
worker that dies at the C level is caught, the pool is rebuilt once, and a
completeness backstop guarantees every case at least a schema-valid
NEEDS_REVIEW fallback. Per-page parsing is guarded so one bad page costs a
page rather than the case, OCR stops after the first 12 pages, and case ids
are recovered by pattern from filenames. Unknown layouts degrade to
NEEDS_REVIEW, never to garbage.

## With another week

A stamp/seal region detector with targeted crop OCR for the worst slips.
Deriving the staleness epoch from printed receipt dates where they exist.
Per-field confidence outputs. And a held-out harness to re-fit the empirical
confidence table without touching decision logic.
