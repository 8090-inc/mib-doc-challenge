#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


SCORE_VERSION = "mib_weighted_v1"

FIELDS = [
    "applicant_name",
    "species_code",
    "home_world",
    "visa_class",
    "sponsor_id",
    "arrival_date",
    "declared_purpose",
    "risk_flags",
    "fee_status",
]

FIELD_WEIGHTS = {
    "applicant_name": 5,
    "species_code": 6,
    "home_world": 5,
    "visa_class": 5,
    "sponsor_id": 5,
    "arrival_date": 4,
    "declared_purpose": 3,
    "risk_flags": 8,
    "fee_status": 4,
}

ADJUDICATION_VALUES = {"APPROVED", "DENIED", "NEEDS_REVIEW"}
FEE_VALUES = {"paid", "waived", "unpaid", "unknown"}

EXTRACTION_SECTION_POINTS = 50.0
CLASSIFICATION_SECTION_POINTS = 80.0
CALIBRATION_SECTION_POINTS = 20.0
MISSING_PENALTY_CAP = 10.0
CLASSIFICATION_MAX_RAW = 8.0


def normalize(value):
    return " ".join(str(value or "").strip().split()).casefold()


def normalize_flags(value):
    raw = normalize(value)
    if raw in {"", "none", "null", "unknown"}:
        return "none"
    return "|".join(sorted(part.strip() for part in raw.split("|") if part.strip()))


def split_pipe(value):
    raw = normalize(value)
    if raw in {"", "none", "null"}:
        return set()
    return {part.strip() for part in raw.split("|") if part.strip()}


