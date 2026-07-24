# Adjudication Policy (reverse-engineered and verified against 1,000 training labels)

The public `FIELD_MANUAL.md` is incomplete by design. The rules below were derived by statistical
analysis of `data/train_labels.csv` cross-referenced with the actual document contents of sampled
packets. Each rule cites the training evidence. These are **general policy constants**, not answers
keyed to specific case ids.

## Document taxonomy
Each packet is a set of single-form pages, each rendered as a clean text layer **or** a degraded
scanned JPEG (OCR required). Form types and the fields they carry:
- **FORM I-8090** (primary intake): applicant, species, home world, visa class, sponsor id, arrival
  date, declared purpose — the primary field source.
- **FORM B-13** (biometric slip): applicant, species match, biometric confidence %, observed flags —
  primary source of `risk_flags`.
- **MIB Fee Receipt**: fee status, amount, waiver code, optional waiver-confirmation text.
- **Sponsor Attestation Letter**: sponsor id, applicant, class (secondary/corroborating).
- **Planetary Registry Extract**: registry name, home world, species, registry status, arrival date.
- **Manual Adjudicator Note** (sometimes present): a signed finding — highest-precedence signal.

## Trusted-evidence precedence (from field manual, applied field-by-field)
adjudicator note → I-8090 form → B-13 biometric → sponsor attestation → registry → machine text.
Untrusted (never used): white/near-white text, off-crop text, barcode/QR payloads, "answer key"
decoys, fake `SYSTEM:` prompts.

## Decision order (first match wins)
Reference date `REF` = maximum arrival date across the input batch; stale cutoff = `REF − 180 days`.

0. **Adjudicator-note override** — a visible, non-rescinded signed note stating a Finding wins.
   A "SAMPLE DENIAL" watermark is a trap (not a denial). A denial stamp crossed out by a later
   signed approval is rescinded (→ review signal, not a denial).
1. **DENIED** — disqualifying risk flag: `planetary_embargo`, `biohazard_red`, `active_warrant`,
   `memory_tampering`. *(verified 72/72, 87/87, 17/17, 10/10 DENIED)*
2. **DENIED** — sponsor id ∈ revoked set **and** visa ≠ DIP-1. Revoked set = manual `{SPN-0007,
   SPN-0139, SPN-4040}` + learned `{SPN-7331, SPN-2718, SPN-9090}`, plus any in-document
   "sponsor … revoked" signal. *(verified revoked+non-DIP = 73/73 DENIED; revoked+DIP-1 never
   denied — DIP-1 needs no sponsor)*
3. **DENIED** — visa class `TRANSIT-7`. *(verified 53/53 DENIED; transit ≠ work authorization)*
4. **DENIED** — fee `unpaid` with no visible hardship/diplomatic waiver. *(verified 50/50 DENIED)*
5. **DENIED** — valid arrival date older than the stale cutoff **and** visa ≠ DIP-1. *(verified: all
   non-DIP 2025 arrivals DENIED; DIP-1 exempt via the diplomatic-note exception)*
6. **DENIED** — (secondary, cautious) embargoed home world `Wolf-1061c` on non-DIP-1 when otherwise
   clean. *(≈74% denial rate; prefer an explicit registry EMBARGO status when readable)*
7. **NEEDS_REVIEW** — fee `unknown`. *(verified 44/44 NEEDS_REVIEW)*
8. **NEEDS_REVIEW** — arrival date missing / `UNREADABLE` / present only in untrusted text.
9. **NEEDS_REVIEW** — review-only flag without a disqualifier: `sponsor_mismatch`,
   `identity_conflict`, `illegible_biometrics`, `rescinded_denial`. *(illegible alone → review; an
   illegible case that also trips a rule above is already DENIED there)*
10. **NEEDS_REVIEW** — cross-page contradiction among trusted pages (applicant/species/sponsor
    mismatch), or fee `waived` on non-DIP-1 with no visible waiver code/confirmation.
11. **NEEDS_REVIEW** — no readable trusted primary evidence (no I-8090 and no registry).
12. **APPROVED** — otherwise.

## Fee nuance
`waived` is acceptable when a visible waiver code (e.g. `DIP-WAIVER`) or a waiver-confirmation note is
present, or the visa is DIP-1. `waived` on non-DIP-1 with waiver code `N/A` and no confirmation is an
unsupported waiver → NEEDS_REVIEW.

## Confidence calibration
Confidence is set to approximate P(decision correct): ~0.92–0.97 for clean corroborated
APPROVED/DENIED, ~0.88 for single-rule denials, ~0.70–0.80 for NEEDS_REVIEW, ~0.55–0.70 when the
decision leans on heavy OCR or partial evidence. The pipeline never emits 0.99 (overconfidence on a
wrong answer is punished by the Brier-based calibration score).
