# MIB Doc Challenge - Technical Memo

## What this is

A program that reads a folder of messy PDF case packets and, for each one, pulls out the applicant's details and decides `APPROVED`, `DENIED`, or `NEEDS_REVIEW`.
It runs fully offline in Docker: no network, no LLM, no model files, just PDF parsing, OCR and rules.

**Public training set: 120.14 / 150** (adjudication 62.9 / 80, extraction 42.1 / 50, calibration 15.1 / 20) at **3.3 s/PDF** against a 6-second budget, measured on the real submission image through the official harness under the scoring runtime.

Built with heavy help from Claude Code (Opus): I directed the strategy and the decisions, it did most of the hands-on coding and measurement.
Nothing is hardcoded or memorised from the answers.
Every change was scored against the 1,000 labelled PDFs and kept only if the number went up, and `analysis/` contains the scripts behind every figure below.

## How it works

1. **Text layer first, traps discarded.** About 1 in 5 packets hide fake "the answer is APPROVED" text in white-on-white or off-page spans. Those spans are dropped on sight, so hidden text never gets a vote.

2. **Three OCR passes on rasterised pages.** `psm 3` reads cleanly scanned tables, `psm 11` is the only one that reads faint and skewed scans at all, and Sauvola binarisation recovers values on blotchy backgrounds. They merge by rank, so a later pass can only fill a gap, never overwrite. A fourth pass was measured and dropped: 0.15 points for nearly double the runtime.

3. **Read what the page says, not what a tidy form would say.** This was the largest pool of loss - roughly 360 correct values sitting in text already read and thrown away. The sponsor page is a *letter*, not a form. OCR reads two-column tables one column at a time, so pairing each label with the next line pairs it with another label. And the first line matching a label used to win even when its value was impossible, so a page titled "Sponsor Attestation Letter" claimed the sponsor field.

4. **Learn the vocabulary from the batch.** Species, home worlds and flags come from small closed sets. The program learns them from the packets that read cleanly, then repairs garbled ones against them - 36 corrupted risk flags recovered, 36 of 36 correct, zero false positives. Anything sitting equally close to two valid values is dropped rather than guessed.

5. **Trust a damaged read only when a second signal agrees with it.** A corrupted *label* is accepted when the value has the right shape; a value whose separator was lost ("SPN2098", "2026 04 24") is re-emitted in canonical form; label/value pairs no rule could place are reconsidered at the end against the learned vocabularies. Both halves must agree, and a rescued value can only fill a gap. Worth +0.61.

6. **Re-read upside-down pages.** About 3% of scanned pages are rasterised rotated, and Tesseract returns confident nonsense rather than an error, so nothing marks them unreadable - its own orientation detector reports 0 or 90 but never 180. So the gate is evidence: a page that yielded no recognisable field label is re-read at 180, then 270. Worth +0.67.

7. **Decide with rules, and hedge when unsure.** A signed adjudicator note is authoritative and is correct on 272 of 272 packets; then disqualifying flags, embargoes, unpaid fees and revoked sponsors. Missing or unreadable evidence goes to `NEEDS_REVIEW` rather than a guess, because a wrong approval is penalised hardest (-4). Reported confidence is how often that rule is actually right on training data, not an inflated number.

## What it gets wrong

- **Missing fee evidence, and mostly not fixable.** 432 packets end with an unknown fee. About 330 have no receipt page anywhere in the packet and about 44 carry a receipt that genuinely reads "unknown"; only around 97 are pages we fail to read. That is roughly 7.7 adjudication points that are not in the documents.
- **Flags that were never printed.** Of 224 missed risk flags, about 163 appear nowhere in visible text and 56 appear only in the hidden spans that are untrusted by design. `illegible_biometrics` is a statement about a scan's quality, not something written on it.
- **25 false approvals.** The most concentrated single loss, and I did not find what separates them: risk flags, visa class, staleness and the presence of an unreadable page were all tested, and none tells these 25 apart from the 122 packets in the same bucket that really are approvals.
- **Wrong applicant on multi-person packets** (~50 cases), and **misread digits in dates**, which unlike a species or home world have no vocabulary to be repaired against.

## Measured dead ends

- **A trained classifier loses to the hand-written rules.** On the *true* field values it is excellent - 95% accuracy, 76.9 / 80 - which proves the policy is learnable and that what we lose is reading, not reasoning. On the fields we actually extract, the best model reaches 51.9 against the rules' 61.8, and every variant produced 43 to 101 false approvals against our 25, because a model optimising for accuracy ignores a penalty that applies to one kind of error.
- **Character-level voting across OCR passes is worth exactly zero.** In every field, the count of cases where no pass is right but a per-character majority reconstructs the truth is 0. One engine's passes fail on the same glyphs. Only choosing between whole values pays.
- **Recalibrating confidence.** It looks like five free points, but the Brier term is dominated by accuracy: perfect calibration is worth about +0.1, and seven cross-validated refits all scored worse than the constants already shipping.

## What I would do with another week

- **A second OCR engine of a genuinely different architecture** (PP-OCR, ~15 MB of ONNX weights, fully offline). A gated prototype measured +0.47 and read a third of the arrival dates no Tesseract pass produced at all, but it cost 4.6 s/PDF and pushed false approvals from 25 to 27, so it did not ship.
- **Ask Tesseract for per-word confidence** (`image_to_data`) instead of plain text. It costs nothing extra and is the natural detector for `illegible_biometrics`.
- **Infer the flags that are never written down**, where 100 of the misses are. Two detectors were tried and both failed: colour (packets missing the biohazard flag carry *less* red than packets with no flag) and whole-packet legibility scoring (16% precision).

## Running it

```bash
docker build -t mib-solution .
docker run --rm --network none \
  -v "$PWD/input:/input:ro" -v "$PWD/output:/output" \
  mib-solution /input /output/predictions.jsonl
```

One note on method, because it shaped the result: OCR is about 95% of runtime and a pure function of the rendered page, so it is computed once per corpus and cached, and `analysis/fastrun.py` replays the real pipeline against that cache. A scoring run drops from 72 minutes to 31 seconds, which is why every claim above has a measurement behind it rather than an argument.

Unknown fields are emitted as sentinels (`SPN-0000`, `1900-01-01`) because the submission schema requires those patterns and does not accept an empty string.