def parse_confidence(row):
    try:
        value = float(row.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0, False
    if not 0.0 <= value <= 1.0:
        return 0.0, False
    return value, True


def read_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_truth(path):
    rows = read_csv_rows(path)
    truth = {}
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if case_id:
            truth[case_id] = row
    return truth


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
        rows = read_csv_rows(path)
    elif suffix in {".json", ".jsonl"}:
        rows = load_json_submission(path)
    else:
        with open(path) as f:
            first_char = f.read(1)
        if first_char in {"[", "{"}:
            rows = load_json_submission(path)
        else:
            rows = read_csv_rows(path)

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("Every submission record must be an object/row.")
        normalized_rows.append({str(key): value for key, value in row.items()})
    return normalized_rows


def index_submission(rows):
    predictions = {}
    duplicate_case_ids = []
    blank_case_rows = 0

    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            blank_case_rows += 1
            continue
        if case_id in predictions:
            duplicate_case_ids.append(case_id)
            continue
        predictions[case_id] = row

    return predictions, duplicate_case_ids, blank_case_rows


def field_match(field, truth, pred):
    truth_value = truth.get(field, "")
    pred_value = pred.get(field, "")
    if field == "risk_flags":
        return normalize_flags(truth_value) == normalize_flags(pred_value)
    return normalize(truth_value) == normalize(pred_value)


def classification_points(truth_adj, pred_adj):
    if pred_adj not in ADJUDICATION_VALUES:
        return 0.0, "invalid_or_blank", False
    if truth_adj == pred_adj:
        return CLASSIFICATION_MAX_RAW, "correct", False
    if truth_adj == "DENIED" and pred_adj == "APPROVED":
        return -4.0, "catastrophic_false_approval", True
    if pred_adj == "NEEDS_REVIEW":
        return 2.0, "conservative_review", False
    if truth_adj == "NEEDS_REVIEW":
        return 1.0, "missed_review", False
    return 0.0, "wrong_decision", False


def score_case(case_id, truth, pred):
    unrecoverable = split_pipe(truth.get("unrecoverable_fields", ""))
    extraction_raw = 0.0
    extraction_max_raw = 0.0
    field_results = {}

    for field in FIELDS:
        weight = FIELD_WEIGHTS[field]
        if field in unrecoverable:
            field_results[field] = {
                "status": "not_scorable_unrecoverable",
                "points": 0,
                "max_points": 0,
            }
            continue

        extraction_max_raw += weight
        matched = bool(pred) and field_match(field, truth, pred)
        points = weight if matched else 0
        extraction_raw += points
        field_results[field] = {
            "status": "matched" if matched else "missed",
            "points": points,
            "max_points": weight,
        }

    truth_adj = str(truth.get("adjudication", "")).strip().upper()
    pred_adj = str((pred or {}).get("adjudication", "")).strip().upper()
    classification_raw, classification_reason, catastrophic = classification_points(truth_adj, pred_adj)
    present = pred is not None
    adjudication_valid = (not present) or pred_adj in ADJUDICATION_VALUES
    adj_correct = present and truth_adj == pred_adj
    confidence, confidence_valid = parse_confidence(pred or {})
    confidence_brier = None
    if present:
        confidence_brier = (confidence - (1.0 if adj_correct else 0.0)) ** 2 if confidence_valid else 1.0
    fee_status = str((pred or {}).get("fee_status", "")).strip()
    fee_status_valid = (not present) or fee_status in FEE_VALUES

    return {
        "case_id": case_id,
        "present": present,
        "truth_adjudication": truth_adj,
        "pred_adjudication": pred_adj if present else "MISSING",
        "field_results": field_results,
        "extraction_raw": extraction_raw,
        "extraction_max_raw": extraction_max_raw,
        "classification_raw": classification_raw if present else 0.0,
        "classification_max_raw": CLASSIFICATION_MAX_RAW,
        "classification_reason": classification_reason if present else "missing_case",
        "adjudication_valid": adjudication_valid if present else None,
        "catastrophic_false_approval": catastrophic if present else False,
        "confidence": confidence if present else None,
        "confidence_valid": confidence_valid if present else None,
        "confidence_brier": confidence_brier,
        "fee_status_valid": fee_status_valid if present else None,
        "difficulty": truth.get("difficulty", ""),
        "damage_profile": truth.get("damage_profile", ""),
        "traps_present": bool(split_pipe(truth.get("traps", ""))),
    }


def safe_divide(numerator, denominator):
    if denominator == 0:
        return 0.0
    return numerator / denominator


def build_results(truth_rows, pred_rows):
    predictions, duplicate_case_ids, blank_case_rows = index_submission(pred_rows)
    expected_ids = set(truth_rows)
    extra_case_ids = sorted(set(predictions) - expected_ids)
    missing_case_ids = []
    case_scores = []
    confusion = Counter()
    totals = Counter()
    confidence_briers = []

    for case_id, truth in truth_rows.items():
        pred = predictions.get(case_id)
        if pred is None:
            missing_case_ids.append(case_id)
        scored = score_case(case_id, truth, pred)
        case_scores.append(scored)

        totals["extraction_raw"] += scored["extraction_raw"]
        totals["extraction_max_raw"] += scored["extraction_max_raw"]
        totals["classification_raw"] += scored["classification_raw"]
        totals["classification_max_raw"] += scored["classification_max_raw"]
        totals["catastrophic_false_approvals"] += int(scored["catastrophic_false_approval"])
        totals["invalid_adjudication_records"] += int(scored["present"] and not scored["adjudication_valid"])
        totals["invalid_confidence_records"] += int(scored["present"] and not scored["confidence_valid"])
        totals["invalid_fee_status_records"] += int(scored["present"] and not scored["fee_status_valid"])

        if scored["present"]:
            confusion[(scored["truth_adjudication"], scored["pred_adjudication"])] += 1
            if scored["confidence_brier"] is not None:
                confidence_briers.append(scored["confidence_brier"])
        else:
            confusion[(scored["truth_adjudication"], "MISSING")] += 1

    extraction_score = EXTRACTION_SECTION_POINTS * safe_divide(
        totals["extraction_raw"], totals["extraction_max_raw"]
    )
    classification_score = CLASSIFICATION_SECTION_POINTS * safe_divide(
        totals["classification_raw"], totals["classification_max_raw"]
    )

    if confidence_briers:
        mean_brier = sum(confidence_briers) / len(confidence_briers)
        calibration_score = CALIBRATION_SECTION_POINTS * max(0.0, 1.0 - 2.0 * mean_brier)
    else:
        mean_brier = None
        calibration_score = 0.0

    missing_penalty = MISSING_PENALTY_CAP * safe_divide(len(missing_case_ids), len(truth_rows))
    total_score = extraction_score + classification_score + calibration_score - missing_penalty

    per_missing_penalty = safe_divide(MISSING_PENALTY_CAP, len(truth_rows))
    for scored in case_scores:
        scored["missing_penalty_score"] = per_missing_penalty if not scored["present"] else 0.0

    results = {
        "score_version": SCORE_VERSION,
        "score_scale": {
            "max_score": EXTRACTION_SECTION_POINTS + CLASSIFICATION_SECTION_POINTS + CALIBRATION_SECTION_POINTS,
            "extraction_points": EXTRACTION_SECTION_POINTS,
            "classification_points": CLASSIFICATION_SECTION_POINTS,
            "calibration_points": CALIBRATION_SECTION_POINTS,
            "missing_penalty_cap": MISSING_PENALTY_CAP,
        },
        "counts": {
            "truth_cases": len(truth_rows),
            "submitted_records": len(pred_rows),
            "scored_predictions": len(set(predictions) & expected_ids),
            "missing_cases": len(missing_case_ids),
            "extra_cases": len(extra_case_ids),
            "duplicate_case_ids": len(duplicate_case_ids),
            "blank_case_rows": blank_case_rows,
            "invalid_adjudication_records": totals["invalid_adjudication_records"],
            "invalid_confidence_records": totals["invalid_confidence_records"],
            "invalid_fee_status_records": totals["invalid_fee_status_records"],
        },
        "scores": {
            "total_score": total_score,
            "extraction_score": extraction_score,
            "classification_score": classification_score,
            "calibration_score": calibration_score,
            "missing_penalty": missing_penalty,
        },
        "raw": {
            "extraction_raw": totals["extraction_raw"],
            "extraction_max_raw": totals["extraction_max_raw"],
            "classification_raw": totals["classification_raw"],
            "classification_max_raw": totals["classification_max_raw"],
            "mean_confidence_brier": mean_brier,
            "catastrophic_false_approvals": totals["catastrophic_false_approvals"],
        },
        "confusion": {
            f"{truth_adj}->{pred_adj}": count
            for (truth_adj, pred_adj), count in sorted(confusion.items())
        },
        "examples": {
            "missing_case_ids": missing_case_ids[:20],
            "extra_case_ids": extra_case_ids[:20],
            "duplicate_case_ids": duplicate_case_ids[:20],
        },
    }
    return results, case_scores


def write_json(path, payload):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def write_jsonl(path, rows):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def print_summary(results):
    counts = results["counts"]
    scores = results["scores"]
    raw = results["raw"]

    print(f"Score version: {results['score_version']}")
    print(f"Cases: {counts['truth_cases']}")
    print(f"Submitted records: {counts['submitted_records']}")
    print(f"Scored predictions: {counts['scored_predictions']}")
    print(f"Missing cases: {counts['missing_cases']}")
    print(f"Extra cases: {counts['extra_cases']}")
    print(f"Duplicate case ids: {counts['duplicate_case_ids']}")
    print(f"Invalid adjudication records: {counts['invalid_adjudication_records']}")
    print(f"Invalid confidence records: {counts['invalid_confidence_records']}")
    print(f"Invalid fee_status records: {counts['invalid_fee_status_records']}")
    print(f"Field extraction: {scores['extraction_score']:.2f} / {EXTRACTION_SECTION_POINTS:.0f}")
    print(f"Classification: {scores['classification_score']:.2f} / {CLASSIFICATION_SECTION_POINTS:.0f}")
    print(f"Calibration: {scores['calibration_score']:.2f} / {CALIBRATION_SECTION_POINTS:.0f}")
    print(f"Missing-case penalty: -{scores['missing_penalty']:.2f} / {MISSING_PENALTY_CAP:.0f}")
    print(f"Deterministic score: {scores['total_score']:.2f} / 150")
    print(f"Catastrophic false approvals: {raw['catastrophic_false_approvals']}")
    if raw["mean_confidence_brier"] is not None:
        print(f"Mean confidence Brier: {raw['mean_confidence_brier']:.4f}")
    print("Confusion:")
    for key, count in results["confusion"].items():
        print(f"  {key}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Deterministically score MIB Doc Challenge predictions.")
    parser.add_argument("--truth", required=True, help="CSV labels with a case_id column.")
    parser.add_argument("--submission", required=True, help="Candidate CSV, JSON, or JSONL predictions.")
    parser.add_argument("--output-json", help="Write aggregate evaluation results as JSON.")
    parser.add_argument("--case-scores-jsonl", help="Write per-case deterministic scoring details as JSONL.")
    args = parser.parse_args()

    truth_rows = read_truth(args.truth)
    pred_rows = read_submission(args.submission)

    if not truth_rows:
        raise SystemExit("No truth rows found.")

    results, case_scores = build_results(truth_rows, pred_rows)
    print_summary(results)

    if args.output_json:
        write_json(args.output_json, results)
    if args.case_scores_jsonl:
        write_jsonl(args.case_scores_jsonl, case_scores)

    invalid_counts = (
        results["counts"]["duplicate_case_ids"]
        + results["counts"]["extra_cases"]
        + results["counts"]["invalid_adjudication_records"]
        + results["counts"]["invalid_confidence_records"]
        + results["counts"]["invalid_fee_status_records"]
    )
    if invalid_counts:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
