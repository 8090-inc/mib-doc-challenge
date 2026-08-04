# Attribution

The challenge rules permit reusing public solution code or ideas where the
licence allows, with clear attribution. This solution is original work, with
the following exceptions.

## tylergibbs1 / mib-doc-challenge-solution (MIT)

Source: <https://github.com/tylergibbs1/mib-doc-challenge-solution>, MIT
licensed. One idea was adapted after reading that repository; no code was
copied.

1. **Closed-vocabulary pixel decoding of damaged scans** -- their
   `mib/pixmatch.py` frames reading a degraded scan as *hypothesis scoring*
   rather than recognition: since each field takes one of a small set of legal
   values, correlate a template of each candidate against the page and rank by
   normalised cross-correlation, which removes gain and offset so washout
   barely moves the ranking. Their docstring cites Kopec & Chou's document
   image decoding (under i.i.d. speckle the matched filter is the ML decoder).

   This mattered because our own closed-set attempt had failed the opposite
   way: `tools/labs/flags_lab.py` cropped the risk panel and ran Tesseract on
   it, producing 0 usable reads from 2,948 crops (`ie ma il eg` against a truth
   of `illegible_biometrics`). Those pixels contain nothing an OCR engine can
   segment. Correlation needs no legible characters, and a sliding correlation
   also searches every offset -- which sidesteps the unregistered-form problem
   that made our `region_probe` measurably negative (−0.53 / −0.44), since the
   scanned form's anchor rows spread 54 points where the text layer has sd 0.00.

   Our implementation is in `tools/labs/pixmatch_lab.py` and is written from
   the described idea. We harvest templates empirically, as they do, but from
   the selection half of the corpus only, so the confirmation half is scored by
   a bank that never saw it.

## strobl / mib-doc-solution (MIT)

Source: <https://github.com/strobl/mib-doc-solution> (commit `d6752ec`), MIT
licensed. Two ideas were adapted after studying that repository; no code was
copied verbatim.

1. **Trace-keyed hierarchical confidence** -- `mibdoc/tracecal.py` adapts the
   back-off structure of their `mib_pipeline/confidence.py`: estimate
   P(answer is correct) per rule trace, backing off
   `global → decision → decision|primary reason → decision|full reason set`
   with Bayesian shrinkage toward each parent. Our implementation is written
   from the described structure and blended with our own posterior-shape
   estimator, which measured better than either alone on our pipeline.

2. **Tesseract `--dpi` hint** -- `mibdoc/ocr.py` passes the true render
   resolution to Tesseract rather than letting it infer one from the PNG
   header, following their `TesseractOcrEngine.read_page`.

3. **A second OCR engine as independent evidence** -- studying their
   engine-abstraction layer prompted us to reconsider how our RapidOCR pass was
   wired. Ours had been merging the second engine's label/value pairs into the
   primary page with `setdefault`, which meant a *wrong* value from the first
   engine permanently blocked a correct one from the second. It now resolves as
   an independent evidence set overlaid only onto fields the primary pass left
   unknown. The re-wiring is ours; the framing of engines as interchangeable
   readers rather than a fallback chain came from reading their code.

Note that `mibdoc/tracecal.py` is fitted and reported during training as a
calibration candidate, but the blend it feeds was not selected on the final
model, so it does not affect inference. It is retained because the comparison
it enables is reported in MEMO.md section 7.

Ideas from that repository that we evaluated and did **not** adopt, because
measurement on our pipeline did not support them, are recorded in `MEMO.md`
under "What did not work".

## arvindcr4 / mib-doc-challenge (MIT)

Source: MIT licensed. One idea was adapted; no code was copied verbatim.

1. **Tolerant "Finding:" matching** -- `mibdoc/notes.py::FINDING_RE` follows the
   approach in their `src/mib/parse.py` of accepting OCR-damaged spellings of
   the literal and of the verdict itself (`Findino`, `APPROVEO`, `DENIEO`,
   `HEEDS REVIEW`). Measured on our pipeline, the tolerant form recovers 19
   findings the strict one misses, 19 of 19 correct.

## Fuzzy risk-flag recovery

`mibdoc/globalscan.py::fuzzy_flags` is our own implementation. The general
notion of similarity-matching damaged flag tokens is common to several public
submissions; our similarity threshold (0.80) was chosen by sweeping it against
the public training labels, not taken from any other solution.
