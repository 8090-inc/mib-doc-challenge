# Technical Memo — MIB Doc Challenge

**Author:** patchg  
**Solution freeze:** v12.1 · train score **122.74 / 150** · **0 catastrophic false approvals** · **~4.0 s/PDF** under official Docker limits  
**Runtime:** Offline Docker · Tesseract OCR · classical CV + rules (no network, no cloud APIs)

## Approach

I built a full offline pipeline that turns messy multi-page PDF packets into structured records and a three-way adjudication (`APPROVED` / `DENIED` / `NEEDS_REVIEW`).

**1. Perception.** Each page is rendered (~200 DPI), optionally deskewed and tear-corrected, then OCR’d with Tesseract and merged with the native PDF text layer. Trust filtering strips injection / “answer key” style noise before fields are read.

**2. Structure.** Text is segmented into typed components (form, B-13 biometric slip, fee receipt, registry, sponsor letter). Fields use a three-state evidence model: *read-and-trusted*, *read-ambiguous*, or *not read*. Risk flags are only trusted from B-13 (or labeled flag lines), never invented as `none` from a blank page.

**3. Policy (deny-first).** Manual inspection stamps short-circuit when present. Otherwise FR6-style rules fire on trusted evidence: disqualifying flags, unpaid fees, TRANSIT-7, registry embargo, revoked sponsors (with corroboration), restricted homes. Approvals require a clean, complete evidence signature (including B-13-backed flags none and real fee evidence)—soft defaults used only for extraction emission, never to unlock approve.

**4. Emission & calibration.** After policy, emit-only enrichments improve field strings (name cleanup, hatch → illegible biometrics, fee labels) without changing adjudication. Confidence is mapped by decision reason (deny high, incomplete low) for calibration points.

**5. Ship path.** A single slim image (`Dockerfile` + `run.sh` + `config/default.yaml` + package) runs under `--network none --read-only --cpus 4 --memory 8g` with four workers and OpenMP thread limits so average time stays under the 6 s/PDF budget.

## What worked

- **Safety first:** keeping catastrophic false approvals at zero on full train by refusing soft “packet looks complete → APPROVED” rules.
- **Asymmetric flag recovery:** parse labeled lines such as garbled `Disqualifying risk flag:` and truncated `O flags:` into deny tokens, without free-text answer-key harvest.
- **Sponsor / multi-page corroboration and geometry (deskew/tear)** that improve extraction without special-casing case IDs.
- **Measured plateaus:** PaddleOCR and heavier B-13 multi-ROI on hard flag-miss slices added no new tokens—so we stopped spending budget there.

## Failure modes

| Mode | Symptom | Why it remains |
|------|---------|----------------|
| Blank B-13 / image-only flags | Gold disq flag, we emit `none` or NR | True OCR ceiling on many train residuals |
| Soft fee | Gold paid, we `unknown` | No receipt text; inventing paid would reopen FA risk |
| Gold APPROVED → our NR | Clean-looking fields, no trusted B-13 none | Correct conservative behavior; complete-packet A is FA-toxic |
| Known false denial | e.g. fee OCR as unpaid vs gold paid | Rare; locked with regression tests |
| Name OCR noise | Near-miss spellings | Open vocabulary; cleanup helps tails, not full identity |

## With another week

1. Layout-aware B-13 / fee **panel detection** (classical or tiny offline detector) before OCR—only if a canary slice shows tokens appear under crops we don’t take today.  
2. Stronger **restricted-home / revoked-sponsor** residual when home/SPN are RT but still NR.  
3. Calibration split by incomplete subtype (flags NR vs fee NR) for a small Brier gain.  
4. Broader validation monitoring (latency histogram, missing-case rate) under the 5k-PDF wall clock.

I would **not** spend another week on soft approve paths or train-label hardcoding: the private test set and FA gates make those false wins.

## Design principles

- **Evidence over labels:** no case-ID special cases; rules must fire on text/geometry available at runtime.  
- **Asymmetry:** deny tokens can promote; recovered `none` never opens approve.  
- **Measure before ship:** full-train Docker freeze under challenge flags before submission.
