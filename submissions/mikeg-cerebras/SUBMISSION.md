# Submission - mikeg-cerebras

Solution repository (private; organizer-confirmed reviewer access on request):
https://github.com/mikeg-cerebras/mib-doc-challenge

Exact candidate branch and receipt:

```text
branch: promotion/fee-unknown-calibration-20260725
receipt commit: 06c90b708b0579470224c20d2d289808e47ef207
runtime code commit: 87da1ec2197531203e3a3aac6b96aa573def3491
inner scored runtime commit: 8acce90e0bdd7c36aa5294e2812980ec4ff44eef
validation JSONL SHA-256: 87ac256383f6617d4ad64671a9a1cecbfe25eed7d26667dbedb68549a3f12bb8
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
and typed-replay receipts, attribution, and audit evidence. The
machine-readable promotion receipt is
`evaluation/FEE_UNKNOWN_PROMOTION.json`.
