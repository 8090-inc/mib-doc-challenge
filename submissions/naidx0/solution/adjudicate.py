"""Decision policy + calibrated confidence.

Rules are evaluated in the verified order (first match wins).  The paramount
constraint is ZERO catastrophic false approvals (predicting APPROVED when the
truth is DENIED): every denial pathway is checked before APPROVED can be
returned, and APPROVED requires sufficient trusted evidence.
"""
import datetime as _dt

from rapidfuzz import fuzz

import vocab

STALE_DAYS = 180

# Evidence-quality approval gate: "pos" => APPROVED requires a positive
# clean-flags attestation (a readable B13/I8090 "Observed flags: none").  This is
# the fix for catastrophic false approvals -- see the gate at the end of
# adjudicate().  ("pos_or_clean"/"off" retained only as documented alternatives.)
_GATE = "pos"
# Revoked-sponsor matching: "ocr" => a well-formed sponsor id in the fixed
# revoked set denies even from a single OCR read (an OCR misread landing in the
# 6-element revoked set is rare; missed revoked sponsors on image-only intake
# forms were common).  "strict" => require a text-layer/corroborated id.
_REVOKED_MODE = "ocr"


def _parse_iso(d):
    try:
        return _dt.date.fromisoformat(d)
    except (ValueError, TypeError):
        return None


def compute_ref_date(all_dates):
    """Reference receipt date = robust near-max arrival across the batch.

    Auto-calibrates to the packet-receipt era but is hardened against OCR-garbage
    dates: values are restricted to the contemporary packet era and a high
    percentile (not the raw max) is used so a stray misread year cannot inflate
    the stale cutoff and cause mass false denials.
    """
    dates = sorted(
        d for d in (_parse_iso(x) for x in all_dates)
        if d and 2020 <= d.year <= 2030
    )
    if not dates:
        return None
    idx = min(len(dates) - 1, int(round(0.97 * (len(dates) - 1))))
    return dates[idx]


def _has_waiver_code(aux):
    """A concrete, visible waiver code/confirmation (not N/A)."""
    for wc in aux.get("waiver_code", []):
        w = str(wc).strip().upper()
        if w and w not in {"N/A", "NA", "NONE", "-", ""}:
            return True
    if aux.get("waiver_confirmed"):
        return True
    return False


def _unpaid_excused(fields, aux):
    # An UNPAID fee is a hard denial unless an actual hardship/diplomatic waiver
    # code is visibly present.  DIP-1 alone does NOT excuse an *unpaid* fee
    # (verified: DIP-1 + unpaid + no waiver -> DENIED).
    return _has_waiver_code(aux)


def _waived_supported(fields, aux):
    # A WAIVED fee is acceptable for DIP-1, or for a non-DIP visa only with a
    # genuine (non-diplomatic) hardship waiver code.  A DIP-WAIVER on a non-DIP-1
    # visa is a mismatch and does NOT support the waiver (verified: MED-3 +
    # DIP-WAIVER -> NEEDS_REVIEW).
    if fields.get("visa_class") == "DIP-1":
        return True
    for wc in aux.get("waiver_code", []):
        w = str(wc).strip().upper()
        if not w or w in {"N/A", "NA", "NONE", "-", ""}:
            continue
        if "DIP" in w:  # diplomatic waiver on a non-diplomatic visa
            continue
        return True
    return bool(aux.get("waiver_confirmed"))


def _name_conflict(cands):
    names = [v for (v, ft, ocr) in cands.get("applicant_name", [])
             if not ocr and ft in ("I8090", "B13", "REGISTRY")]
    names = [" ".join(n.split()) for n in names
             if n and not n.startswith("[") and "cut out" not in n.lower()]
    uniq = list(dict.fromkeys(names))
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            # only a *clear* name difference is a real identity conflict; a small
            # edit distance is just OCR noise between the same name
            if fuzz.ratio(uniq[i].lower(), uniq[j].lower()) < 55:
                return True
    return False


def _sponsor_conflict(cands):
    ids = []
    for (v, ft, ocr) in cands.get("sponsor_id", []):
        if ocr:
            continue
        sp = vocab.canon_sponsor(v)
        if sp:
            ids.append(sp)
    return len(set(ids)) > 1


