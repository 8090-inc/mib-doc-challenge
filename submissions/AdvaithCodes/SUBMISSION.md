# Submission

- GitHub username: `AdvaithCodes`
- Public solution repository: https://github.com/AdvaithCodes/mib-doc-solution
- Mandatory Dockerfile: https://github.com/AdvaithCodes/mib-doc-solution/blob/main/Dockerfile

The solution repository contains the complete offline runtime, pinned
dependencies, the fitted calibration tables, and reproduction instructions. CI
builds the image for `linux/amd64` and runs it under the scoring flags
(`--network none --cpus 4 --memory 8g --read-only --tmpfs /tmp`) on every push,
so contract violations fail there rather than at scoring time.

The runtime uses no LLMs, VLMs, cloud OCR or network services. OCR is RapidOCR
(PP-OCR ONNX models, 15.4 MiB total) plus Tesseract, both offline. Measured
runtime is 3.6 s/PDF against the 6 s budget.

The challenge entry is complete only when this pull request targets the official
repository's `main` branch and the mandatory submission form has also been
completed:

https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform
