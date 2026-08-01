# MIB Doc Challenge — Technical Memo

## Summary

A deterministic, offline, CPU-only pipeline. Every field and every decision
traces to a specific visible mark on a rendered page, through a provenance
record that survives into the diagnostics.

On the 1,000 labelled training packets, scored with the organiser's
`scripts/evaluate.py`:

| Component | Score |
| --- | ---: |
| Field extraction | 40.496667 / 50 |
| Classification | 60.940000 / 80 |
| Calibration | 15.925072 / 20 |
| **Total** | **117.361739 / 150** |
| **Catastrophic false approvals** | **0** |

This is an in-sample number on public labels, not an estimate of private-test
performance. Two properties are worth more than the total: **zero catastrophic
false approvals**, and **280 of 280 true `NEEDS_REVIEW` cases correctly held in
review**. The pipeline never guesses when the evidence is not there.

No LLM, VLM, cloud OCR, network call, label file, case-ID lookup, or hidden
answer text participates in the runtime.

## Approach

PyMuPDF extracts native text with coordinates and per-span visibility. Tesseract
is invoked only on pages whose visible native text is insufficient, with bounded
higher-DPI and preprocessing variants for damaged fee receipts, biometric rows,
and adjudicator notes. Form values are paired to labels **geometrically**, not
by reading order — this corpus frequently places a value above its label in
internal span order, which silently shifts whole rows.

Extraction emits provenance-bearing candidates rather than values: each carries
document type, page, geometry, source, OCR confidence, visibility, trust tier,
and case linkage. Resolution applies the field manual's precedence and preserves
conflicts instead of averaging them away. Adjudication is deterministic, and a
set of uncertainty guards blocks approval whenever critical evidence is
unresolved, explicitly unreadable, or potentially stale.

**The trust boundary is visibility, enforced structurally.** Roughly a fifth of
packets carry a planted answer key as white-on-white or off-crop text. We do not
detect it by keyword: spans are classified by render properties before
extraction, and invisible content never enters the candidate stream. It cannot
supply a field, and it cannot supply a decision. Public entries above our score
exist that read that channel by default, and others that refuse it on the same
grounds we do; it is a disclosed trap, and we do not read it.

Confidence is a bounded mapping from the decision pathway, not a free parameter.
Mean Brier error is 0.1019, and the review bucket is honestly calibrated —
mean confidence 0.459 against 0.471 actual accuracy.

Two field repairs are ported under MIT from `strobl/mib-doc-solution` and
reimplemented against our span model, with full provenance in `ATTRIBUTION.md`.

The accepted post-PR-#51 change is status-aware, emission-only mode imputation.
After adjudication, confidence calibration, and the two visible-evidence
repairs are final, it fills only unresolved schema placeholders with five
independently measured public-train priors: `fee_status=paid`,
`visa_class=MED-3`, `declared_purpose=reactor maintenance`,
`home_world=Luyten-b`, and `species_code=TRIANGULAN`. Resolved values,
including literal `fee_status=unknown`, remain unchanged. The decision layer
never consumes these values, and `risk_flags`, applicant name, sponsor ID, and
arrival date are never imputed.

On the 1,000-case training run this changed exactly 1,202 cells: 400 fee,
183 visa, 246 purpose, 218 home-world, and 155 species. It fixed 406 cells and
broke 13 fee cells, for a measured extraction and total gain of **+1.825556**;
classification, calibration, adjudication, confidence, triggered rules,
blocking unknowns, and contradictions were byte-identical. The feature is on
by default after passing the independent and combined gates and can be disabled
with `MIB_ENABLE_STATUS_AWARE_IMPUTATION=0`.

## Failure modes

**Evidence that does not exist.** The dominant residual is not misreading, it is
absence. Of the 390 packets where we emit `fee_status: unknown` against a known
label, **319 contain no fee evidence anywhere** — no receipt page, native or
rasterised. Zero contain the word `Amount`. We censused this before optimising
and found the addressable slice was four cases, of which one would be wrong. The
public labels do not mark unrecoverable fields, so raw public field accuracy
understates true scored accuracy; `fee_status` at 60.1% is largely a floor
imposed by the documents.

