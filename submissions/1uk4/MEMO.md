# MIB Doc Challenge — Technical Memo

## Results

The system scores **118.56 / 150** on the full training set of 1,000 labeled packets, measured with the official evaluator. On a fixed 800/200 train/val split it scores **118.46 on train and 118.94 on val**. It produces **15 catastrophic false approvals**. All 5,000 validation records were emitted schema-valid with zero missing cases. Runtime is **3.5 seconds per PDF** in a single 4 vCPU container. The image is 0.26 GiB and runs fully offline on the Python standard library, Pillow, and Tesseract.

## How the system was built

The system went through four versions.

Version 1 used only the standard library and scored 103.48. It built the rule catalog, with every rule tagged by provenance: stated in the Field Manual, or inferred from training data. Its closing audit showed that none of the remaining 22 false approvals had any signal in the text layer. The disqualifying flags live in images.

Version 2 scored 104.98 by adding OCR as a safety check that runs only when the rules want to approve.

Version 3 grew into the layered pipeline and reached 118.08. An OCR quality bundle added 10.71 points and cut false approvals from 22 to 15. Every rule's accuracy was then measured directly, and every confidence value was recalibrated to its measured frequency. The main approve rule claimed 0.94 confidence but was right 69% of the time. Fixing that class of overconfidence was worth roughly 3 points on its own.

Version 4 rebuilt the pipeline as a standalone package. It was proven byte-identical to its predecessor on all 1,000 packets before any improvement was attempted. After that, changes were accepted only through a measurement gauntlet, and the system finished at 118.56.

## Architecture

The pipeline has seven layers. Layers 1 through 5 establish what the packet says. Layers 6 and 7 decide what to do about it.

Layer 1 enumerates the PDF text streams and images. Layer 2 decodes text and runs pooled multi-pass OCR, concatenating the outputs so that whichever pass read a field legibly wins at extraction. Layer 3 is the trust boundary, and trust is decided exactly once. Sanitizers strip injection payloads and redaction placeholders, and an illegibility detector excludes garbage OCR. Layer 4 emits typed signals weighted by the Field Manual's evidence hierarchy, from adjudicator notes at the top down to the bare text layer at the bottom. Layer 5 consolidates the signals. The highest authority wins, and disagreements and per-field provenance are preserved for the decision layers.

Layer 6 is a strict-priority rule chain. A signed adjudicator finding trumps everything, and it was correct on all 162 training cases that carry one. Hard denials fire before the extraction fallback, so a half-readable packet can still be denied on its readable half. Layer 7 applies nine named policy stages: three upgrades, one trust bypass, and five guards. The guards can only demote an approval to review. The system cannot manufacture a denial from suspicion alone.

## Decisions shaped by reading the scorer

Ambiguous cases route to review. Each contested rule bucket's action was verified as expected-value optimal against its measured truth distribution. Every packet emits a schema-valid record. Every confidence value is a lookup in a single registry, and each value is that bucket's measured accuracy, including 0.34 on the 251-case extraction-failure fallback. A completeness test verifies that every tag the pipeline can emit has a registry entry. The registry also served as the error map: the lowest-accuracy buckets marked where the score was being lost, and optimization work was aimed there. The 0.34 fallback bucket led to the fee-extraction investigation, which decomposed the bucket case by case and established that the missing evidence is absent from the packets themselves.

## Adversarial content

Hidden text never becomes evidence. The injection sanitizer fires on 98% of packets, because planted SYSTEM payloads are ambient in this corpus. The illegibility detector excludes 19% of images. Redaction placeholders are stripped at layer 3, with a second check at layer 4 that caught 9 survivors. Because trust is settled before extraction, no downstream rule needs its own defenses. A hidden answer key can neither fill a field nor flip a verdict, and the Manual's traps fail because a denial always requires positive visible evidence.

## Measurement discipline and failure modes

The v4 rewrite was gated on byte-identity rather than score-matching. The same code produces 145 different rows under two Tesseract versions while the aggregate score moves only 0.10, so a score-tolerance gate would have passed a changed system. Every candidate improvement ran a full-set measurement, the fixed split with validation never tuned against, a false-approval count, and per-case diff attribution. One change was accepted: a sparse-text OCR pass worth +0.37 on train and +0.90 on val. The rejected changes are retained in the code as documented negatives, switched off: fee recovery that gained on train but lost on val, page rotation and deskew passes that measured at +0.02 and −0.01 at their ceilings, and a defensive downgrade that catches all 15 false approvals by spending 76 correct approvals.

The same measurements bound what remains. About 95% of the extraction loss is on evidence that is absent from the packets, mainly risk panels and fee receipts removed by the generator. The 15 false approvals are structurally undetectable, since the disqualifying flag appears nowhere visible and proxy rules downgrade roughly five correct approvals for every one they catch. The engine-version drift above also flips 7 verdicts, so the container is the canonical artifact.

## With another week

Classification holds the largest headroom: 62.5 of 80, with the loss concentrated in rule buckets the deterministic chain cannot split further. The first project would be a small calibrated classifier blended over the rule prior for exactly those buckets, trained on extraction and document-quality features, with the existing rules kept as the fallback path and the false-approval count as a hard acceptance gate. The second is a taxonomy of the roughly 330 fields where a value was extracted but wrong, which the per-field audit bounds at about 1.5 points, addressed by targeted normalizers per error class. The third is calibration refinement: four guards currently share one 0.65 confidence, and measuring each guard's accuracy individually would sharpen Brier at no classification risk. The fourth is engine robustness: 249 images sit within 0.05 of the illegibility threshold, which is the main driver of the cross-version drift, and measuring that boundary under multiple Tesseract builds would either stabilize it or justify pinning it.

## Reproducibility

A clean checkout builds and runs with Docker alone. There are 159 unit tests, committed golden outputs with a byte-parity gate, and every number in this memo has a committed measurement script and a dated ledger entry in the repository, for accepted and rejected experiments alike.
