#!/usr/bin/env python3
import argparse
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

FEE_VALUES = {"paid", "waived", "unpaid", "unknown"}
ADJUDICATION_VALUES = {"APPROVED", "DENIED", "NEEDS_REVIEW"}


def expected_ids_from_manifest(path):
    with open(path, newline="") as f:
        return [row["case_id"].strip() for row in csv.DictReader(f)]


def expected_ids_from_pdf_dir(path):
    return sorted(pdf.stem for pdf in Path(path).glob("*.pdf"))


def load_json_submission(path):
    text = Path(path).read_text()
    if Path(path).suffix.lower() == ".jsonl":
        rows = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_num}: invalid JSONL: {exc}") from exc
        return rows

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("predictions", "submission", "results", "cases"):
            if isinstance(payload.get(key), list):
                return payload[key]
        if "case_id" in payload:
            return [payload]

        rows = []
        for case_id, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("case_id", case_id)
                rows.append(row)
        if rows:
            return rows

    raise SystemExit("JSON submission must be a list, a JSONL file, or an object with a predictions list.")


def read_submission(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDNAMES:
                print("Invalid CSV header.", file=sys.stderr)
                print(f"Expected: {FIELDNAMES}", file=sys.stderr)
                print(f"Got:      {reader.fieldnames}", file=sys.stderr)
                raise SystemExit(2)
            return list(reader)
    if suffix in {".json", ".jsonl"}:
        rows = load_json_submission(path)
    else:
        with open(path) as f:
            first_char = f.read(1)
        rows = load_json_submission(path) if first_char in {"[", "{"} else read_submission_csv_fallback(path)

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("Every submission record must be an object/row.")
        normalized_rows.append({str(key): value for key, value in row.items()})
    return normalized_rows


def read_submission_csv_fallback(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDNAMES:
            print("Invalid CSV header.", file=sys.stderr)
            print(f"Expected: {FIELDNAMES}", file=sys.stderr)
            print(f"Got:      {reader.fieldnames}", file=sys.stderr)
            raise SystemExit(2)
        return list(reader)


def validate_row(row, line_label):
    errors = []
    missing_fields = [field for field in FIELDNAMES if field not in row]
    extra_fields = sorted(set(row) - set(FIELDNAMES))
    if missing_fields:
        errors.append(f"{line_label}: missing fields {missing_fields}")
    if extra_fields:
        errors.append(f"{line_label}: unexpected fields {extra_fields}")
    if missing_fields:
        return errors

    case_id = str(row["case_id"]).strip()
    if not case_id:
        errors.append(f"{line_label}: missing case_id")

    fee_status = str(row["fee_status"]).strip()
    if fee_status not in FEE_VALUES:
        errors.append(f"{line_label}: invalid fee_status {row['fee_status']!r}")

    adjudication = str(row["adjudication"]).strip().upper()
    if adjudication not in ADJUDICATION_VALUES:
        errors.append(f"{line_label}: invalid adjudication {row['adjudication']!r}")

    try:
        confidence = float(row["confidence"])
    except (TypeError, ValueError):
        errors.append(f"{line_label}: confidence is not numeric")
    else:
        if not 0 <= confidence <= 1:
            errors.append(f"{line_label}: confidence must be between 0 and 1")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate MIB Doc Challenge submission CSV/JSON/JSONL format.")
    parser.add_argument("--submission", required=True)
    parser.add_argument("--manifest", help="CSV with a case_id column, such as data/validation_manifest.csv.")
    parser.add_argument("--pdf-dir", help="Directory of PDFs; expected case ids are read from PDF filenames.")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail if any expected case id is omitted. By default, missing cases are valid but scored negatively.",
    )
    args = parser.parse_args()

    if bool(args.manifest) == bool(args.pdf_dir):
        raise SystemExit("Pass exactly one of --manifest or --pdf-dir.")

    expected_ids = expected_ids_from_manifest(args.manifest) if args.manifest else expected_ids_from_pdf_dir(args.pdf_dir)
    expected_set = set(expected_ids)
    rows = read_submission(args.submission)

    errors = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        line_label = f"record {index}"
        errors.extend(validate_row(row, line_label))
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            continue
        if case_id in seen:
            errors.append(f"{line_label}: duplicate case_id {case_id}")
        seen.add(case_id)

    missing = sorted(expected_set - seen)
    extra = sorted(seen - expected_set)
    if missing and args.require_complete:
        errors.append(f"missing {len(missing)} expected case ids; first 10: {missing[:10]}")
    if extra:
        errors.append(f"contains {len(extra)} unexpected case ids; first 10: {extra[:10]}")

    if errors:
        for error in errors[:50]:
            print(error, file=sys.stderr)
        if len(errors) > 50:
            print(f"... and {len(errors) - 50} more errors", file=sys.stderr)
        return 2

    print(f"Valid submission records: {len(rows)}")
    if missing:
        print(f"Missing expected case ids: {len(missing)} (valid, scored with missing-case penalty)")
    else:
        print("Missing expected case ids: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
