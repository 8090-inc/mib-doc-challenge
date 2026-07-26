"""Per-PDF orchestration split into two phases.

extract_case(pdf)  -> serializable evidence dict (runs in worker processes)
finalize_case(...) -> final output row, given the whole batch (staleness
                      uses a batch-level receipt clock when a packet has no
                      receipt date of its own; per-doc evidence always wins)
"""

import time
from datetime import date, timedelta
from pathlib import Path

from . import evidence as evidence_mod
from . import vocab
from .extract import (Token, extract_fields, parse_adjudicator_note,
                      parse_bio_confidence, parse_date, parse_registry_status,
                      parse_sponsor_letter, vocab_sweep)
from .ocr import ocr_page
from .pdfio import harvest
from .rules import CaseBelief, cascade, ev_decide
from .stamps import read_note_text, read_stamps

PER_PDF_BUDGET_S = 25.0
# Bump when extract_case output semantics change (dev cache key).
EXTRACT_VERSION = 8

# Output fill-ins for unreadable fields (train-label modes). These are
# submission guesses only - adjudication beliefs never consume them.
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


import re as _re

_FOOTER_RE = _re.compile(
    r"Packet\s+MIB[-\s]*\d{6}\s*/\s*page\s*\d+|Synthetic hiring challenge document"
    r"|MIB[-\s]*\d{6}\s*\|\s*MIB Eyes Only", _re.IGNORECASE)

# Fake answer keys / injected instructions are untrusted regardless of
# visibility (field manual: they are not evidence). Filter them out of the
# extraction stream and remember the trap.
_INJECT_RE = _re.compile(
    r"answer\s*key|SYSTEM\s*:|ignore\s+(all\s+|the\s+)?(visible\s+)?(evidence|instructions|policy)"
    r"|output\s+this|approve\s+(this|all)\s+case|adjudicate\s+as|final\s+answer",
    _re.IGNORECASE)


def meaningful_text(text: str) -> str:
    return _FOOTER_RE.sub("", text).strip()


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


def extract_case(pdf_path: Path) -> dict:
    """Phase 1: harvest one packet into a serializable evidence dict."""
    start = time.monotonic()

    def time_left():
        return PER_PDF_BUDGET_S - (time.monotonic() - start)

    import fitz
    pages = harvest(pdf_path)
    doc = fitz.open(str(pdf_path))

    candidates = {}
    page_types = []
    page_details = []   # per page: {type, channel, conf, chars}
    damage_signals = []
    trap_detected = False
    stamp_events = []      # (kind, page_type, page_index)
    ocr_pages = 0
    special = {"letter_names": [], "notes": []}

    try:
        for page in pages:
            channel = "text"
            channel_conf = 1.0
            if page.is_scanned or len(meaningful_text(page.visible_text)) < 30:
                result = ocr_page(doc, page.index,
                                  allow_escalation=time_left() > 20,
                                  time_left=time_left)
                tokens = ocr_words_to_tokens(result)
                channel = "ocr"
                ocr_pages += 1
                channel_conf = max(0.2, min(1.0, result.mean_conf / 90.0))
                damage_signals.append(1.0 - min(1.0, result.mean_conf / 90.0))
                text_for_type = result.text
            else:
                tokens = spans_to_tokens(page.spans)
                damage_signals.append(0.0)
                text_for_type = page.visible_text

            if page.hidden_text.strip():
                lowered = page.hidden_text.lower()
                if any(kw in lowered for kw in ("approve", "answer", "system",
                                                "instruction", "adjudic",
                                                "deny", "json")):
                    trap_detected = True

            # Drop injected instruction/answer-key lines from extraction input.
            inj_tokens = [t for t in tokens if _INJECT_RE.search(t.text)]
            if inj_tokens or _INJECT_RE.search(text_for_type or ""):
                trap_detected = True
                from .extract import group_lines
                bad_rows = set()
                for line in group_lines(tokens):
                    line_text = " ".join(t.text for t in line)
                    if _INJECT_RE.search(line_text):
                        bad_rows.update(id(t) for t in line)
                tokens = [t for t in tokens if id(t) not in bad_rows]

            page_type = classify_page_type(text_for_type)
            page_types.append(page_type)
            page_details.append({
                "type": page_type,
                "channel": channel,
                "conf": round(channel_conf, 3),
                "chars": len(meaningful_text(text_for_type or "")),
                "scanned": bool(page.is_scanned),
            })

            # Stamps (rendered ink) + adjudicator note phrasing.
            for ev in read_stamps(doc, page.index, time_left=time_left):
                stamp_events.append((ev.kind, page_type, page.index))
            if page_type == "adjudicator_note":
                for ev in read_note_text(text_for_type, page.index):
                    stamp_events.append((ev.kind, page_type, page.index))

            fields = extract_fields(tokens, page.index, channel, channel_conf)
            swept = vocab_sweep(tokens, page.index, channel, channel_conf)
            for field_name, vals in swept.items():
                fields.setdefault(field_name, []).extend(vals)
            for field_name, vals in fields.items():
                for val in vals:
                    val.page_type = page_type
                candidates.setdefault(field_name, []).extend(vals)

            page_text_now = " ".join(t.text for t in tokens)
            if page_type == "sponsor_letter":
                letter = parse_sponsor_letter(page_text_now)
                for fname in ("sponsor_id", "visa_class", "declared_purpose"):
                    if letter.get(fname):
                        from .extract import FieldValue
                        candidates.setdefault(fname, []).append(FieldValue(
                            letter[fname], 0.85 * channel_conf, channel,
                            page.index, page_type="sponsor_letter"))
                if letter.get("letter_name"):
                    special["letter_names"].append(letter["letter_name"])
            elif page_type == "adjudicator_note":
                note = parse_adjudicator_note(page_text_now)
                if note:
                    special["notes"].append(note)
            elif page_type == "registry_extract":
                status = parse_registry_status(page_text_now)
                if status:
                    special["registry_status"] = status
            elif page_type == "biometric_slip":
                bio = parse_bio_confidence(page_text_now)
                if bio is not None:
                    special["bio_conf"] = min(special.get("bio_conf", 101), bio)
    finally:
        doc.close()

    values, confs, conflicts = evidence_mod.resolve(candidates)
    flags, flag_conf = evidence_mod.merge_flags(candidates, values.get("home_world"))

    return {
        "case_id": pdf_path.stem,
        "special": special,
        "values": values,
        "confs": confs,
        "conflicts": {k: bool(v) for k, v in conflicts.items()},
        "flags": sorted(flags),
        "flag_conf": flag_conf,
        "page_types": page_types,
        "page_details": page_details,
        "damage": (sum(damage_signals) / len(damage_signals)
                   if damage_signals else 1.0),
        "ocr_pages": ocr_pages,
        "n_pages": len(pages),
        "trap_detected": trap_detected,
        "stamps": stamp_events,
        "elapsed": time.monotonic() - start,
    }


