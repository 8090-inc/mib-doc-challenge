# Data Download

The bulk PDFs are distributed as a versioned zip outside this Git repository.

Download:

- Hugging Face: <https://huggingface.co/datasets/arjun-krishna1/mib-doc-challenge-data>
- File: `mib-doc-challenge-public-data-v2026-07-07.zip`

The dataset is private until the challenge launches.

Unzip it at the repository root. It expands to:

- `data/train/`: training PDFs
- `data/train_labels.csv`: training answers
- `data/validation/`: validation PDFs
- `data/validation_manifest.csv`: validation case IDs and PDF paths

Verify the download with:

```bash
shasum -a 256 mib-doc-challenge-public-data-v2026-07-07.zip
```

Expected checksum:

```text
a9bb8c1bbf51346ebf49c2e3e1acdb7a5d6cd0760162767b0d133c7b7200f3c4
```
