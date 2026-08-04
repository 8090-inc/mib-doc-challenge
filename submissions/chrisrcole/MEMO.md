# Technical Memo — Visible-Evidence Hybrid + Cole Integration

## Attribution

This submission is layered; we attribute each layer rather than presenting
it as one system. The runtime foundation — span forensics, OCR, field
extraction, the policy engine, a small offline resolver, and calibration —
is reused under MIT from Tyler Gibbs's resubmission, itself derived from
Calling Moonshots, itself from Brian Pridgen's `handemanai` baseline (full
chain in `ATTRIBUTION.md`/`NOTICE.md`). On top of that frozen baseline,
Chris Cole integrated techniques from a separate, independently-built engine
("mib-with-others," archived at `archivedenginescripts/` for audit) and
added new work. Each item below is labeled by source.

## Approach

**Inherited baseline.** PDF text spans are classified by opacity, render
mode, contrast, crop intersection, and size before rasterization; invisible
spans are painted out before OCR runs, so hidden text and injected
answer-key overlays cannot reach extraction. OCR is RapidOCR/PP-OCRv5 — no
LLM or VLM anywhere in this pipeline — with selective high-quality re-read
for pages missing deny-relevant fields. A deterministic policy engine
applies revoked-sponsor, embargo, staleness, and disqualifying-flag rules
with an expected-value decision rule, so the system never approves on a
coin flip. A frozen five-seed resolver handles only the narrow
`NEEDS_REVIEW` subset, on features that exclude case IDs and identity.

**Cole's additions, shipped by default:** note-verdict recovery
(`colenote.py` — four readers recover a verdict from notes too damaged for
the baseline's reader; reasoning ported from mib-with-others, implementation
new); a ported page classifier (`colepages.py`) that typed 125 pages the
baseline left `unknown`, letting the note reader see them; a blob/silhouette
reader (`blobstamp.py`) that matches a note line's shape and width when
glyphs weld into one mass, rebuilt from curated exemplars and locality-gated
so it can't fire on an arbitrary page; an OCR cache and pass framework
(`ocrcache.py`, `passes.py`, both new) for cheap re-reads across recovery
stages; and a time-governed refinement harness (`refine.py`, new) that seeds
a valid conservative row for every case immediately, then spends leftover
budget on the highest-value unresolved cases before a governor closes the
window.

**Tried and shipped off:** a deshred stage (`vshred.py`/`hshred.py`, ported,
working, ~72 CPU-s/case against a 6s budget); a 57-bucket stamp classifier,
verdict-stamp gate, and portrait-signature model (staged in `models/cole/`,
not wired into the decision path). Neither lacked signal — both cost more
than they returned inside this budget.

**Portrait and stamp signatures — explored, no usable trend.** We went
looking for a shortcut: do portraits share a visual signature by
`species_code`/`home_world`, and does a stamp's visual variant carry
information beyond its own printed verdict? We harvested 309 stamp crops
(67 APPROVED / 141 DENIED / 101 NEEDS_REVIEW, 160 real after a shape gate)
and 525 portrait crops plus a 229-crop blue-background reference, and built
real infrastructure to compare them — a color/tone threshold signature for
portraits, and a two-stage k-means-teacher/grayscale-student classifier for
stamps (80.9% vs. 44.5% rescan stability, a real result on its own). What we
did not find was a usable cross-field trend: no portrait-to-species or
portrait-to-home-world correlation, and no stamp-variant correlation with
anything beyond the stamp's own text. That capability stayed staged, never
wired into a decision, and never taken to a full A/B — an unexploited lead,
not a formally tested null result.

**Human-eye-first tooling.** We built a small internal viewer (`viewer/`,
not shipped in the container) to render what each stage actually saw —
visible-text renders, masked-hidden-text overlays, page-type calls,
recovered note verdicts — beside the source PDF. Reading raw OCR JSON is
slow; seeing it the way a human adjudicator would catches wrong turns
faster.

