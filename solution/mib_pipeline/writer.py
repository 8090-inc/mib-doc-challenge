"""Strict submission writer.

Emits exactly the 12 schema keys per row, enum-validated, deduplicated,
case_id taken from the PDF filename stem. Never emits an extra key
(validate_submission.py fails the whole file on unknown keys) and never
omits a case (missing cases cost more than a NEEDS_REVIEW guess).
"""

import json
import os
import re
import tempfile

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

_FEE = {"paid", "waived", "unpaid", "unknown"}
_ADJ = {"APPROVED", "DENIED", "NEEDS_REVIEW"}
_SPN = re.compile(r"^SPN-\d{4}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_row(row: dict) -> dict:
    """Coerce a prediction dict into a schema-valid 12-key row."""
    out = {}
    for key in FIELDNAMES:
        out[key] = row.get(key)

    out["case_id"] = str(out["case_id"]).strip()
    for key in ("applicant_name", "species_code", "home_world", "visa_class",
                "declared_purpose"):
        val = out.get(key)
        out[key] = str(val).strip() if val else "unknown"

    spn = str(out.get("sponsor_id") or "").strip().upper()
    out["sponsor_id"] = spn if _SPN.match(spn) else "SPN-0000"

    dt = str(out.get("arrival_date") or "").strip()
    out["arrival_date"] = dt if _DATE.match(dt) else "2026-01-01"

    flags = str(out.get("risk_flags") or "none").strip().lower()
    parts = sorted({p.strip() for p in flags.split("|") if p.strip()} - {"none", ""})
    out["risk_flags"] = "|".join(parts) if parts else "none"

    fee = str(out.get("fee_status") or "").strip().lower()
    out["fee_status"] = fee if fee in _FEE else "unknown"

    adj = str(out.get("adjudication") or "").strip().upper()
    out["adjudication"] = adj if adj in _ADJ else "NEEDS_REVIEW"

    try:
        conf = float(out.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    out["confidence"] = round(min(0.99, max(0.01, conf)), 4)
    return out


def write_jsonl(path: str, rows: list) -> None:
    """Atomic write: dedup by case_id (first wins), exactly 12 keys per row."""
    seen = set()
    deduped = []
    for row in rows:
        cleaned = clean_row(row)
        if cleaned["case_id"] in seen:
            continue
        seen.add(cleaned["case_id"])
        deduped.append(cleaned)

    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            for row in deduped:
                f.write(json.dumps(row, sort_keys=True) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
