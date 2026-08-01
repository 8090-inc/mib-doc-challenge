# Submission: Zwin-ux

| | |
|--|--|
| **Public solution repository** | https://github.com/Zwin-ux/XenoLedger |
| **Scoring branch** | `codex/score-control-20260724` |
| **Pinned commit** | `c25a47845ad0eb1307c84484df7bf564c8fbe0cb` |
| **Dockerfile** | repository root |
| **Entrypoint** | `run.sh <input_pdf_dir> <output_predictions_path>` |
| **Runtime default** | `MIB_RESIDUAL_CENSUS=1` (residual-census full path) |
| **Public train (official evaluator)** | **150.00 / 150 · CFA = 0** |
| **Validation predictions** | `predictions.jsonl`, **5,000** unique case IDs, `validate_submission.py` clean |
| **Technical memo** | `MEMO.md` |
| **Candidate** | `CANDIDATE.md` |
| **Method wiki** | **`WIKI.md`** (functions, climb, kill list, peer context) |
| **Train evaluation receipt** | `train_evaluation.json` |

### Public pages

| Surface | URL |
|---------|-----|
| **Code home** | https://github.com/Zwin-ux/XenoLedger |
| **Score wiki (repo)** | https://github.com/Zwin-ux/XenoLedger/tree/codex/score-control-20260724/wiki |
| **Final submission** | https://zwin-ux.github.io/XenoLedger/scroll-world/ |
| **Process report** | https://zwin-ux.github.io/XenoLedger/report/ |
| **Workbench** | https://zwin-ux.github.io/XenoLedger/ |
| Source tree | https://github.com/Zwin-ux/XenoLedger/tree/codex/score-control-20260724/docs/showcase |

### PINNED_SHA

```
PINNED_SHA=c25a47845ad0eb1307c84484df7bf564c8fbe0cb
```

That commit contains the residual-census path, 5,000 validation predictions, public pages, and Pages workflow. Later commits on the branch only update docs.

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
