# Submission

- GitHub username: `adhyaay-karnwal`
- Public solution repository:
  https://github.com/adhyaay-karnwal/mib-doc-solution
- Dockerfile:
  https://github.com/adhyaay-karnwal/mib-doc-solution/blob/main/Dockerfile
- Release source commit:
  `0479e46109925cc9bc8fbd92f2281635471a1f75`
- Tested image ID:
  `sha256:7b64c06b262bd50d312d5155f338ed718996b00e0d64709f854a2ec92e3fb9e3`

The final image is offline, CPU-only, and visible-evidence-first. Its public
train full-data confidence artifact scores **124.05 / 150**, with **zero
catastrophic false approvals**; nested five-fold OOF evidence is **123.95**.
The underlying 1,000-PDF Docker run completed in 1.511 seconds/PDF.

Validation predictions: **5,000 / 5,000** records with zero omissions. The
official manifest validator reported 5,000 valid records and zero missing IDs.
Measured runtime was **8,873.53 seconds total (1.775 seconds/PDF)** under the
exact 4 CPU / 8 GB offline contract.

Predictions SHA-256:

`a83f651d2a56ba54fac1f2a6ad1dfaf863458427989f827740d272ed058afc89`

The mandatory challenge submission form must also be completed:
https://docs.google.com/forms/d/1ZLkHmTsYd9I87JL1sUyps2rPTe6ohEI_lTZ8Jjts6bw/viewform
