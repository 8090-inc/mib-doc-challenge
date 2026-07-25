# Submission - mikeg-cerebras

Solution repository (private; organizer-confirmed reviewer access on request):
https://github.com/mikeg-cerebras/mib-doc-challenge

Exact candidate branch and receipt:

```text
branch: research/abhishek-safe-derivative
receipt commit: 770fb11f9c7561fc4935e7fa0ae034af16239080
scored runtime commit: 8acce90e0bdd7c36aa5294e2812980ec4ff44eef
validation JSONL SHA-256: f80aa5d16f123e2ab9e447594b36a59a8cc0fa1c6ea6c6c728ba74880b3e7e73
```

After checking out that branch, build and run from its repository root:

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=<pdf_dir>,dst=/input,readonly \
  --mount type=bind,src=<out_dir>,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

See `README.md`, `RUNTIME.md`, `DERIVATIVE_PROVENANCE.md`, and
`HIDDEN_KEY_AUDIT.md` on the candidate branch for architecture, exact image
receipt, attribution, and audit evidence.
