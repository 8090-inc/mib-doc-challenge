# Submission

**Solution repository (public, contains the `Dockerfile`):**
<https://github.com/christopherwoodall/8090-summer-solution-ocr>

## Run contract

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src="$PWD/data/validation",dst=/input,readonly \
  --mount type=bind,src="$PWD/out",dst=/output \
  mib-submission /input /output/predictions.jsonl
```

The image runs fully offline (`--network none`, read-only root, writes only to `/tmp`
and the output path), uses no LLMs/VLMs/cloud services, and processes a PDF in
~1.2 s on 4 vCPUs (budget: 6 s/PDF). `predictions.jsonl` in this folder is the
pipeline's output on `data/validation/` (5,000 PDFs), generated with the same code
and models the image contains; it passes
`vendor/scripts/validate_submission.py --manifest data/validation_manifest.csv`.

Local scorer numbers and reproduction commands are in the repository `README.md`;
the technical memo is `MEMO.md` in this folder.
