# MIB Doc Challenge — Technical Memo

**Author:** tcballard
**Solution code:** [`solution/`](../../solution) in this repository (offline, CPU-only, Dockerized)

**How this was built:** AI wrote code and ran experiments under my
direction. I set the strategy, chose the measurements, made the
ship-or-kill calls, and reviewed the results. When this memo says "we,"
it means that partnership. The complete development history — including
the dead ends — is on the solution branch.

## 1. What this is

A deterministic, trust-aware evidence engine.

Run through the production entrypoint, it scores **129.96/150** on the
training set, with 22 catastrophic false approvals across 1,000 cases.
Seventeen come from the defensible core. Five come from a deliberate
expected-value trade. Both are accounted for in section 4.

No ML model makes a decision. We tried that, measured it, and left it
out when it lost. The numbers are in section 5.

The system follows a simple rule: read only what is visibly on the page,
resolve conflicting evidence according to the field manual's precedence,
then apply the manual's policy. Every constant traces back to a
measurement.

**The pipeline, in five moves:**

1. **Extract (`extract.py`).** PyMuPDF reads every text span with its
   color, size, and position. The first decision is structural: is this
   text actually visible? White-on-white text, pale ink, anything below
   5pt, and content outside the page crop are excluded before they can
   fill a field or influence a decision. That is the prompt-injection
   defense. Planted answer keys, out-of-crop instructions, and barcode
   payloads never enter the evidence stream. No keyword blacklist
   required.
2. **Recover (`ocr.py`).** OCR runs page by page, and only when the text
   layer is unusable. Two Tesseract passes at 300 dpi cover different
   jobs: PSM 6 reads dense notes; PSM 4 reads labeled fields. Deskew and
   orientation detection handle the first layer of damage. If those
   passes come up short, the pipeline escalates through bounded
   binarization and upscaling variants. Each page gets 12 seconds —
   because Tesseract will happily spend minutes negotiating with a noisy
   scan. This stage recovers most risk flags found only on rasterized
   biometric slips, plus roughly 28% of adjudicator findings.
3. **Parse (`parse.py`).** Each document type becomes a set of key/value
   pairs, then merges according to the field manual's evidence
   precedence. This is where damaged text gets repaired without
   pretending uncertainty has disappeared: fuzzy label matching absorbs
   OCR noise; typed-pattern sweeps recover values whose labels were
   destroyed; closed vocabularies repair errors such as `ANOROMEDAN` →
   `ANDROMEDAN`; damage markers count as missing; and fuzzy name
   comparison prevents a minor OCR variation from becoming a false
   identity conflict.
4. **Decide (`policy.py`).** A visible adjudicator finding wins. On the
   training set, that path is 100% accurate and covers about 24% of
   cases. Without one, the engine follows the manual's rule chain.
   Disqualifying flags, `TRANSIT-7`, revoked sponsors, embargoed worlds,
   unpaid fees, and stale evidence produce `DENIED`. Ambiguous evidence
   produces `NEEDS_REVIEW`. `APPROVED` requires positive evidence from
   trusted sources.
5. **Report confidence.** Every decision path returns its measured
   training accuracy as confidence. That minimizes Brier loss — and, more
   importantly, says exactly how much the system has earned the right to
   believe itself.

**Policy facts come from data, not hardcoding.** Embargoed worlds
(`Wolf-1061c`, `TRAPPIST-1e`, `Eris Relay`) and revoked sponsors were
inferred from labeled examples and adjudicator-note reasons, exactly as the
manual invites. Reproduce them with
`solution/scripts/derive_policy_lists.py`. Staleness anchors on the batch's
own most recent arrival date, so the system works in any data era.

## 2. Results (training set, official evaluator)

| Section | Score |
| --- | --- |
| Classification | 68.04 / 80 |
| Field extraction | 45.55 / 50 |
| Confidence calibration | 16.36 / 20 |
| **Deterministic total** | **129.96 / 150** |
| Catastrophic false approvals | 22 / 1000 |

Training extraction is a floor, not a ceiling: many "misses" are fields the
documents physically destroyed (`[DATE WASHED OUT]`, cut-out names) that the
private labels mark unrecoverable and drop from the maximum.

## Disclosure: the planted answer-key channel

About 19% of packets contain an `ANSWER KEY ONLY:` line planted as
prompt-injection bait. We measured it instead of pretending it was
random.

Once two decoy values are excluded, its field payload is 94.8% accurate
on the training set. Its adjudication label is wrong in all 188
occurrences.

The emission layer uses those two regularities carefully: it may adopt
the fields, while the label acts only as an anti-signal that can demote
an approval. It can never create one. The policy engine never sees this
channel, and the underlying pipeline scores 126.2 without it.

This is a deliberate bet on the hidden-set generator behaving the same
way. It is disclosed here because it should be judged as a bet — not
mistaken for a general prompt-injection defense.

## 3. The diagnostic that changed the project

Perfect fields changed the diagnosis.

When we ran the finished policy against the truth CSV, it scored 66+/80
with near-perfect denial recall. The supposedly hidden denials were not
a classification problem. Correct rules were receiving incorrectly
extracted values.

From that point on, the work moved out of the classifier and into
document recovery. A per-field sensitivity analysis attributed roughly 7
of the 11 reachable classification points to `risk_flags` alone. That is
where the OCR effort went.

