# MIB Doc Challenge Submission

## Links

- Solution repository (public, contains the `Dockerfile` and root MIT
  `LICENSE`): https://github.com/speculator19/mib-portfolio
- Pinned commit for scoring: `07b1c9659104e3f79b88ffba130e4a1576beefc7`
- Submission form: filled out on 2026-08-04

## Summary

Three complementary open-source pipelines (attributed in `ATTRIBUTION.md`)
run over one shared render/OCR substrate; a frozen learned referee merges
their full evidence — anchor-relative posterior tables, note/DQ guardrails,
and out-of-fold-gated decision, confidence, and field heads — deciding by
expected value under the scoring asymmetry.

- Train dev (5-fold cross-validated, all learned parts out-of-fold): **142.59 / 150**
- One-shot sealed 200-case holdout (pre-registered, spent once): **142.15 / 150**
- Measured runtime at contest limits (4 vCPU / 8 GiB, `--network none`,
  official Docker contract): **3.70 s/PDF average**, byte-identical reruns
- Validation predictions: 5,000/5,000 cases, sha256 `ca6f9b629e99b361c04c020c2b59c60d82e88719de3ee8f90118fdc6f53953ce`
- No network, no LLMs/VLMs, no cloud APIs at runtime; all deps version-pinned

## Checklist

- [x] Submission form filled out (2026-08-04, after PR creation)
- [x] This PR only adds `submissions/<username>/predictions.jsonl`, `MEMO.md`, `SUBMISSION.md`
- [x] Solution repo builds with `docker build` and runs with the documented two-argument contract
- [x] Root MIT `LICENSE` present in the solution repository
