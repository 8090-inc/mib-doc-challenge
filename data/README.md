# Data Download

The bulk PDFs are distributed as a versioned zip outside this Git repository.

Download:

- Google Drive: <https://drive.google.com/file/d/1vHvXhAa6CYMycNRXDgyA8E6DaoJu8grl/view?usp=sharing>
- File: `mib-doc-challenge-public-data-v2026-06-30.zip`

Drive access is managed by 8090 until launch.

Unzip it at the repository root. It expands to:

- `data/train/`: training PDFs
- `data/train_labels.csv`: training answers
- `data/validation/`: validation PDFs
- `data/validation_manifest.csv`: validation case IDs and PDF paths

Verify the download with:

```bash
shasum -a 256 mib-doc-challenge-public-data-v2026-06-30.zip
```

Expected checksum:

```text
c10138d3feecbd51f8620ae7808d848c848254cba87fe769413d87e73a333eb8
```