**Risk flags are the real blocker.** `risk_flags` carries the heaviest field
weight and sits at 74.3%. We emit `none` for 249 packets that carry a genuine
flag, most on rasterised biometric slips damaged past our recovery threshold.
This is the single largest constraint on the whole system, for a reason the next
section makes concrete.

**195 true approvals are held in review.** Our fail-closed posture costs about
11.7 classification points. That is a deliberate trade: an unsafe `APPROVED`
costs 12 raw points against the review hedge's 2, and we have no CFAs.

**A rejected approval head, reported because the negative result is the
finding.** We implemented a layout-consensus rule to release clean packets from
review — proven fee, registry-and-intake identity agreement, permitted visa and
sponsor, no visible risk token. Measured in-pipeline it fired 135 approvals at
**57% precision**: +0.85 classification but **−1.18 calibration** and 29
catastrophic false approvals, scoring **114.60 against a 115.54 baseline**. No
confidence setting made it profitable. Every principled tightening we tried made
precision *worse*, falling to 0.11–0.31, because packets whose fields resolve
cleanly are exactly the adversarial ones. **16 of the 29 false approvals were
packets carrying a real disqualifying flag that we had read as `none`.** The
head is not wrong; it sits downstream of risk extraction. We reverted it rather
than ship a measured regression, and we declined to adopt the fitted
visa/purpose/page-signature blocklists that make the published version of this
rule work on public labels.

## What another week would buy

**Risk-flag recovery, using direction-asymmetric readers.** A reader that can
never emit `none` cannot manufacture a false approval, so it can run far more
aggressively than a symmetric one — deny-direction recovery on damaged biometric
slips, derived and validated on held-out folds. This is worth roughly +5 to +6:
direct extraction credit on the heaviest-weighted field, plus the 89 true
approvals currently blocked at the approval head's risk gate, plus making that
head safe enough to re-enable.

**Render-first extraction with a second OCR engine.** Our native-text-first
architecture leaves roughly 6 extraction points on the table against
render-first entries. Rasterising every page and adding a detection-based engine
for unresolved fields addresses the damaged-scan tail that Tesseract alone
misses.

**Confidence sub-bucketing by evidence quality.** Calibration is currently capped
by having 595 coin-flip reviews; it improves mostly as a by-product of resolving
them, but splitting the review bucket by evidence completeness would recover a
fraction independently.

## Compliance and runtime

Offline (`--network none`), CPU-only, read-only root with a writable `/tmp`,
4 vCPU and 8 GiB. The final 1,000-case official-contract run completed in
1,202.26 seconds — **1.202 seconds per PDF** against a 6-second budget. The
parallel four-worker contract run completed in 357.07 seconds and produced the
same prediction SHA-256. The image is 115,731,362 bytes against a 4 GiB cap and
vendors no model artefacts. One valid JSONL row is emitted per input. 196 tests
pass.

Licences and provenance for the ported code and all dependencies are recorded in
`ATTRIBUTION.md` and `third_party_licenses/`.

After the labeled release gates passed, the four-worker validation contract
emitted 5,000 predictions and 5,000 diagnostics in 1,897.10 seconds and passed
the complete-manifest validator with no missing, extra, or duplicate IDs. The
validation corpus has no labels, so it was used only for completeness and
drift checks. Reversing the final diagnostics' recorded placeholders showed
8,158 changes in the five allowlisted fields, with no decision or confidence
changes. Exact hashes and placeholder counts are recorded in
`reports/pr51_imputation_v1/P7_RELEASE_RECEIPT.md`.

The public repository is published as a single commit whose tree is the exact
source of the scored image
(`sha256:c561c701e1afa433a88fd79ff04a95294e82dbbb1a90d006ebf87be9748ecfe2`,
115,731,362 bytes), which produced the submitted prediction file with SHA-256
`b333b63c56f64eace1708f42b787954ef9a2df6135829e1ad1fdce38679dfd75`. Docker
image IDs are not bit-reproducible, so the correspondence was verified by
behaviour rather than by hash: the repository was cloned fresh, built, and run
offline against the training corpus, and its predictions are byte-identical to
the scored image's.
