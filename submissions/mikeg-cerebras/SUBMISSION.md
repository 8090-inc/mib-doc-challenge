# Submission - mikeg-cerebras

Solution repository (private; organizer-confirmed reviewer access on request):
https://github.com/mikeg-cerebras/mib-doc-challenge

Exact candidate branch and receipt:

```text
branch: promotion/trace-aware-denial-softening-20260728
receipt commit: 40e68485e7e20db11542fba8e75d9ffb8510f2d0
runtime code commit: 3be2063ed7c2e54eba910c2346052e84ef1a0400
protected base runtime commit: 87da1ec2197531203e3a3aac6b96aa573def3491
inner scored runtime commit: 8acce90e0bdd7c36aa5294e2812980ec4ff44eef
independent audit commit: 9a5c5cd2d0de3bdb1dac6c5de82d5cd9b12c24c4
validation JSONL SHA-256: 36232106f99a5ad5fea2083e93f441745e6e277669265a377205e98140eb1b17
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
`evaluation/TRACE_AWARE_DENIAL_SOFTENING_PROMOTION.json`.
