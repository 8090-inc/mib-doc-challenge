# MIB Document Challenge — Technical Memo

## Summary

This submission is a deterministic, CPU-only document pipeline designed around
the challenge's most important boundary: visible evidence is trusted and hidden
PDF instructions are not. It renders every page to pixels with Poppler, applies
bounded classical image preprocessing, recognizes text with offline Tesseract,
decodes challenge fields inside labeled regions, and resolves evidence with
explicit provenance and policy precedence. It contains no LLM, VLM, cloud OCR,
API key, validation-answer lookup, or per-case edit.

On the 1,000 public training packets, the frozen v9 image scores **125.23 / 150**:
42.10 extraction, 66.58 classification, and 16.55 calibration. It emits 1,000
valid rows with no missing cases. Under the organizer runner it completes in
4,028 seconds (4.03 seconds/PDF) on four CPUs and 8 GiB, with a 0.16 GiB image.

## Approach

The evidence path begins by rendering PDFs at 150 DPI. Native text layers,
barcodes, QR codes, off-page content, and embedded instructions are never read.
The only raw PDF metadata used is a bounded ReportLab creation date, treated as
the receipt clock for the public staleness rule; it never supplies an applicant
field or decision. Each visible page is deskewed and passed through a primary
OCR/layout path. Low-confidence, unclassified, blank-field, fee-gap, or manual
pages receive a bounded fallback ladder: autocontrast, sparse-text recognition,
rotation, ink masks, and selected 280-DPI top/full-page retries. At most two
pages per packet use the expensive path.

Recognition is deliberately constrained. Closed vocabularies repair modest OCR
damage in species, planet, visa, purpose, fee, and risk values. Sponsor IDs and
dates use narrow grammars with common character-confusion repair. Names use the
public synthetic name grammar. Label extraction is exact-first and only then
fuzzy, preventing a near label such as “Registry Name” from stealing the later
“Registry Status” region.

Every recovered value is stored as a claim with page, source type, OCR variant,
and confidence. Resolution follows the public trust hierarchy: visible manual
correction/finding, intake, biometric or fee evidence, sponsor attestation, and
registry. The resolver also detects sponsor/applicant conflicts and preserves
visible unreadable or blank labels as gaps rather than filling them from hidden
content.

Adjudication is transparent and ordered. Visible signed/manual findings win.
Otherwise the system applies disqualifying risks, transit and mandatory-fee
rules, embargo/revoked-sponsor rules with diplomatic exceptions, staleness,
then review-only risks and evidence gaps. A compact final backoff handles clean
packets in which only a trusted risk or fee source is absent. It uses aggregate
training frequencies by missing-source type and visa class—never case IDs—and
assigns empirically calibrated confidence. Other policy families are calibrated
separately; for example, a visible disqualifying risk is much more reliable than
an OCR-inferred authoritative gap.

Four worker processes handle sorted PDFs, with one OCR thread per worker. Output
is deterministic JSONL sorted by case ID and atomically replaced only after all
workers finish. An exception in one packet yields a conservative schema-valid
row instead of losing the batch.

## Failure modes

The largest remaining limitation is genuinely absent visible evidence. If a
risk panel or fee page is cut away, a system cannot know whether the hidden
condition was clean, unpaid, or disqualifying. The aggregate backoff improves
the deterministic score but can still false-approve some denied packets; these
events are reported at low confidence and were included in model selection, not
ignored. Tesseract can also lose severely warped stamps, merge adjacent labels,
or classify a damaged page as the wrong document family. The two-page fallback
cap protects runtime but may leave a third damaged page underprocessed.

Confidence is calibrated in-sample by interpretable decision families, so a
validation layout shift could change reliability. The creation-date clock also
assumes the organizer's ReportLab-style metadata remains meaningful; if absent,
the pipeline simply declines the staleness inference. Finally, fixed OCR rules
are less flexible than a learned layout model on unseen templates, although
they are easy to audit and robust against prompt injection.

## With another week

I would build a synthetic corruption harness from the public templates and use
grouped, out-of-fold evaluation by damage pattern rather than further tuning on
the same 1,000 labels. I would train a small task-specific page-family and
region-quality model, within the challenge's model limits, to spend high-DPI OCR
only where its expected value is highest. I would add connected-component-based
stamp localization, local perspective correction, and per-field OCR ensembles
instead of whole-page retries. Finally, I would fit out-of-fold isotonic or
beta calibration over decision family, evidence completeness, OCR agreement,
and fallback usage, then freeze it before looking at validation outcomes.