def batch_receipt_clock(all_cases) -> date:
    """Batch-wide stand-in for 'now' when a packet has no receipt date:
    a high percentile of plausible dates seen across the batch (robust to
    isolated OCR misparses producing far-future years)."""
    receipts = []
    others = []
    for case in all_cases:
        r = parse_date(case.get("values", {}).get("receipt_date", "") or "")
        if r and "2020-01-01" <= r <= "2035-12-31":
            receipts.append(r)
        a = parse_date(case.get("values", {}).get("arrival_date", "") or "")
        if a and "2020-01-01" <= a <= "2035-12-31":
            others.append(a)
    pool = sorted(receipts or others)
    if not pool:
        return date(2026, 7, 1)
    idx = min(len(pool) - 1, int(0.995 * (len(pool) - 1) + 0.5))
    return date.fromisoformat(pool[idx])


def belief_from_case(case: dict, clock: date) -> CaseBelief:
    values = case.get("values", {})
    confs = case.get("confs", {})
    arrival = parse_date(values.get("arrival_date", "") or "")
    receipt = parse_date(values.get("receipt_date", "") or "")
    stamps = case.get("stamps", [])
    kinds = [k for k, _, _ in stamps]
    special = case.get("special", {})

    # Explicit adjudicator findings outrank stamp blobs.
    note_approves = "approve" in kinds
    note_denies = "deny" in kinds
    rescinded = "rescinded" in kinds
    for note in special.get("notes", []):
        if note.get("note_finding") == "APPROVED":
            note_approves = True
        elif note.get("note_finding") == "DENIED":
            note_denies = True
        if note.get("note_rescinded"):
            rescinded = True

    flags = set(case.get("flags", []))
    for note in special.get("notes", []):
        flags.update(note.get("note_flags", []))
    if case.get("conflicts", {}).get("applicant_name"):
        flags.add("identity_conflict")
    if case.get("conflicts", {}).get("sponsor_id"):
        flags.add("sponsor_mismatch")
    # Sponsor letter naming a different applicant than the packet name.
    intake_name = (values.get("applicant_name") or "").lower()
    for lname in special.get("letter_names", []):
        if intake_name and lname.lower() != intake_name:
            from rapidfuzz import fuzz as _fuzz
            if _fuzz.ratio(lname.lower(), intake_name) < 72:
                flags.add("sponsor_mismatch")

    return CaseBelief(
        visa_class=values.get("visa_class"),
        fee_status=values.get("fee_status"),
        risk_flags=frozenset(flags),
        sponsor_id=values.get("sponsor_id"),
        sponsor_seen="sponsor_id" in values,
        home_world=values.get("home_world"),
        arrival_date=date.fromisoformat(arrival) if arrival else None,
        receipt_date=date.fromisoformat(receipt) if receipt else clock,
        note_approves=note_approves,
        note_denies=note_denies,
        denial_rescinded=rescinded,
        field_confidences=dict(confs),
        damage_score=case.get("damage", 0.5),
        trap_detected=case.get("trap_detected", False),
    )


