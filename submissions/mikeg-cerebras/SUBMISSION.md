# Submission - mikeg-cerebras

Private solution repository:
<https://github.com/mikeg-cerebras/mib-doc-challenge>

Exact production:

```text
branch: main
runtime integration commit: 8a722bc
V5 source commit: 4870112
V5 research receipt: acb008c
independent promotion audit: 4c1915d
image SHA-256: b7fbadb59e30be241f4aad3bbe74a8fc6cada3270753399f457dec159dde92e3
train prediction SHA-256: 99cb6e81366b8efb8a99a6bca298cf79d112fba5b22027917413cb07eec8117b
validation JSONL SHA-256: e8da6488fbbfeaa145829f1466e6b5311fc400842f7f5f3ccc1468e01ad18881
```

Build and run:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=<pdf_dir>,dst=/input,readonly \
  --mount type=bind,src=<out_dir>,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

Exact receipt:
`evaluation/NATIVE_LAYOUT_V5_PROMOTION.json`.
