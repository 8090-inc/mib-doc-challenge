#!/usr/bin/env python3
"""Build the extraction cache used by the replay harness.

Development tooling -- NOT copied into the Docker image.

Ingest + extract is ~95% of pipeline runtime and is unaffected by changes to
adjudication, calibration or policy tables.  Caching it once turns an 18-minute
experiment into a ~1-second one, which is the difference between testing one
idea per uptime window and testing fifty.

    python3 build_cache.py <pdf_dir> <out.pkl> [workers]

The cache is committed to the repo on purpose: this environment restarts
frequently and restores the working tree, so anything uncommitted is lost.
"""
import os
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solution"))

import extract  # noqa: E402
import ingest  # noqa: E402


def _one(path):
    try:
        case_id, pages = ingest.ingest_pdf(str(path), do_ocr=True)
        fields, aux, cands = extract.resolve_fields(pages, frozenset(), frozenset())
        return {"case_id": case_id, "fields": fields, "aux": aux,
                "cands": cands, "ok": True}
    except Exception as exc:  # never let one bad packet kill the build
        return {"case_id": ingest._case_id_from_name(str(path)) or "MIB-000000",
                "fields": {}, "aux": {}, "cands": {}, "ok": False,
                "error": repr(exc)}


def main():
    pdf_dir, out = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    pdfs = sorted(Path(pdf_dir).rglob("*.pdf"))
    print(f"caching {len(pdfs)} packets with {workers} workers", flush=True)

    results = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, res in enumerate(ex.map(_one, pdfs, chunksize=4), start=1):
            results[res["case_id"]] = res
            if i % 100 == 0:
                print(f"  {i}/{len(pdfs)}", flush=True)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump({"version": 1, "results": results}, fh,
                    protocol=pickle.HIGHEST_PROTOCOL)
    size = os.path.getsize(out) / 1e6
    print(f"wrote {len(results)} cases -> {out} ({size:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
