# Submission — arthurmichel00

**Solution repository:** `https://github.com/arthurmichel00/mib-doc-solution`

## Summary

**129.14 / 150 official train · 130.57 / 150 held-out 200 · 1 catastrophic false approval (the documented designed trap) · 5.87 s/PDF against a 6.0 budget, 0.36 GiB image.**

An offline, deterministic document pipeline:

- **Trust boundary.** Hidden PDF spans are redacted *before* rasterization, so no downstream contrast step can resurrect injected text, and pages are typed digital-vs-scan. Non-footer text-layer content on scan pages is untrusted by construction; the corpus's hidden "answer key" is never read.
- **OCR ensemble.** Scans go through a pooled multi-pass Tesseract ladder with orientation/deskew retries, a bundled RapidOCR PP-OCRv6 ONNX fallback that fires only when a decision-relevant field is still unread (adopted over v4/v5 by measured A/B: +0.81), and a final measured preprocessing escalation (divide-by-blur / Sauvola / Lanczos-2×) whose reads can only fill unread fields, never out-vote an affirmative read. Behind the escalation, for the four closed-menu fields only, a constrained-candidate channel (`MIB_CTCFILL`) scores every legal value against the recognizer's own frame posteriors with the exact CTC forward algorithm rather than decoding its argmax — a mechanism adapted from a MIT-licensed public solution and credited in `ATTRIBUTION.md`, re-gated on our data and capped below the affirmative-read threshold so no policy rule can consume a fill. Two channels added in this build sit beside it: a generator-inversion reader (`MIB_ABSYNTH`) that renders every legal candidate through a degradation kernel recovered from the damaged row itself and picks by normalized cross-correlation against a census-calibrated margin, which reads rows where no decoder gets usable frames (it recovers MIB-000016's species code and home world, both of which the previous build missed); and an in-house likelihood fusion (`MIB_CTCFILL_FUSION`) that averages each candidate's log-likelihood across preprocessing views and across pages, so the channel decides once on the fused evidence instead of once per view — no new inference, removal-only test-pinned. A fine-tuned Tesseract LSTM (`MIB_TESSFT`; MIT, credited with its sha in `THIRD_PARTY_NOTICES.md`) runs strip-scoped inside the escalation tier, its confidence scaled 0.75 so that the worst invention we could provoke from it on textureless noise still lands below the affirmative-read line; the page-level variant measured ten times over the time budget and was rejected in design, and its individual yield is unproven — it was measured inside the shipped flag-set, never alone. Fields are recovered by label-anchored parsing, closed-vocabulary correction (with fusion/ligature edit costs, a label-licensed truncation-prefix rule for clipped flag rows, and a cross-page sponsor digit vote — the three `MIB_SNAPFIX` repairs), and precedence-weighted cross-page reconciliation in which exact digital lines beat OCR vote-sums (with a decoy-aware guard for names) and trusted adjudicator-note Reason lines are mined for field values (each template 100% gold-verified). A candidate-trained 17 MB CRNN line recognizer (synthetic renders of the corpus's own fonts through a measured damage chain) and a human-audit-derived sponsor strip-weld serve as bounded last-resort readers. Reason-template adjudication (`MIB_REASON_ADJ`), green-stamp rescue (`MIB_STAMP_RESCUE`), `MIB_SNAPFIX`, `MIB_CTCFILL`, `MIB_ABSYNTH`, `MIB_CTCFILL_FUSION` and `MIB_TESSFT` ship enabled, baked into the image's `ENV`; multi-view escalation, the rotation probe, the per-field candidate margin floor (`MIB_CTCFILL_MARGIN` — rejected on measurement in composition: it blocked one wrong fill at the cost of eight right ones), the cross-channel veto (`MIB_XCHANNEL_VETO` — 0 fires across the real 31-slot fill population), two-rail band registration (`MIB_ROWRESTORE` — detector hand-verified 2/2, 0 fires under the shipped configuration), vocabulary user-words and joint-grammar name decode ship disabled (each measured net-negative, value-free, or inert on the final tree).
- **Policy + abstention.** A rule-based policy engine with positive-evidence gates adjudicates: deny rules fire only on affirmative reads, approval requires every outcome-determinative field to be affirmatively read, and under-determined cases (silent flags, unreadable fees) are pinned to NEEDS_REVIEW per the organizer rulings in issues #4/#5. An emission-time consistency guard keeps every APPROVED row free of deny-triggering field values (full disclosure in `MEMO.md`).
- **Calibration.** Confidence is the per-decision-path empirical accuracy with shrinkage, fit out-of-fold and refit at freeze from in-container OCR to close a fit/serve provenance gap.

