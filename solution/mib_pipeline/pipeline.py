"""Per-PDF orchestration. Placeholder floor implementation for now:
extraction stages land here incrementally."""

from pathlib import Path


def process_pdf(pdf_path: Path) -> dict:
    # Floor predictor: hedge everything. Replaced by real extraction+rules.
    return {
        "case_id": pdf_path.stem,
        "applicant_name": "unknown",
        "species_code": "TRIANGULAN",
        "home_world": "Luyten-b",
        "visa_class": "MED-3",
        "sponsor_id": "SPN-0000",
        "arrival_date": "2026-04-01",
        "declared_purpose": "research",
        "risk_flags": "none",
        "fee_status": "paid",
        "adjudication": "NEEDS_REVIEW",
        "confidence": 0.28,
    }