## Provenance and a self-deselection commitment

Our first approach was our own engine: CPU-based, built on torch and docTR.
We ran it partly on GPU for speed — OCR output is the same either way, just
faster — and a CPU timing test looked fast enough to ship, until we realized
it was reading a warm OCR cache rather than doing the work cold. That forced
a late pivot: rather than ship an unvalidated from-scratch engine, we
adopted Tyler Gibbs's audited baseline as a working first pass and layered
our own note-recovery, page-classification, and refinement work on top —
the system described above. If our submitted `predictions.jsonl` turns out
identical to his, that is why, and we would rather self-select out of
consideration than have that read as passing off someone else's work as
new.

## Validation discipline and results

Validation PDFs and case IDs are never used as labels or model-selection
feedback; the pipeline holds no per-case lookup table, and the case ID comes
from the filename, never from content. On the public 1,000-case training
split, scored with the official `scripts/evaluate.py`: the frozen baseline
scores 134.72/150 with 12 catastrophic false approvals. Layering the note
channel and ported classifier reaches 135.07, and wiring the
harvested-profile banks reached 135.42/150 as of our last full official
re-score. Later work pushed the recovered-verdict ledger to 370/370 with
zero contradictions, but we have not re-run the full scorer against that
exact state — we report the last number we actually measured.

A cold, uncached, 24-worker bare-metal run of pass 1 alone, on the exact
pinned dependency stack, scored 134.85/150 (45.47 extraction, 72.05
classification, 17.33 calibration, 12 catastrophic false approvals) on the
public training split — confirming the wiring and pinned stack reproduce
end to end from a clean checkout. A follow-up passes-2–4 refinement
re-verification (targeting ~135.4) was started on the same run but will not
complete before submission; the pass-1 figures above are what we confirmed
end to end in time.

## Known failure modes

We did not resolve the baseline's 12 false approvals: root-cause work traced
them to two training cases where the disqualifying evidence (a biometric
slip) is genuinely absent from the packet, not damaged — indistinguishable
from 17 packets the same mechanism correctly approves. Guards that remove
all 12 cost 22–34 raw points by also blocking those correct approvals; our
shipped guard blocks only approvals a recovered note directly contradicts —
costs nothing, but doesn't remove any of the 12 either. The 6s/PDF budget is
also a hardware bet: we measured 4.4–4.8s/PDF on one machine and >9.3s/PDF,
unfinished, on a slower one, for the identical image — the time-governed
harness exists so a slow host still yields a valid file instead of a
timeout, not to make the host fast. Barcode immunity is also incidental, not
designed: no decoder exists in the runtime, so barcode text only fails to
influence a decision because it doesn't survive our vocabulary grammar.

## With another week

Two things, and they compound. First, speed: the baseline's high-quality
re-read escalates on any missing deny-relevant field, firing on ~70% of
packets and burning ~85% of pass-1 runtime rereading every scan page rather
than just the page carrying the missing field — the single largest lever we
measured and didn't ship, because we didn't want to change the hottest path
unmeasured this late. Second, and bigger: get substantially better at
reading damaged pages, not just faster at what we already read. We'd push
deshred, vshred, hshred, deglitch, ink-cleaning, and blob-matching further,
and train a dedicated engine purely for blobby, welded-together text instead
of curated shape templates. More ambitiously, we'd stop asking one engine to
read six unrelated document types and train a specialist per page type —
intake, biometric slip, sponsor letter, registry extract, fee receipt, and
adjudicator note each have their own layout and damage profile, and a model
that's very good at one of those six is smaller and more testable than one
generalist reading all six.

A closing note, since this was written by someone who is a petroleum engineer and not software
engineer: this challenge was genuinely fun, a real way to build skill in
this domain, and directly applicable to the oil and gas industry, where the
same problem shows up constantly — reconciling degraded scans, conflicting
field records, and evidence of varying trust across permits, inspection
reports, and well documentation.
