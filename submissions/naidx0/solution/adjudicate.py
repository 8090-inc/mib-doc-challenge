"""Decision policy + calibrated confidence.

Rules are evaluated in the verified order (first match wins).  The paramount
constraint is avoiding catastrophic false approvals (predicting APPROVED when
the truth is DENIED): every denial pathway is checked before APPROVED can be
returned, and APPROVED requires sufficient trusted evidence.

An approval is never granted merely because we FOUND no disqualifier -- absence
of evidence is not evidence of absence when half of a packet may be an
unreadable scan.  It is granted only when the disqualifying pathways have been
POSITIVELY EXCLUDED, by one of three routes:

  * `attested_clean`   -- a trusted source read "Observed flags: none" AND every
                          field the remaining denial rules key on was itself
                          positively read (diplomatic packets need fewer of
                          them, since DIP-1 is exempt from the sponsor, stale
                          date and soft-embargo pathways);
  * `consensus_clean`  -- LAYOUT CONSENSUS: every core identity field is printed
                          identically on two or more independent MIB forms, the
                          registry reads CLEAR, the fee was read, and no page of
                          the packet was degraded -- so no page went unread and
                          nothing could have hidden in one;
  * `clean`            -- the historical positive-attestation gate.
"""
import datetime as _dt

from rapidfuzz import fuzz

import vocab

STALE_DAYS = 180

# Evidence-quality approval gate: "pos" => APPROVED requires either a positive
# clean-flags attestation (a readable B13/I8090 "Observed flags: none") OR full
# LAYOUT CONSENSUS across independent forms -- see the gate at the end of
# adjudicate().  ("off" retained only as a documented alternative.)
_GATE = "pos"
# Revoked-sponsor matching: "ocr" => a well-formed sponsor id in the fixed
# revoked set denies even from a single OCR read (an OCR misread landing in the
# 6-element revoked set is rare; missed revoked sponsors on image-only intake
# forms were common).  "strict" => require a text-layer/corroborated id.
_REVOKED_MODE = "ocr"

# ---- Embargoed home worlds (policy table, learned from labeled examples the
# same way the revoked-sponsor table is; NOT a per-case lookup) ---------------
# HARD: every applicant whose registry/intake home world is one of these carries
# a planetary_embargo disqualifier and is denied regardless of visa class
# (verified on the labeled corpus: 50/50 DENIED, 50/50 carry planetary_embargo,
# across XW-1/XW-2/MED-3/DIP-1).
EMBARGO_WORLDS_HARD = frozenset({"Eris Relay", "TRAPPIST-1e"})
# SOFT: denied for every non-diplomatic class, but DIP-1 is exempt (verified:
# 51/51 non-DIP-1 DENIED; DIP-1 from the same world is adjudicated normally).
EMBARGO_WORLDS_SOFT = frozenset({"Wolf-1061c"})


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


def _field_agreement(cands, field, canon=None):
    """How many DISTINCT form types agree on the modal value of `field`.

    This is the core layout-consensus primitive: two independent MIB forms
    printing the same value is positive evidence that we read it correctly,
    which no single-source read can give us.
    """
    vals = []
    for (value, form_type, _ocr) in cands.get(field, []):
        cv = canon(value) if canon else " ".join(str(value).split()).lower()
        if cv:
            vals.append((cv, form_type))
    if not vals:
        return 0
    counts = {}
    for cv, _ft in vals:
        counts[cv] = counts.get(cv, 0) + 1
    top = max(sorted(counts), key=lambda k: counts[k])
    return len({ft for cv, ft in vals if cv == top})


def _name_agreement(cands):
    """Distinct form types whose applicant_name matches the primary reading.

    Uses fuzzy equality so OCR noise between two renderings of the same name
    still counts as agreement, while a genuinely different name does not.
    """
    vals = []
    for (value, form_type, from_ocr) in cands.get("applicant_name", []):
        v = " ".join(str(value).split())
        if not v or v.startswith("[") or "cut out" in v.lower():
            continue
        vals.append((v.lower(), form_type, from_ocr))
    if not vals:
        return 0
    primary = next((v for v, _ft, ocr in vals if not ocr), vals[0][0])
    return len({ft for v, ft, _o in vals if fuzz.ratio(v, primary) >= 80})


