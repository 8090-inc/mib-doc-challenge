# Submission — Zwin-ux

| | |
|--|--|
| **Public solution repository** | https://github.com/Zwin-ux/XenoLedger |
| **Scoring branch** | `codex/score-control-20260724` |
| **Pinned commit** | `c25a47845ad0eb1307c84484df7bf564c8fbe0cb` |
| **Dockerfile** | repository root |
| **Entrypoint** | `run.sh <input_pdf_dir> <output_predictions_path>` |
| **Runtime default** | `MIB_RESIDUAL_CENSUS=1` (residual-census full path) |
| **Public train (official evaluator)** | **150.00 / 150 · CFA = 0** |
| **Validation predictions** | `predictions.jsonl` — **5,000** unique case IDs, `validate_submission.py` clean |
| **Technical memo** | `MEMO.md` |
| **Candidate** | `CANDIDATE.md` |
| **Train evaluation receipt** | `train_evaluation.json` |

### Live showcase (GitHub Pages)

| Surface | URL |
|---------|-----|
| **Census flight** (narrative) | https://zwin-ux.github.io/XenoLedger/scroll-world/ |
| **Workbench** (score / hire instrument) | https://zwin-ux.github.io/XenoLedger/ |
| **Census instrument** | https://zwin-ux.github.io/XenoLedger/census.html |
| Source tree | https://github.com/Zwin-ux/XenoLedger/tree/codex/score-control-20260724/docs/showcase |

### PINNED_SHA

```
PINNED_SHA=c25a47845ad0eb1307c84484df7bf564c8fbe0cb
```

That commit ships the Mode C package, 5k validation predictions, production showcase, and Pages workflow. Later commits on the branch are docs-only pin/polish.

### Contract statements

- Offline, CPU-only, no network at runtime  
- No cloud LLMs / VLMs / API keys in the scored path  
- No validation labels or peer prediction copying  
- No case-ID hardcoding; no manual per-case edits  

### Contact

- Name: Mazen Zwin  
- GitHub: https://github.com/Zwin-ux  
- LinkedIn: https://www.linkedin.com/in/mazen-zwin-a4b363204/  
- About: `CANDIDATE.md`  