Runtime: no LLMs/VLMs, no network, no per-case hardcoding.

## How to run

```bash
docker build -t mib-submission /path/to/this/repo
mkdir -p /tmp/mib-output
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="/tmp/mib-output",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

The image accepts exactly two arguments (`<input_pdf_dir> <output_predictions_path>`) and satisfies the full `DOCKER_SUBMISSION.md` contract (`--read-only`, `--network none`, `--cpus 4`, `--memory 8g`, tmpfs `/tmp`). An offline init check runs inside the build harness to guarantee no component attempts a network fetch at scoring time.

Every shipped lever is baked into the image's `ENV` — `MIB_RAPID_MODEL=v6`, `MIB_REASON_ADJ=1`, `MIB_STAMP_RESCUE=1`, `MIB_SNAPFIX=1`, `MIB_CTCFILL=1`, `MIB_ABSYNTH=1`, `MIB_CTCFILL_FUSION=1`, `MIB_TESSFT=1` — so the command above reproduces the submitted configuration exactly, with **no `-e` flags**. The dormant levers stay off unless explicitly set, and the submitted `predictions.jsonl` was generated by this image with no environment overrides.

## How this was built

Flag-gated AI-agent loops with verification in code: 40+ levers built and A/B-measured, 17 shipped, dead ends recorded in an append-only ledger. The operating model is in `MEMO.md` ("How this was built — the operating model"); the per-lever record and evidence detail are in [LEVERS.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/LEVERS.md) and [APPENDIX.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/APPENDIX.md) in the solution repository.

## Scores (official evaluator)

| Metric | Full train (1000) — official, Docker scoring contract | Held-out 200 of train (official metric, scored on the same frozen-image predictions) |
|---|---:|---:|
| **Total** | **129.14 / 150** | **130.57 / 150** |
| Field extraction | 45.51 / 50 | 45.42 / 50 |
| Classification | 66.67 / 80 | 68.00 / 80 |
| Calibration | 16.96 / 20, Brier 0.0760 | 17.15 / 20, Brier 0.0712 |
| Catastrophic false approvals | 1 (documented designed trap, MIB-000865) | 1 (same case) |
| Validity | exit 0, all 1000 rows, zero invalid records | — |

Holdout ≥ train at every measured milestone (126.08 → 127.17 → 128.76 → 129.05 → 129.21 → 129.24 → 129.51 → 130.25 → 130.50 → 130.57), and the single catastrophic false approval is the same documented designed trap at every milestone. Improvement trajectory and per-change measurements are in [APPENDIX.md](https://github.com/arthurmichel00/mib-doc-solution/blob/main/APPENDIX.md).

Runtime under the scoring contract: 5.87 s/PDF, 0.36 GiB image (quiet-box `docker_check`, the fixed 100-PDF subset, budget 6.0; the previous build measured 5.81 — the two reading channels added here cost ~0.06 s/PDF between them, and that cost is disclosed in `MEMO.md` rather than hidden). The same image reads the full 1,000-case train corpus in 5,006 s end-to-end (5.01 s/PDF); we quote the stricter 100-PDF figure. The submitted `predictions.jsonl` was generated by this exact frozen image over all 5,000 validation PDFs under the same offline contract and validated against the manifest. No hidden-text ingestion — the hidden "answer key" is adversarial and is never read. Full approach, failure modes, red-team hardening, and attribution in `MEMO.md`.