# Provisional per-reason accuracy priors; replaced by trained calibration
# once real train-set runs exist.
REASON_CONF = {
    "adjudicator_note_approves": 0.94, "adjudicator_note_denies": 0.94,
    "clean": 0.90, "transit_visa": 0.95, "fee_unknown": 0.85,
    "fee_unpaid": 0.92, "stale_arrival": 0.90, "embargoed_world": 0.93,
    "embargoed_world_non_dip": 0.93, "revoked_sponsor": 0.88,
    "arrival_missing_or_hidden": 0.60, "disqualifying_flag": 0.93,
    "review_flag": 0.86,
}


def finalize_case(case: dict, all_cases) -> dict:
    """Phase 2: decide + emit an output row given batch context."""
    if "values" not in case:  # hard extraction failure
        return {"case_id": case["case_id"], "adjudication": "NEEDS_REVIEW",
                "confidence": 0.3, "risk_flags": "none", "fee_status": "unknown"}

    clock = batch_receipt_clock(all_cases)
    belief = belief_from_case(case, clock)
    adjudication, reason = cascade(belief)
    values, confs = case["values"], case["confs"]

    from . import model_runtime
    from .features import FORCED, build_features
    from .rules import ev_utility
    if model_runtime.available():
        record = dict(case)
        record["reason"] = reason
        record["belief_flags"] = sorted(belief.risk_flags)
        p_a, p_d, p_r = model_runtime.predict_proba(build_features(record))
        base_reason = reason.split(":")[0]
        if base_reason in FORCED:
            adjudication = FORCED[base_reason]
            p_raw = {"APPROVED": p_a, "DENIED": p_d,
                     "NEEDS_REVIEW": p_r}[adjudication]
            p_raw = max(p_raw, 0.5)
        else:
            adjudication = max(("APPROVED", "DENIED", "NEEDS_REVIEW"),
                               key=lambda a: ev_utility(a, p_a, p_d, p_r))
            p_raw = {"APPROVED": p_a, "DENIED": p_d,
                     "NEEDS_REVIEW": p_r}[adjudication]
        confidence = model_runtime.calibrate(p_raw)
    else:
        base = REASON_CONF.get(reason.split(":")[0], 0.85)
        evidence_quality = min(1.0, (confs.get("visa_class", 0.3)
                                     + confs.get("fee_status", 0.3)
                                     + case.get("flag_conf", 0.3)) / 2.2 + 0.25)
        confidence = max(0.3, base * (0.55 + 0.45 * evidence_quality)
                         * (1.0 - 0.35 * case.get("damage", 0.0)))

    row = {"case_id": case["case_id"]}
    flags = set(case.get("flags", []))
    for field_name in evidence_mod.OUTPUT_FIELDS:
        if field_name == "risk_flags":
            row[field_name] = "|".join(sorted(flags)) if flags else "none"
        else:
            row[field_name] = values.get(field_name) or FIELD_PRIORS[field_name]
    row["adjudication"] = adjudication
    row["confidence"] = round(confidence, 3)
    return row


def process_pdf(pdf_path: Path) -> dict:
    """Single-PDF convenience wrapper (tests, debugging)."""
    case = extract_case(pdf_path)
    return finalize_case(case, [case])


def debug_info(case: dict, all_cases) -> dict:
    """Dev-only: full decision trace for error analysis."""
    if "values" not in case:
        return {"case_id": case["case_id"], "error": case.get("error", "?")}
    clock = batch_receipt_clock(all_cases)
    belief = belief_from_case(case, clock)
    adjudication, reason = cascade(belief)
    return {
        "case_id": case["case_id"],
        "adjudication": adjudication,
        "reason": reason,
        "values": case["values"],
        "confs": {k: round(v, 3) for k, v in case["confs"].items()},
        "conflicts": case.get("conflicts"),
        "flags_extracted": case.get("flags"),
        "belief_flags": sorted(belief.risk_flags),
        "special": case.get("special"),
        "stamps": case.get("stamps"),
        "page_types": case.get("page_types"),
        "page_details": case.get("page_details"),
        "flag_conf": case.get("flag_conf"),
        "damage": round(case.get("damage", 0), 3),
        "ocr_pages": case.get("ocr_pages"),
        "trap": case.get("trap_detected"),
        "clock": clock.isoformat(),
    }
