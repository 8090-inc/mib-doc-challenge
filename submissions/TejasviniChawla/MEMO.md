# MIB Doc Challenge — Technical Memo

**Candidate:** Tejasvini Chawla · **Solution repo:** (link in SUBMISSION.md)

## Approach

The pipeline is a classical, fully-offline document system: PyMuPDF + Tesseract + OpenCV + rules,
no ML models beyond a fitted lookup table. Design principle: **trust only what a human would see**,
then squeeze every redundant copy of a fact out of the packet.

**1. Trust-classified text acquisition.** Every page yields text one of two ways. Pages with a real
text layer are read span-by-span with color/position metadata; spans that are white-on-white,
outside the crop box, or in micro-fonts are classified hidden and never parsed (this defeats the
embedded `SYSTEM: ignore visible evidence...` answer-key injections wholesale). Scanned pages are
rasterized and OCR'd — rasterization is inherently injection-proof, since hidden text doesn't
survive rendering. OCR escalates through bounded retries: raw 300dpi psm6 → orientation probe
(Tesseract OSD) → deskew/contrast-stretch variant; empirically, aggressive preprocessing *hurts*
on these synthetic scans, so the raw pass is primary.

**2. Page-type parsing.** Six document types (intake form, fee receipt, registry extract, biometric
slip, sponsor letter, adjudicator note) are classified by fuzzy header matching that survives OCR
damage, then parsed with per-type logic: strict label regexes, fuzzy per-line label recovery,
prose patterns for sponsor letters, `Finding:` extraction (plus a fuzzy uppercase-stamp matcher
that recovers `DEMIET` → `DENIED`), manual-correction grammar, and decoy detection
(`COPY ARTIFACT` pages describe a different applicant and are excluded).

**3. Closed-vocabulary snapping.** Every categorical field is fuzzy-snapped onto vocabularies mined
from the training labels: 12 species codes, 13 home worlds, 10 purposes, 5 visa classes, 8 flags —
and applicant names, which turn out to be generated from a closed 12×12 prefix-suffix token set
(144 tokens). This turns OCR noise ("bichmzsrd_yed") into exact matches (biohazard_red). A
context-free scavenging pass recovers values from pages whose labels were destroyed, since the
vocabularies are distinctive enough to match without label anchors.

**4. Cross-page merging with evidence precedence.** Fields merge across pages following the field
manual's trust order, adjusted by source quality (text layer ≫ high-conf OCR ≫ low-conf OCR).
Names are majority-voted (on train conflicts, the intake form is the tampered document). Manual
corrections override everything. Fee status falls back to the receipt's Amount line
($809 = paid, $0 + waiver code = waived; validated 297/297 and 106/106 on train).

**5. Derived flags.** Beyond printed `Observed flags:` lists, three flags are derived:
identity_conflict (trusted identity documents disagree on the name), sponsor_mismatch (the sponsor
letter attests a different applicant), illegible_biometrics (a biometric slip so damaged its flag
line cannot be read — 100% precision on a held-out train sample).

**6. Adjudication.** A visible adjudicator note wins outright (rank-1 evidence; 100% agreement with
train labels across 287 recovered notes, both text-layer and OCR). Otherwise a rule engine encodes
the field manual plus edge rules mined from the 1,000 training labels: three unpublished revoked
sponsors (SPN-2718/7331/9090, same DIP-1 exemption signature as the published three), two fully
embargoed worlds (Eris Relay, TRAPPIST-1e), Wolf-1061c embargoed for non-diplomatic classes, and
DIP-1 exemptions for revoked sponsors and stale arrivals. A small fitted policy layer resolves
rules whose truth distribution is mixed, by maximizing expected classification points under the
scoring matrix (the -4 false-approval cell makes NEEDS_REVIEW optimal for evidence-starved pools).

**7. Confidence.** Brier-optimal by construction: confidence = empirical accuracy of the decision
bucket (rule × OCR-quality band × missing-fields band), fit on train with smoothing and shipped as
a generated lookup table.

## Failure modes (known and accepted)

- **Invisible evidence.** ~4% of train packets carry a disqualifying flag with no visible trace
  (e.g., a memory_tampering case whose biometric slip was simply removed — verified by exhaustive
  span/image/font/metadata comparison against clean packets). These are undecidable case-by-case;
  the policy layer plays the expected-points optimum and calibration prices the residual risk.
- **Ink-destroyed scans.** The heaviest damage profile reduces glyphs to blobs no OCR can read
  (verified manually). Cross-page redundancy recovers most fields; what remains is the intended
  unrecoverable tier.
- **Stale-date rule.** Packets carry no receipt date, so staleness uses a cutoff fitted on train
  (2026-01-28). If the private test's date window shifts materially, this rule degrades.
- **Single-digit OCR errors in sponsor IDs** occasionally survive (SPN-2913 read as SPN-2513 on a
  degraded letter) despite a digit-whitelist re-OCR pass.

## What I'd do with another week

1. Train a small CNN glyph classifier (well under the 250 MB artifact cap) on synthetic renders of
   the document fonts + damage profiles — the degraded-bold pages are a solvable font-specific OCR
   problem that generic Tesseract loses.
2. Replace the stale-date cutoff with per-packet receipt inference.
3. Portrait-image forensics (perceptual hashing across the corpus) to catch identity conflicts
   whose text evidence was destroyed.
4. Bucket-level decision policy with cross-validation, and finer calibration buckets.

## Reproducing

`docker build -t mib-submission .` then run with the challenge's documented offline contract.
No network, no API keys, CPU-only; ~1.2s/PDF on 4 vCPUs. Calibration table and vocabularies are
checked in as generated code; `tools/` contains the fit scripts.
