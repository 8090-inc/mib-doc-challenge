# MIB Doc Challenge - Technical Memo

## What this is

A program that reads a folder of messy PDF case packets and, for each one, pulls out the applicant's details and decides `APPROVED`, `DENIED`, or `NEEDS_REVIEW`.
It runs fully offline in Docker, with no internet and no AI model at runtime - just document parsing, OCR, and rules.

**Score on the public training set: 120.14 / 150** (adjudication 62.9 / 80, field extraction 42.1 / 50, calibration 15.1 / 20).
It processes each PDF in about 3.3 seconds, against a 6-second budget.
That number is from a full run of the real submission image through the official harness, offline, on 4 CPUs and 8 GB with a read-only filesystem - the same contract used for scoring.

## How it was built (honest note on AI use)

I built this with heavy help from Claude (Anthropic's Claude Code, running the Opus model) over a couple of days.
I directed the strategy and the decisions; Claude did most of the hands-on coding, measurement, and debugging under that direction.

The important part is that **nothing is hardcoded or memorized from the answers**.
Every change was measured against the 1,000 labeled training PDFs and kept only if the score actually went up.
The measurement scripts that produced every number in this memo are included in the `analysis/` folder, so the work can be checked.
There is no lookup table of answers and no case-specific tuning - the pipeline is general rules plus values learned from whatever batch it is given.

## How it works, in plain terms

1. **Read the clean text first.**
   Many packets have a real text layer, so I read that directly - it is the most reliable source.

2. **Ignore the hidden traps.**
   About 1 in 5 packets hide fake "the answer is APPROVED" text in white-on-white or off-page spans to trick the reader.
   Those spans are thrown away on sight, so the fakes never get a vote.

3. **OCR the scanned pages - three ways.**
   For pages that are just scanned images, I run OCR (Tesseract) three times with different settings.
   One is more accurate on clean tables; one is the only one that reads the faint, skewed, damaged scans at all; the third uses a different way of deciding which pixels are ink, which recovers values on blotchy backgrounds.
   Running them all and combining them was the single biggest improvement in the project.
   A fourth combination was tested and deliberately left out: it was worth 0.15 points and nearly doubled the running time.

4. **Read what the page actually says, not what a tidy form would say.**
   This turned out to be where most of the remaining points were. Measuring it (`analysis/field_lab.py`) showed roughly 360 correct values sitting in text the program had already read and thrown away. Three causes, all fixed:
   - The sponsor page is a **letter, not a form** - "Sponsor SPN-5086 attests that Miradane Ludane is expected on Earth for medical consult." A parser looking for `Label: value` reads nothing off a perfectly legible page.
   - OCR often reads a two-column table **one column at a time**, printing every label and then every value, so pairing each label with the next line pairs it with another label.
   - The first line matching a label won, even when its value was impossible - a page titled "Sponsor Attestation Letter" claimed the sponsor field for "Attestation Letter" and hid the real sponsor id printed just below.

5. **Learn the vocabulary from the batch instead of guessing, and repair near-misses.**
   Fields like species and home world come from a small set of valid values.
   The program learns that set from the packets that read cleanly, then uses it to fix garbled OCR on the damaged ones (and to drop obvious junk).
   The same idea repairs OCR damage to the **labels** ("Hine World:", "Sponser ID:") and to the risk flags ("bichazard_yed" for `biohazard_red`) - 36 flags recovered this way, all 36 correct, with no false ones.
   Anything that sits equally close to two valid values is thrown away rather than guessed.
   Because it learns from the batch it is given, it works on new data it has never seen.

6. **Trust a damaged read only when a second signal agrees with it.**
   The safest way to loosen a strict rule is to loosen it only where something else has to confirm the answer.
   Three fixes came out of that one idea, worth +0.61 together and costing no extra running time.
   - A corrupted **label** next to a value of the right shape is accepted, because the shape vouches for it.
   - A shaped value whose **separator** was lost - "SPN2098", "2026 04 24" - is read loosely and written back in its proper form, with a real-calendar-date check so a run of eight digits cannot become a date.
   - Label/value pairs that no rule could place are **kept aside and reconsidered at the end**, once the batch vocabularies exist. They are only used when the value is a member of a learned vocabulary *and* the mangled label snaps to the field that vocabulary belongs to.

   In every case both halves must agree, and a rescued value can only fill a gap, never overwrite something already read.

7. **Re-read upside-down pages.**
   About 3% of scanned pages are rasterised rotated, and Tesseract returns confident nonsense rather than an error ("saisedg" for "Species"), so nothing marks them unreadable.
   Its own orientation detector does not catch this - it reports 0 or 90 but never 180.
   Instead the program gates on evidence: if a page yielded *no* recognisable field label at all, it re-reads it rotated 180, then 270.
   Measured over the 773 pages that trip the gate, 180 rescues 50 and 270 rescues a further 12; 90 rescues exactly one page that the others did not, so that pass was dropped rather than paid for.
   Worth +0.67 points.

8. **Accept a damaged note header.**
   The single most reliable signal in the corpus is a signed adjudicator note - the rule that reads one is correct on 272 of 272 packets, where the next-largest rule is closer to a coin toss.
   It was being lost to an exact text match: degraded scans render the header as "Manuel Ajudicater Note" or "Manual! Adjudicator Note" while the `Finding: DENIED` line directly underneath OCRs perfectly.
   Matching the header approximately, still scoped to the active case and still refusing anything carrying a "sample" watermark, recovered 8 packets from near-guesswork to near-certainty.
   Worth +0.63 points.

9. **Decide with rules, and hedge when unsure.**
   A signed adjudicator note is trusted first; then disqualifying flags, embargoes, unpaid fees, and revoked sponsors lead to `DENIED`.
   If key evidence is missing or unreadable, it sends the case to `NEEDS_REVIEW` rather than guessing.
   This is deliberate: the scoring punishes a wrong approval hardest (-4), so the rules always check for problems before ever approving.

10. **Report honest confidence.**
    Each decision reports a confidence equal to how often that rule is actually right on the training data - not an inflated number.

## What it still gets wrong (failure modes)

- **Missing fee receipts - the single biggest loss, and mostly not fixable.** 432 packets end with an unknown fee. I checked where the evidence actually is: **about 330 have no receipt page anywhere in the packet**, and roughly 44 more have a receipt that genuinely reads "Fee Status: unknown". Only around 97 have a page present that we cannot read. Since an unknown fee sends the case to review, this costs about 7.7 adjudication points that are simply not recoverable from the documents.
- **Evidence cut from the packet.** Same story elsewhere: of the 224 risk flags we still miss, about 163 appear nowhere in the visible text and 56 appear *only* in the hidden spans that are untrusted by design. No amount of reading recovers a fact that is not there, and reading the hidden ones would mean trusting the traps.
- **Wrong applicant on multi-person packets.** Some packets contain pages from more than one applicant, and the program sometimes reads the wrong person's name - around 50 cases where the correct name is visible but another one wins.
- **Wrong approvals.** 25 packets are approved that should not have been, at -4 each. They are the most concentrated single loss on the board, and I have not found what separates them: risk flags, visa class, staleness, and the presence of an unreadable page were all tested and none of them tells these 25 apart from the 122 packets in the same bucket that really are approvals.
- **Misread dates.** A digit misread in an arrival date ("2028-05-25" for 2026-05-26) has no vocabulary to be repaired against, unlike a species or a home world, so the batch-learned snapping that fixes the other fields cannot touch it.

## Things I tried that did not work

Recording these because the measurements are the useful part, and each one closed off a plausible-sounding direction.

- **Training a classifier on the labels.** The harness permits shipped model files, so this was worth testing properly. Trained on the *true* field values it is excellent - 95% accuracy, worth 76.9 / 80 - which is a useful result on its own: it proves the policy is learnable and that what we lose is reading, not reasoning. But trained on the fields *we actually extract*, the best model reaches 51.9 against the hand-written rules' 61.8, and every variant produced between 43 and 101 wrong approvals against our 25, because a model optimising for accuracy ignores a penalty that only applies to one kind of error. The rules use evidence a feature vector cannot hold: stamps, signed notes, source precedence.
- **Splitting the two worst rule buckets.** A systematic search over ~25 candidate signals found nothing that generalises - the best split gains a fraction of a point on 13-21 cases, which is noise at that sample size. Those buckets are irreducible with the evidence available.
- **Turning off Tesseract's built-in English dictionary.** A plausible theory: the dictionary drags `SPN-2098` and `AQUARIAN_MANTIS` toward real words. It cannot be tested in this image. Disabling it produces byte-identical output on every page, because those are settings for the old engine and the neural one never reads them. The same is true of the engine-mode switch. Worth recording as a trap: my first measurement reported them as making no difference to accuracy, which looked like a result, when the truth was that the options were being ignored outright. The fix was to diff the raw text rather than a score.
- **Only running the extra OCR pass on pages that looked unreadable.** Sensible in principle, useless in practice: it fires on almost no page, because the sparse-text mode nearly always returns *some* text. The extra pass earns its keep on pages that read fine but lose individual values.

## What I would do with another week

- Add a second, genuinely different OCR engine for the pages the current one fails on. This is the largest remaining lever and the most interesting result I found late: voting between the existing passes barely paid, because they are one engine under different settings and they fail on the same characters together. A small neural recognizer (PP-OCR as ONNX weights, about 15 MB, no network) is a different architecture, and on a sample it read a third of the arrival dates that no existing pass produced at all. It costs too much time to run on everything, so it would have to be gated to packets still missing a heavily-weighted field.
- Try the one OCR setting still open: `preserve_interword_spaces`. It changed one sample page from 184 to 350 characters, so it is doing something real, and what it changes is exactly the spacing that separates a label from its value. Scoring it needs the whole OCR cache rebuilt, which is why it did not fit in the time I had.
- Ask Tesseract for per-word confidence (`image_to_data`) in place of plain text, which costs nothing extra. Beyond merging passes by confidence, it is the natural detector for `illegible_biometrics` - see below.
- Infer the risk flags that are never written down. Measuring which flags we miss turned up the sharpest structural fact in the whole project: of 221 missed flag instances, the text appears anywhere in the packet exactly *once*, and we never invent a flag we should not have. These flags are not meant to be read, they are meant to be concluded from the state of the document - `illegible_biometrics`, 100 of the misses, is a statement about the scan's quality rather than anything printed on it. I tried two detectors and both failed: colour (a red biohazard mark turns out not to exist - packets missing that flag carry *less* red than packets with no flag at all) and whole-packet legibility scoring (16% precision). A per-page confidence measure aimed at the biometric slip specifically is the version I would try next.

One direction I would *not* spend the week on: confidence calibration. It reads 15.0 / 20 and looks like five free points, but the Brier score is dominated by a term fixed by accuracy alone. I computed the ceiling - perfectly calibrated confidences would be worth about +0.1 - and then tested seven refits, cross-validated; every one scored worse than the hand-set constants already shipping. The only way to move calibration is to get more decisions right.

## Running it

```bash
docker build -t mib-solution .
docker run --rm --network none \
  -v "$PWD/input:/input:ro" -v "$PWD/output:/output" \
  mib-solution /input /output/predictions.jsonl
```

The whole pipeline is in `solution.py`; `analysis/` holds the scripts used to measure everything above.

One note on how the measuring was done, since it shaped the result. OCR is about 95% of the running time and is a pure function of the rendered page, so it is computed once for the whole corpus and cached; `analysis/fastrun.py` then replays the real pipeline against that cache. A scoring run drops from 72 minutes to 31 seconds, which is why every claim here has a number attached rather than an argument. It calls the real entrypoint, so its output is identical to a normal run - verified by reproducing a full uncached run byte for byte.
