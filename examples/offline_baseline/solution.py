#!/usr/bin/env python3
import csv
import json
import sys
from pathlib import Path


FIELDNAMES = [
    "case_id",
    "applicant_name",
    "species_code",
    "home_world",
    "visa_class",
    "sponsor_id",
    "arrival_date",
    "declared_purpose",
    "risk_flags",
    "fee_status",
    "adjudication",
    "confidence",
]


def prediction_for(pdf):
    return {
        "case_id": pdf.stem,
        "applicant_name": "unknown",
        "species_code": "unknown",
        "home_world": "unknown",
        "visa_class": "unknown",
        "sponsor_id": "SPN-0000",
        "arrival_date": "1900-01-01",
        "declared_purpose": "unknown",
        "risk_flags": "none",
        "fee_status": "unknown",
        "adjudication": "NEEDS_REVIEW",
        "confidence": 0.01,
    }


def write_jsonl(path, pdfs):
    with open(path, "w") as f:
        for pdf in pdfs:
            f.write(json.dumps(prediction_for(pdf), sort_keys=True) + "\n")


def write_json(path, pdfs):
    with open(path, "w") as f:
        json.dump({"predictions": [prediction_for(pdf) for pdf in pdfs]}, f, indent=2, sort_keys=True)
        f.write("\n")


def write_csv(path, pdfs):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for pdf in pdfs:
            writer.writerow(prediction_for(pdf))


def main(input_dir, output_path):
    pdfs = sorted(Path(input_dir).glob("*.pdf"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".jsonl":
        write_jsonl(output, pdfs)
    elif output.suffix.lower() == ".json":
        write_json(output, pdfs)
    else:
        write_csv(output, pdfs)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: solution.py <input_pdf_dir> <output_path>")
    main(sys.argv[1], sys.argv[2])