def adjudicate(fields, aux, cands, ref_date, use_embargo=False):
    flags = set()
    rf = fields.get("risk_flags", "none")
    if rf and rf != "none":
        flags = set(rf.split("|"))
    # flags asserted by an adjudicator note ("Disqualifying risk flag: X")
    for nf in aux.get("note_flags", "none").split("|"):
        if nf and nf != "none":
            flags.add(nf)
    # explicit registry EMBARGO status is a planetary_embargo disqualifier
    # (verified: visible EMBARGO -> DENIED in 9/10 cases, all visa classes)
    if aux.get("registry_embargo"):
        flags.add("planetary_embargo")

    visa = fields.get("visa_class", "")
    fee = fields.get("fee_status", "")
    sponsor = fields.get("sponsor_id", "")
    world = fields.get("home_world", "")
    arrival = fields.get("arrival_date", "")

    has_intake = any(ft == "I8090" for lst in cands.values() for (_, ft, _) in lst)
    has_registry = any(ft == "REGISTRY" for lst in cands.values() for (_, ft, _) in lst)
    has_b13 = any(ft == "B13" for lst in cands.values() for (_, ft, _) in lst)
    have_core = bool(fields.get("species_code") or visa or sponsor or has_intake or has_registry)

    # 0. Adjudicator note.  A note DENIAL is always honored (denial precedence).
    # (confidence values below are calibrated to empirical per-rule accuracy on
    # the labeled corpus so that confidence ~= P(our decision is correct).)
    finding = aux.get("note_finding")
    if finding == "DENIED":
        return "DENIED", 0.95, "adjudicator_note"

    # --- HARD DENIAL SIGNALS (C1) -------------------------------------------
    # These are evaluated BEFORE any APPROVED/NEEDS_REVIEW note override so that
    # a forged / mangled "Finding: APPROVED" line can never beat a genuine
    # disqualifier (which would be a catastrophic false approval).

    # 1. Disqualifying risk flag.
    dq = flags & vocab.DISQUALIFYING_FLAGS
    if dq:
        return "DENIED", 0.9, "disqualifying_flag:" + ",".join(sorted(dq))

    # 1b. Adjudicator note asserts a disqualifying flag (even if OCR mangled the
    # specific flag name) -> denial.
    if aux.get("note_disqualifier"):
        return "DENIED", 0.82, "note_disqualifier"

    # 2. Revoked sponsor.  Non-DIP-1 -> hard denial.  DIP-1 is sponsor-exempt
    # (verified: revoked + DIP-1 -> APPROVED) UNLESS a page that could hide a
    # disqualifier was illegible, in which case be conservative.
    #
    # C6/A4: a static-list membership may only DENY when the sponsor id came
    # from a TRUSTED TEXT-LAYER span (not OCR) or is corroborated across >=2
    # pages -- otherwise an OCR misread (e.g. SPN-4530 -> SPN-4040) could map a
    # valid sponsor INTO the revoked set and cause a false denial.  An explicit
    # in-document "sponsor ... revoked" signal always counts.
    if _REVOKED_MODE == "ocr":
        # A well-formed sponsor id that lands in the (small, fixed) revoked set is
        # honored even from a single OCR read: an OCR misread accidentally landing
        # in the 6-element revoked set is rare, whereas revoked sponsors on
        # image-only intake forms are common and were being missed.
        revoked_list = sponsor in vocab.REVOKED_SPONSORS
    else:
        revoked_list = (sponsor in vocab.REVOKED_SPONSORS) and (
            aux.get("sponsor_id_trusted") or aux.get("sponsor_corroborated"))
    revoked = bool(aux.get("sponsor_revoked_signal")) or revoked_list
    if revoked and visa != "DIP-1":
        return "DENIED", 0.86, "revoked_sponsor"

    # 3. Transit visa.
    if visa == "TRANSIT-7":
        return "DENIED", 0.92, "transit_visa"

    # 4. Unpaid fee without a visible waiver (DIP-1 does NOT excuse unpaid).
    if fee == "unpaid" and not _unpaid_excused(fields, aux):
        return "DENIED", 0.88, "unpaid_no_waiver"

    # 5. Stale arrival for non-DIP-1.
    ad = _parse_iso(arrival)
    if ad and ref_date and visa != "DIP-1":
        if ad < ref_date - _dt.timedelta(days=STALE_DAYS):
            return "DENIED", 0.9, "stale_arrival"

    # 0b. NOW honor an APPROVED/NEEDS_REVIEW adjudicator-note override -- only
    # after every hard denial above has had a chance to fire (C1).  Trusted only
    # from the clean text layer, never from noisy OCR.  A real "Finding:" line is
    # authoritative even under a "sample denial" watermark (the watermark alone
    # is the trap, not a signed finding).
    if finding in ("APPROVED", "NEEDS_REVIEW") and aux.get("note_finding_trusted"):
        conf = 0.93 if finding == "APPROVED" else 0.88
        return finding, conf, "adjudicator_note"

    # 2b. Revoked + DIP-1 with an illegible page that could hide a disqualifier
    # -> conservative review (soft signal, evaluated after the note override).
    if revoked and visa == "DIP-1" and aux.get("illegible_page"):
        return "NEEDS_REVIEW", 0.45, "revoked_dip_illegible"

    # 6. Embargoed home world for non-DIP-1 (A2, gated).  The bare home-world
    # heuristic stays DISABLED (net-negative under OCR misreads); this gated
    # version fires only when the home world came from a TRUSTED TEXT-LAYER span
    # and the visa is confidently a real non-DIP-1 class with no other flags.
    if (visa in ("XW-1", "XW-2", "MED-3") and aux.get("home_world_trusted")
            and world in vocab.EMBARGO_WORLDS and not flags):
        return "DENIED", 0.6, "embargo_world"

    # 7. Unknown fee.
    if fee == "unknown":
        return "NEEDS_REVIEW", 0.9, "fee_unknown"

    # 8. Missing / unreadable arrival date.
    if not arrival:
        return "NEEDS_REVIEW", 0.4, "missing_arrival"

    # 9. Review-only flags.
    rev = flags & vocab.REVIEW_FLAGS
    if rev:
        return "NEEDS_REVIEW", 0.87, "review_flag:" + ",".join(sorted(rev))

    # 9b. A biometric slip listed observed flags we could not read -> we cannot
    # rule out a disqualifier, so route to review rather than approve.
    if aux.get("uncertain_flags"):
        return "NEEDS_REVIEW", 0.45, "uncertain_flags"

    # 9c. A decision-relevant field was torn / redacted -> review.
    if aux.get("damaged_key"):
        return "NEEDS_REVIEW", 0.72, "damaged_field"

    # 9d. C2: a page is PRESENT but entirely unreadable (needed OCR, produced
    # nothing).  We cannot rule out a disqualifier hidden on it (e.g. a B13
    # biometric slip whose form type could not even be identified because the
    # scan was illegible) -> route to review, never approve.  This is the sole
    # guard once the OCR-misread revoked-sponsor gate (C6/A4) no longer fires on
    # such packets.
    if aux.get("illegible_page"):
        return "NEEDS_REVIEW", 0.5, "illegible_page"

    # 10. Cross-page contradictions / unsupported waiver.
    if _name_conflict(cands):
        return "NEEDS_REVIEW", 0.45, "name_conflict"
    if _sponsor_conflict(cands):
        return "NEEDS_REVIEW", 0.65, "sponsor_conflict"
    if fee == "waived" and not _waived_supported(fields, aux):
        return "NEEDS_REVIEW", 0.5, "unsupported_waiver"

    # 10b. MED-3 (medical/biological consultation) requires a clean biohazard
    # check.  With no biometric slip present at all, that clearance cannot be
    # verified -> review rather than approve (also guards against an unreadable
    # biohazard_red disqualifier).
    if visa == "MED-3" and not has_b13:
        return "NEEDS_REVIEW", 0.45, "med3_no_biometric"

    # 11. Insufficient trusted evidence.
    if not have_core:
        return "NEEDS_REVIEW", 0.6, "insufficient_evidence"

    # 12. Evidence-quality APPROVAL GATE.  Reaching here means no denial or
    # review rule fired -- but "no disqualifier found" is NOT the same as
    # "positively confirmed clean".  A catastrophic false approval happens when a
    # disqualifier exists but the flag-bearing evidence (a B13 biometric slip)
    # was missing or unreadable, so the pipeline saw no flag and defaulted to
    # clean.  Require POSITIVE confirmation: a readable trusted source that
    # actually attested "Observed flags: none" (positive_clean_flags).  Absent
    # that, we cannot rule out a hidden disqualifier -> route to review.
    positive_clean = bool(aux.get("positive_clean_flags"))
    degraded = bool(aux.get("illegible_page")) or aux.get("n_unknown_pages", 0) > 0 \
        or aux.get("n_ocr_pages", 0) > 0

    gate_ok = True
    if _GATE == "pos":
        gate_ok = positive_clean
    elif _GATE == "pos_or_clean":
        gate_ok = positive_clean or not degraded
    elif _GATE == "off":
        gate_ok = True

    if not gate_ok:
        # Calibrated to the empirical accuracy of a review on these unconfirmed
        # packets (P(review correct) ~= 0.33 on the labeled corpus; the rest are
        # true-APPROVED we conservatively hold, plus some true-DENIED).
        return "NEEDS_REVIEW", 0.33, "unverified_clean"

    # Confidence reflects corroboration strength (empirical ~0.67 overall; higher
    # when fully text-layer with multiple corroborating forms).
    ocr_used = any(ocr for lst in cands.values() for (_, _, ocr) in lst)
    if not ocr_used and has_intake and has_registry and has_b13:
        conf = 0.88
    elif ocr_used or not (has_intake or has_registry):
        conf = 0.63
    else:
        conf = 0.66
    return "APPROVED", conf, "clean"
