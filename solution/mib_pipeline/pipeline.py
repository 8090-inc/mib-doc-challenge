"""Per-PDF orchestration: harvest -> channel selection -> extraction ->
evidence aggregation -> belief -> cascade + EV decision -> output row."""

import time
from datetime import date
from pathlib import Path

from . import evidence as evidence_mod
from . import vocab
from .extract import Token, extract_fields, parse_date
from .ocr import ocr_page
from .pdfio import harvest
from .rules import CaseBelief, Decision, cascade, ev_decide

PER_PDF_BUDGET_S = 25.0

# Priors from training-label distributions, used only to fill unreadable
# output fields (never to drive adjudication beliefs).
FIELD_PRIORS = {
    "applicant_name": "unknown",
    "species_code": "TRIANGULAN",
    "home_world": "Luyten-b",
    "visa_class": "MED-3",
    "sponsor_id": "SPN-0000",
    "arrival_date": "2026-04-01",
    "declared_purpose": "reactor maintenance",
    "risk_flags": "none",
    "fee_status": "paid",
}


def spans_to_tokens(spans):
    tokens = []
    for span in spans:
        if not span.visible:
            continue
        words = span.text.split()
        if not words:
            continue
        char_w = (span.bbox[2] - span.bbox[0]) / max(1, len(span.text))
        x = span.bbox[0]
        for word in words:
            tokens.append(Token(word, x, span.bbox[1],
                                x + char_w * len(word), span.bbox[3], 95.0))
            x += char_w * (len(word) + 1)
    return tokens


def ocr_words_to_tokens(result):
    return [Token(w[0], w[2] / result.scale, w[3] / result.scale,
                  (w[2] + w[4]) / result.scale, (w[3] + w[5]) / result.scale,
                  w[1])
            for w in result.words]


def classify_page_type(text: str) -> str:
    """Fuzzy page-template detection from harvested text."""
    from rapidfuzz import fuzz
    lowered = text.lower()
    scores = {
        "intake_form": max(fuzz.partial_ratio(lowered, "form i-8090"),
                           fuzz.partial_ratio(lowered, "work authorization intake")),
        "biometric_slip": max(fuzz.partial_ratio(lowered, "form b-13"),
                              fuzz.partial_ratio(lowered, "biometric scan slip")),
        "sponsor_letter": fuzz.partial_ratio(lowered, "sponsor attestation"),
        "inspection_stamp": fuzz.partial_ratio(lowered, "arrival inspection"),
        "registry_extract": fuzz.partial_ratio(lowered, "planetary registry extract"),
        "prior_incident": fuzz.partial_ratio(lowered, "prior incident summary"),
        "fee_receipt": fuzz.partial_ratio(lowered, "fee receipt"),
        "adjudicator_note": max(fuzz.partial_ratio(lowered, "adjudicator note"),
                                fuzz.partial_ratio(lowered, "manual adjudicator")),
    }
    page_type, score = max(scores.items(), key=lambda kv: kv[1])
    return page_type if score >= 75 else ""


def process_pdf(pdf_path: Path) -> dict:
    start = time.monotonic()

    def time_left():
        return PER_PDF_BUDGET_S - (time.monotonic() - start)

    import fitz
    pages = harvest(pdf_path)
    doc = fitz.open(str(pdf_path))

    candidates = {}
    page_types_seen = []
    damage_signals = []
    trap_detected = False
    hidden_all = []

    try:
        for page in pages:
            channel = "text"
            channel_conf = 1.0
            if page.is_scanned or len(page.visible_text) < 40:
                result = ocr_page(doc, page.index,
                                  allow_escalation=time_left() > 20,
                                  time_left=time_left)
                tokens = ocr_words_to_tokens(result)
                channel = "ocr"
                channel_conf = max(0.2, min(1.0, result.mean_conf / 90.0))
                damage_signals.append(1.0 - min(1.0, result.mean_conf / 90.0))
                text_for_type = result.text
            else:
                tokens = spans_to_tokens(page.spans)
                damage_signals.append(0.0)
                text_for_type = page.visible_text

            if page.hidden_text.strip():
                hidden_all.append(page.hidden_text)
                lowered = page.hidden_text.lower()
                if any(kw in lowered for kw in ("approve", "answer", "system",
                                                "instruction", "adjudic")):
                    trap_detected = True

            page_type = classify_page_type(text_for_type)
            page_types_seen.append(page_type)

            fields = extract_fields(tokens, page.index, channel, channel_conf)
            for field_name, vals in fields.items():
                for val in vals:
                    val.page_type = page_type
                candidates.setdefault(field_name, []).extend(vals)
    finally:
        doc.close()

    values, confs, conflicts = evidence_mod.resolve(candidates)
    flags, flag_conf = evidence_mod.merge_flags(candidates, values.get("home_world"))

    arrival = parse_date(values.get("arrival_date", "") or "")
    receipt = parse_date(values.get("receipt_date", "") or "")

    belief = CaseBelief(
        visa_class=values.get("visa_class"),
        fee_status=values.get("fee_status"),
        risk_flags=frozenset(flags),
        sponsor_id=values.get("sponsor_id"),
        sponsor_seen="sponsor_id" in values,
        home_world=values.get("home_world"),
        arrival_date=date.fromisoformat(arrival) if arrival else None,
        receipt_date=date.fromisoformat(receipt) if receipt else None,
        field_confidences={k: v for k, v in confs.items()},
        damage_score=(sum(damage_signals) / len(damage_signals)
                      if damage_signals else 1.0),
        trap_detected=trap_detected,
    )

    adjudication, reason = cascade(belief)
    # Provisional confidence heuristics; replaced by trained calibration.
    base_conf = {
        "adjudicator_note_approves": 0.95, "adjudicator_note_denies": 0.95,
        "clean": 0.9, "transit_visa": 0.95, "fee_unknown": 0.85,
        "fee_unpaid": 0.92, "stale_arrival": 0.9, "embargoed_world": 0.93,
        "embargoed_world_non_dip": 0.93, "revoked_sponsor": 0.88,
        "arrival_missing_or_hidden": 0.6,
    }.get(reason.split(":")[0], 0.85)
    evidence_quality = min(1.0, (confs.get("visa_class", 0.3)
                                 + confs.get("fee_status", 0.3)
                                 + flag_conf) / 2.2 + 0.25)
    confidence = max(0.3, base_conf * (0.55 + 0.45 * evidence_quality)
                     * (1.0 - 0.35 * belief.damage_score))

    row = {"case_id": pdf_path.stem}
    for field_name in evidence_mod.OUTPUT_FIELDS:
        if field_name == "risk_flags":
            row[field_name] = "|".join(sorted(flags)) if flags else "none"
        else:
            row[field_name] = values.get(field_name) or FIELD_PRIORS[field_name]
    row["adjudication"] = adjudication
    row["confidence"] = round(confidence, 3)
    return row