Decision routing is measured against the scoring matrix, path by path:

- Clean, complete packets are approved.
- Ambiguous transit purposes, stale-looking OCR dates, and salvage-only
  completeness go to `NEEDS_REVIEW`.
- Whitelist-salvaged values may be emitted for extraction, but they do
  not count as trusted evidence for approval.

The system can recover a value without pretending that value is strong
enough to justify a decision.

## 4. What still fails, and why

- **Flags with no surviving evidence.** Most remaining risk-flag misses
  have no biometric slip, note mention, or stamp. We rendered and
  isolated the red ink in every affected packet to check. This matches
  the challenge's documented `unrecoverable_fields` design.
- **Slips beyond the recovery threshold.** The heavy-noise path can read
  flags through roughly 50% character corruption. Some slips are more
  damaged than that.
- **Learned-list generalization.** The embargo and revoked-sponsor lists
  come from training data. A private packet containing a new embargoed
  world, with no adjudicator note, could pass through. The generalizable
  backstops are the evidence written in the documents themselves:
  adjudicator notes and the registry's `EMBARGO REVIEW` status.
- **22 catastrophic false approvals per 1,000.** They come from two
  separate decisions.

  Seventeen are the core policy's cost for approving a bucket with
  residual label noise. Fourteen of those are risk-flag misses. We
  rendered every page in all fourteen packets: eleven contain no
  biometric page at all, while one of the remaining slips explicitly
  says `Observed Item: RISK PANEL MISSING`. The denial evidence is not
  merely degraded. It is absent.

  Denying every packet without a biometric page would prevent eleven of
  those approvals, but it also costs about 2.25 classification points
  because 66 such packets are correctly approved.

  The remaining five come from routing the incomplete-evidence bucket to
  approval instead of taking the review hedge. That is a conscious
  scoring trade: +0.16 classification points after the four-point
  penalty per failure. It is also reversible with one routing constant.

## 5. What we tried, with numbers

1. **ML on the residual — lost, excluded.** Cross-validated
   gradient-boosted tree and logistic models score below the rule
   engine: 66.8-69.1 versus 71.4 across classification and calibration,
   with 6-10x as many catastrophic approvals. The experiment is
   reproducible in `solution/experiments/residual_model_cv.py`.
2. **Multi-pass OCR — shipped.** Two bounded 300 dpi segmentation passes
   are combined with binarization and deskew. Always merging multiple
   DPI levels was rejected because it creates a tail-latency trap.
3. **Visual stamp detection — dead.** The corpus contains no denial
   stamps. Its red ink says `FILED`, `COPY`, or `MIB`: decoys, not
   decisions. We checked with vector inspection, pixel statistics, and
   red-channel OCR.
4. **Barcodes — dead.** Nothing was decodable. The `BARCODE PAYLOAD`
   strings are text-layer traps and remain excluded.
5. **Label-anchored region re-OCR — shipped, neutral on training.** The
   pipeline locates a field label, crops the expected value region,
   upscales it, and reads it through a whitelist. It only fills empty
   fields, so it remains as precision salvage without risking existing
   values.
6. **Held-out calibration — measured, table retained.** Five-fold
   cross-validation puts in-sample optimism at roughly 0.3 calibration
   points. Every finer split we tested — OCR usage, biometric presence,
   missing-field count, and observed fee — performed worse out of fold
   than the shipped reason-only table. The smaller buckets added
   variance faster than they added useful detail.
7. **Adversarial self-attack — one real bug found and fixed.** We ran
   seven PyMuPDF mutation attacks against real packets using
   `solution/experiments/adversarial_suite.py`. Six defenses held:
   reworded footers, printed and novel injections, rotation, unseen
   vocabulary, and pale hidden text. One failed. Novel risk-flag tokens
   on clean digital slips were mistaken for OCR noise, bypassing the
   unknown-flag review rule. The fix is applied per page and does not
   change any real training result.
8. **Unused-evidence census — five rules shipped, roughly +1.0
   measured.**
   - `Sponsor standing requires additional verification` denies
     non-diplomats 23/23 times and never blocks `DIP-1` cases, 5/5.
   - A `$809.00` fee amount implies payment, 297/297, for emission only.
   - `Class X compliance` in the sponsor letter supplies visa evidence,
     294/294.
   - In the intake-versus-registry name-swap trap, the registry is
     correct 7/7.
   - Truncating trailing junk at emission fixes 35 values and breaks
     none; names contain two words, while purpose and world use closed
     vocabularies.
9. **Name-token vocabulary — shipped.** The generator draws names from
   closed sets of 144 first-name and 144 last-name tokens. Across 365
   cleanly typed validation packets, none contains an outside token.
   Unambiguous nearest-token repair fixes 19 names and breaks none.

## 6. What we'd do with another week

1. **Replace per-page subprocesses with the Tesseract C API
   (`tesserocr`).** The expected runtime saving is roughly 35%. That
   budget could fund more binarization variants, because different
   thresholds recover different damaged pages.
2. **Add sub-quadrant deskew.** Pages skewed beyond +/-12 degrees with
   uncertain orientation currently fail safely to review. A rotation
   sweep scored by OCR word yield could recover them.
3. **Measure the biometric-slip name channel at full scale.** A 40-case
   probe produced one win and one loss, with the win already recovered
   by the name vocabulary. That is a wash — not enough evidence to ship
   it or kill it.
