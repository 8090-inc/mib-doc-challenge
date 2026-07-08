"""Entry point: process a directory of PDF case packets into predictions.

Usage: python3 -m mib_pipeline.cli <input_pdf_dir> <output_predictions_path>
"""

import sys
import time
from pathlib import Path

from . import writer


def predict_case(pdf_path: Path) -> dict:
    """Produce a prediction for one PDF. (Extraction stages plug in here.)"""
    from .pipeline import process_pdf  # local import: keep CLI import cheap
    return process_pdf(pdf_path)


def fallback_row(pdf_path: Path) -> dict:
    """Schema-valid hedge when processing fails entirely."""
    return {
        "case_id": pdf_path.stem,
        "adjudication": "NEEDS_REVIEW",
        "confidence": 0.3,
        "risk_flags": "none",
        "fee_status": "unknown",
    }


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("usage: python3 -m mib_pipeline.cli <input_pdf_dir> <output_path>",
              file=sys.stderr)
        return 2
    input_dir, output_path = Path(argv[0]), argv[1]
    pdfs = sorted(input_dir.glob("*.pdf"))
    print(f"[mib] {len(pdfs)} PDFs in {input_dir}", flush=True)

    rows = []
    start = time.monotonic()
    for i, pdf in enumerate(pdfs):
        try:
            rows.append(predict_case(pdf))
        except Exception as exc:  # never lose a case to one bad PDF
            print(f"[mib] {pdf.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            rows.append(fallback_row(pdf))
        if (i + 1) % 100 == 0:
            writer.write_jsonl(output_path, rows)  # checkpoint (atomic)
            pace = (time.monotonic() - start) / (i + 1)
            print(f"[mib] {i+1}/{len(pdfs)} pace={pace:.2f}s/pdf", flush=True)

    writer.write_jsonl(output_path, rows)
    print(f"[mib] wrote {len(rows)} predictions to {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
