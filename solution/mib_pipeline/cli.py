"""Entry point: process a directory of PDF case packets into predictions.

Usage: python3 -m mib_pipeline.cli <input_pdf_dir> <output_predictions_path>

Two-phase flow:
  1. Extract every packet in parallel (4 workers), producing per-case
     evidence + a provisional decision.
  2. Finalize decisions batch-wide (staleness needs a batch receipt clock
     when a packet carries no receipt date) and write once, atomically.
"""

import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from . import writer

WORKERS = min(4, os.cpu_count() or 1)


def _extract_one(pdf_path_str: str) -> dict:
    import json
    from .pipeline import EXTRACT_VERSION, extract_case
    pdf_path = Path(pdf_path_str)
    cache_dir = os.environ.get("MIB_CACHE_DIR")
    cache_path = None
    if cache_dir:
        st = pdf_path.stat()
        key = f"{pdf_path.stem}_v{EXTRACT_VERSION}_{st.st_size}_{int(st.st_mtime)}"
        cache_path = Path(cache_dir) / f"{key}.json"
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text())
            except Exception:
                pass
    try:
        case = extract_case(pdf_path)
    except Exception as exc:
        print(f"[mib] {pdf_path.name}: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)
        return {"case_id": pdf_path.stem, "error": str(exc)}
    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(case))
        except Exception:
            pass
    return case


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("usage: python3 -m mib_pipeline.cli <input_pdf_dir> <output_path>",
              file=sys.stderr)
        return 2
    input_dir, output_path = Path(argv[0]), argv[1]
    pdfs = sorted(str(p) for p in input_dir.glob("*.pdf"))
    print(f"[mib] {len(pdfs)} PDFs in {input_dir}, {WORKERS} workers", flush=True)

    from .pipeline import finalize_case

    start = time.monotonic()
    extracted = []
    if len(pdfs) <= 2 or WORKERS == 1:
        for p in pdfs:
            extracted.append(_extract_one(p))
    else:
        with Pool(processes=WORKERS, maxtasksperchild=50) as pool:
            for i, case in enumerate(pool.imap_unordered(_extract_one, pdfs)):
                extracted.append(case)
                if (i + 1) % 100 == 0:
                    pace = (time.monotonic() - start) / (i + 1)
                    print(f"[mib] extracted {i+1}/{len(pdfs)} pace={pace:.2f}s/pdf",
                          flush=True)
                    # Checkpoint provisional rows in case of a hard kill.
                    rows = [finalize_case(c, extracted) for c in extracted]
                    writer.write_jsonl(output_path, rows)

    rows = [finalize_case(case, extracted) for case in extracted]
    writer.write_jsonl(output_path, rows)
    debug_path = os.environ.get("MIB_DEBUG_PATH")
    if debug_path:
        import json
        from .pipeline import debug_info
        with open(debug_path, "w") as f:
            for case in extracted:
                f.write(json.dumps(debug_info(case, extracted)) + "\n")
    pace = (time.monotonic() - start) / max(1, len(pdfs))
    print(f"[mib] wrote {len(rows)} predictions to {output_path} "
          f"({pace:.2f}s/pdf)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