def _corroborated(aux, cands):
    """True when the packet is fully cross-corroborated AND fully legible.

    Every core identity field must be printed identically on at least two
    independent form types, the Planetary Registry must positively read CLEAR,
    and no page may have been degraded -- nothing needed OCR, nothing was left
    UNKNOWN, nothing was illegible.  Together these mean we demonstrably read
    every page of the packet, so a disqualifier cannot be hiding in one we
    silently failed to parse.
    """
    return (
        _name_agreement(cands) >= 2
        and _field_agreement(cands, "species_code") >= 2
        and _field_agreement(cands, "home_world") >= 2
        and _field_agreement(cands, "arrival_date") >= 2
        and bool(aux.get("registry_clear"))
        and aux.get("n_ocr_pages", 0) == 0
        and aux.get("n_unknown_pages", 0) == 0
        and not aux.get("illegible_page")
    )


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
    # A home world on the hard embargo list is itself a planetary_embargo
    # disqualifier even when the biometric slip never spelled the flag out.
    if fields.get("home_world", "") in EMBARGO_WORLDS_HARD:
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
        return "DENIED", 0.96, "adjudicator_note"

    # --- HARD DENIAL SIGNALS (C1) -------------------------------------------
    # A directly-observed disqualifying flag is checked BEFORE any
    # APPROVED/NEEDS_REVIEW note override, so that a forged / mangled
    # "Finding: APPROVED" line can never beat a visible disqualifier (which
    # would be a catastrophic false approval).

    # 1. Disqualifying risk flag.
    dq = flags & vocab.DISQUALIFYING_FLAGS
    if dq:
        return "DENIED", 0.93, "disqualifying_flag:" + ",".join(sorted(dq))

    # 1b. Adjudicator note asserts a disqualifying flag (even if OCR mangled the
    # specific flag name) -> denial.
    if aux.get("note_disqualifier"):
        return "DENIED", 0.82, "note_disqualifier"

    # 1c. A signed adjudicator finding is the TOP of the field-manual trusted-
    # evidence precedence ("visible MIB adjudicator stamp or signed manual
    # note"), above the intake form and the biometric slip.  Once no *visible*
    # disqualifier has fired it therefore outranks every DERIVED denial pathway
    # below (revoked-sponsor table, transit class, unpaid fee, stale date): the
    # human adjudicator saw the same packet and already ruled on it.  Verified
    # on the labeled corpus: a recovered "Finding:" line matches the truth
    # 248/248 times.  OCR-recovered findings are honored as well -- they are
    # just as accurate empirically, and the documented trap is a "sample
    # denial" WATERMARK, not a signed Finding: line.
    if finding in ("APPROVED", "NEEDS_REVIEW"):
        return finding, 0.95, "adjudicator_note"

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
        return "DENIED", 0.92, "revoked_sponsor"

    # 3. Transit visa.
    if visa == "TRANSIT-7":
        return "DENIED", 0.88, "transit_visa"

    # 4. Unpaid fee without a visible waiver (DIP-1 does NOT excuse unpaid).
    if fee == "unpaid" and not _unpaid_excused(fields, aux):
        return "DENIED", 0.88, "unpaid_no_waiver"

    # 5. Stale arrival for non-DIP-1.
    ad = _parse_iso(arrival)
    if ad and ref_date and visa != "DIP-1":
        if ad < ref_date - _dt.timedelta(days=STALE_DAYS):
            return "DENIED", 0.89, "stale_arrival"

    # 2b. Revoked + DIP-1 with an illegible page used to short-circuit to review
    # here, on the grounds that the unreadable page might hide a disqualifier.
    # That guard is redundant: DIP-1 is sponsor-exempt by policy, so the only
    # remaining denial routes are a risk flag, the fee, a hard-embargo world and
    # an adjudicator denial -- and the approval gate below already refuses to
    # approve unless the clean-flags attestation and the fee were POSITIVELY
    # read.  An illegible page therefore cannot carry such a packet to approval
    # on its own, and packets that are otherwise fully evidenced no longer get
    # held in review for a page the decision never depended on.  Removing the
    # special case is worth +0.18 on the training corpus with no change to the
    # catastrophic count.

    # 6. Soft-embargo home world: denied for every non-diplomatic class, DIP-1
    # exempt (verified 51/51 on the labeled corpus).  Unlike the hard list above
    # this does not present as a planetary_embargo flag, so it is its own rule.
    if visa != "DIP-1" and world in EMBARGO_WORLDS_SOFT:
        return "DENIED", 0.70, "embargo_world"

    # 7. Unknown fee.  (Confidence is the empirical accuracy of a review here:
    # the fee page was present but unreadable, and roughly half of those packets
    # turn out to be genuine reviews.)
    if fee == "unknown":
        # 0.86 was tried here and MEASURED WORSE (calibration 15.91 -> 15.88 on
        # the full training set).  The 44/44 evidence was about cases where the
        # GOLD fee is unknown; this rule fires when OUR READ is unknown, which
        # also covers packets whose true fee is paid or waived and simply could
        # not be read.  Those are not all review cases, so the rule is less
        # reliable than the gold statistic suggested.  Reverted to the measured
        # value.
        return "NEEDS_REVIEW", 0.56, "fee_unknown"

    # 8. Missing / unreadable arrival date (field manual: mark NEEDS_REVIEW).
    if not arrival:
        return "NEEDS_REVIEW", 0.35, "missing_arrival"

    # 9. Review-only flags.
    rev = flags & vocab.REVIEW_FLAGS
    if rev:
        return "NEEDS_REVIEW", 0.93, "review_flag:" + ",".join(sorted(rev))

    # 9b. A biometric slip listed observed flags we could not read -> we cannot
    # rule out a disqualifier, so route to review rather than approve.
    if aux.get("uncertain_flags"):
        return "NEEDS_REVIEW", 0.28, "uncertain_flags"

    # 9c. A decision-relevant field was torn / redacted -> review.
    if aux.get("damaged_key"):
        return "NEEDS_REVIEW", 0.72, "damaged_field"

    # 9c-bis. DIPLOMATIC PACKET WITH EVERY DENIAL PATHWAY POSITIVELY EXCLUDED.
    # A DIP-1 packet is sponsor-exempt, stale-date-exempt and soft-embargo-exempt
    # by policy, so exactly four things can deny it: a disqualifying risk flag,
    # an unpaid fee, a hard-embargo home world, and an adjudicator denial.  If we
    # positively READ "Observed flags: none" AND positively READ the fee as
    # paid/waived, all four have been excluded by evidence rather than by
    # absence.  The hedges further down (a second page that needed re-scanning,
    # an unsupported waiver, a missing biometric slip) are about evidence we did
    # not need, so they must not hold this packet in review.
    if (visa == "DIP-1" and aux.get("positive_clean_flags")
            and fee in ("paid", "waived")):
        return "APPROVED", 0.85, "attested_clean"

    # 9c-ter. The same argument generalised to every visa class.  A non-DIP-1
    # packet has three further denial pathways -- the revoked-sponsor table, the
    # stale-arrival cutoff and the embargoed home world -- and each of them is
    # only trustworthy if we actually READ the field it keys on.  So require a
    # positive, trusted read of every one of them (plus the clean-flags
    # attestation and the fee) before the secondary hedges are waived.  Nothing
    # here is an assumption: each denial route has been evaluated against a value
    # we recovered, not against a blank we failed to recover.
    if (aux.get("positive_clean_flags")
            and fee in ("paid", "waived")
            and visa
            and arrival
            and world and aux.get("home_world_trusted")
            and sponsor
            and (aux.get("sponsor_id_trusted") or aux.get("sponsor_corroborated"))):
        return "APPROVED", 0.85, "attested_clean"

    # 9d. C2: a page is PRESENT but entirely unreadable (needed OCR, produced
    # nothing).  We cannot rule out a disqualifier hidden on it (e.g. a B13
    # biometric slip whose form type could not even be identified because the
    # scan was illegible) -> route to review, never approve.  This is the sole
    # guard once the OCR-misread revoked-sponsor gate (C6/A4) no longer fires on
    # such packets.
    if aux.get("illegible_page"):
        return "NEEDS_REVIEW", 0.35, "illegible_page"

    # 10. Cross-page contradictions / unsupported waiver.
    if _name_conflict(cands):
        return "NEEDS_REVIEW", 0.70, "name_conflict"
    if _sponsor_conflict(cands):
        return "NEEDS_REVIEW", 0.65, "sponsor_conflict"
    if fee == "waived" and not _waived_supported(fields, aux):
        return "NEEDS_REVIEW", 0.33, "unsupported_waiver"

    # 10b. MED-3 (medical/biological consultation) requires a clean biohazard
    # check.  With no biometric slip present at all, that clearance cannot be
    # verified -> review rather than approve (also guards against an unreadable
    # biohazard_red disqualifier).
    if visa == "MED-3" and not has_b13:
        return "NEEDS_REVIEW", 0.20, "med3_no_biometric"

    # 11. Insufficient trusted evidence.
    if not have_core:
        return "NEEDS_REVIEW", 0.6, "insufficient_evidence"

    # 11b. FEE EVIDENCE.  The fee is one of the four hard denial conditions, so
    # "we never found a fee receipt at all" is not the same as "the fee was
    # fine".  Unless the rest of the packet is fully corroborated (below), an
    # unread fee is treated like the manual's `unknown` -> review.  This closes
    # the two remaining catastrophic false approvals, both of which were
    # genuinely UNPAID packets whose receipt page we never recovered.
    if fee not in ("paid", "waived") and not _corroborated(aux, cands):
        return "NEEDS_REVIEW", 0.34, "fee_unverified"

    # 12. APPROVAL GATE.  Reaching here means no denial or review rule fired --
    # but "no disqualifier found" is NOT the same as "positively confirmed
    # clean".  A catastrophic false approval happens when a disqualifier exists
    # but the flag-bearing evidence (a B13 biometric slip) was missing or
    # unreadable, so the pipeline saw no flag and defaulted to clean.
    #
    # Two independent ways to clear the gate:
    #
    #  (a) POSITIVE ATTESTATION -- a readable trusted source actually stated
    #      "Observed flags: none" (positive_clean_flags); or
    #
    #  (b) LAYOUT CONSENSUS -- every core identity field is corroborated by two
    #      or more independent form types, the registry reads CLEAR, the fee was
    #      positively read, and no page of the packet was degraded (nothing
    #      needed OCR, nothing was unclassifiable, nothing was illegible).  A
    #      packet that intact is one whose pages we demonstrably all read, so a
    #      disqualifier could not have hidden in a page we failed to parse.
    #      Restricted to packets whose remaining denial pathways are also
    #      covered by that same corroboration: DIP-1 is sponsor-, stale-date-
    #      and soft-embargo-exempt by policy, and for every other class we
    #      additionally require the sponsor id to agree across two sources so
    #      the revoked-sponsor table cannot have been dodged by a misread id.
    positive_clean = bool(aux.get("positive_clean_flags"))
    consensus = _corroborated(aux, cands) and fee in ("paid", "waived") and (
        visa == "DIP-1"
        or _field_agreement(cands, "sponsor_id", vocab.canon_sponsor) >= 2)

    gate_ok = (positive_clean or consensus) if _GATE == "pos" else True

    if consensus and not positive_clean:
        return "APPROVED", 0.78, "consensus_clean"

    if not gate_ok:
        # Calibrated to the empirical accuracy of a review on these unconfirmed
        # packets (P(review correct) ~= 0.33 on the labeled corpus; the rest are
        # true-APPROVED we conservatively hold, plus some true-DENIED).
        return "NEEDS_REVIEW", 0.33, "unverified_clean"

    # Confidence = empirical precision of this approval pathway on the labeled
    # corpus (~0.85); the OCR/form-count split below it was not predictive.
    return "APPROVED", 0.87, "clean"
