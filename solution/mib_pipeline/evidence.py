"""Cross-page evidence aggregation with the field-manual precedence ladder."""

from collections import defaultdict
from datetime import date

from . import vocab
from .extract import FieldValue  # noqa: F401  (typing/reference)

# Evidence precedence (FIELD_MANUAL): adjudicator note/stamp > intake form >
# biometric slip > sponsor attestation > registry extract > raw text layer.
PAGE_TYPE_RANK = {
    "adjudicator_note": 6.0,
    "intake_form": 5.0,
    "biometric_slip": 4.0,
    "sponsor_letter": 3.0,
    "registry_extract": 2.0,
    "inspection_stamp": 2.0,
    "prior_incident": 2.0,
    "fee_receipt": 2.5,      # authoritative for fee_status specifically
    "": 1.0,                  # unknown page type
}

OUTPUT_FIELDS = ["applicant_name", "species_code", "home_world", "visa_class",
                 "sponsor_id", "arrival_date", "declared_purpose",
                 "risk_flags", "fee_status"]


def resolve(candidates_per_field: dict):
    """Pick a winning value per field.

    candidates_per_field: {field: [FieldValue, ...]} accumulated over pages.
    Returns ({field: value}, {field: conf01}, {field: conflict_bool}).
    """
    values, confs, conflicts = {}, {}, {}
    for field_name, cands in candidates_per_field.items():
        if not cands:
            continue
        weights = defaultdict(float)
        best_conf = defaultdict(float)
        for cand in cands:
            rank = PAGE_TYPE_RANK.get(cand.page_type, 1.0)
            if field_name == "fee_status" and cand.page_type == "fee_receipt":
                rank = 5.5  # receipts outrank forms for the fee itself
            weight = rank * (0.25 + 0.75 * cand.conf)
            weights[cand.value] += weight
            best_conf[cand.value] = max(best_conf[cand.value], cand.conf)
        ordered = sorted(weights.items(), key=lambda kv: -kv[1])
        value, top_weight = ordered[0]
        runner_weight = ordered[1][1] if len(ordered) > 1 else 0.0
        values[field_name] = value
        margin = 1.0 if runner_weight == 0 else max(0.15, 1.0 - runner_weight / top_weight)
        confs[field_name] = min(0.98, best_conf[value] * (0.6 + 0.4 * margin))
        conflicts[field_name] = (len(ordered) > 1
                                 and runner_weight >= 0.6 * top_weight)
    return values, confs, conflicts


def merge_flags(candidates_per_field: dict, home_world):
    """Union risk flags across pages (flags accumulate rather than conflict),
    with embargo inference from the home world."""
    flags = set()
    conf = 0.0
    for cand in candidates_per_field.get("risk_flags", []):
        if cand.value and cand.value != "none":
            flags.update(cand.value.split("|"))
        conf = max(conf, cand.conf)
    if home_world in vocab.EMBARGOED_WORLDS_ALWAYS:
        flags.add("planetary_embargo")
        conf = max(conf, 0.9)
    return flags, conf
