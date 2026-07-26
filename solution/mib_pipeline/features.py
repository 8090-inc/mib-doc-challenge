"""Feature builder shared by training (scripts_dev/train_model.py) and the
runtime adjudicator. Must stay deterministic and dependency-light."""

from . import vocab

FEE_VALS = ["paid", "waived", "unpaid", "unknown", None]
VISA_VALS = vocab.VISA_CLASSES + [None]
REASONS = ["adjudicator_note_approves", "adjudicator_note_denies",
           "disqualifying_flag", "fee_unknown", "fee_unpaid", "transit_visa",
           "embargoed_world", "embargoed_world_non_dip", "revoked_sponsor",
           "stale_arrival", "arrival_missing_or_hidden", "review_flag", "clean"]
PAGE_TYPES = ["intake_form", "biometric_slip", "sponsor_letter",
              "inspection_stamp", "registry_extract", "prior_incident",
              "fee_receipt", "adjudicator_note", ""]


def build_features(d: dict) -> dict:
    """d: the per-case evidence/debug record."""
    values = d.get("values", {})
    confs = d.get("confs", {})
    flags = set(d.get("belief_flags") or [])
    special = d.get("special") or {}
    details = d.get("page_details") or []
    reason = (d.get("reason") or "clean").split(":")[0]

    f = {}
    for fee in FEE_VALS:
        f[f"fee_{fee}"] = 1.0 if values.get("fee_status") == fee else 0.0
    for visa in VISA_VALS:
        f[f"visa_{visa}"] = 1.0 if values.get("visa_class") == visa else 0.0
    for flag in vocab.RISK_FLAGS:
        f[f"flag_{flag}"] = 1.0 if flag in flags else 0.0
    f["n_flags"] = float(len(flags))
    for r in REASONS:
        f[f"reason_{r}"] = 1.0 if reason == r else 0.0
    types = [p.get("type") for p in details]
    for pt in PAGE_TYPES:
        f[f"has_{pt or 'unknown_page'}"] = 1.0 if pt in types else 0.0
    f["n_pages"] = float(len(details))
    f["n_unclassified"] = float(sum(1 for p in details if not p.get("type")))
    f["n_scanned"] = float(sum(1 for p in details if p.get("scanned")))
    f["min_page_conf"] = min([p.get("conf", 1.0) for p in details] or [1.0])
    f["mean_page_conf"] = (sum(p.get("conf", 1.0) for p in details) / len(details)
                           if details else 0.0)
    f["damage"] = float(d.get("damage") or 0.0)
    f["trap"] = 1.0 if d.get("trap") else 0.0
    f["ocr_pages"] = float(d.get("ocr_pages") or 0)
    for key in ["applicant_name", "species_code", "home_world", "visa_class",
                "sponsor_id", "arrival_date", "declared_purpose", "fee_status"]:
        f[f"conf_{key}"] = float(confs.get(key, 0.0))
        f[f"miss_{key}"] = 0.0 if values.get(key) else 1.0
    f["bio_conf"] = float(special.get("bio_conf") or -1.0)
    f["has_note"] = 1.0 if special.get("notes") else 0.0
    f["n_stamps"] = float(len(d.get("stamps") or []))
    f["conflict_name"] = 1.0 if (d.get("conflicts") or {}).get("applicant_name") else 0.0
    f["conflict_sponsor"] = 1.0 if (d.get("conflicts") or {}).get("sponsor_id") else 0.0
    f["wolf_non_dip"] = 1.0 if (values.get("home_world") == "Wolf-1061c"
                                and values.get("visa_class") != "DIP-1") else 0.0
    f["revoked_sponsor"] = 1.0 if values.get("sponsor_id") in vocab.REVOKED_SPONSORS else 0.0
    return f


# Cascade rungs that stay forced regardless of model probabilities
# (100%-pure on train given their evidence actually extracted).
FORCED = {"adjudicator_note_approves": "APPROVED",
          "adjudicator_note_denies": "DENIED",
          "transit_visa": "DENIED",
          "fee_unpaid": "DENIED",
          "fee_unknown": "NEEDS_REVIEW",
          "embargoed_world": "DENIED",
          "embargoed_world_non_dip": "DENIED",
          "disqualifying_flag": "DENIED"}
