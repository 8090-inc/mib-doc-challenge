"""Field parsing (per page) + cross-page merge with source precedence."""
import re

from rapidfuzz import fuzz

import vocab

# (canonical label, internal field) -- longest / most specific first
LABEL_FIELDS = [
    ("case id", "case_id"),
    ("registry name", "reg_name"),
    ("applicant", "applicant_name"),
    ("species code", "species_code"),
    ("species match", "species_code"),
    ("home world", "home_world"),
    ("visa class", "visa_class"),
    ("sponsor id", "sponsor_id"),
    ("arrival date", "arrival_date"),
    ("declared purpose", "declared_purpose"),
    ("fee status", "fee_status"),
    ("waiver code", "waiver_code"),
    ("amount", "amount"),
    ("observed flags", "risk_flags"),
    ("registry status", "registry_status"),
    ("biometric confidence", "biometric_conf"),
]
LABEL_KEYS = [k for k, _ in LABEL_FIELDS]

# span texts that are decorative placeholders, never field values
_NON_VALUE_RE = re.compile(r"\b(PASSPORT|REGISTRY|SCAN|SPECIMEN)\s+IMAGE\b|"
                           r"\bEYES ONLY\b|Packet MIB-|Synthetic hiring", re.I)


def _norm_label(s):
    return re.sub(r"[^a-z]", "", s.lower())


_NORM_LABEL_KEYS = [(_norm_label(k), f) for k, f in LABEL_FIELDS]


def _match_label(left, fuzzy=False):
    """Map a left-of-colon (or standalone) label token to an internal field."""
    n = _norm_label(left)
    if not n:
        return None
    for key, field in _NORM_LABEL_KEYS:
        if n == key or n.startswith(key) or key in n:
            return field
    if fuzzy:
        best_field, best_score = None, 0
        for key, field in _NORM_LABEL_KEYS:
            sc = fuzz.ratio(n, key)
            if sc > best_score:
                best_score, best_field = sc, field
        if best_score >= 80:
            return best_field
    return None


def _center_y(bbox):
    return (bbox[1] + bbox[3]) / 2.0


def parse_page_fields(page, species_vocab=frozenset(), world_vocab=frozenset()):
    """Return {internal_field: value} parsed from one page's trusted evidence."""
    fields = {}
    spans = page.get("text_spans", [])

    # --- method A: inline "Label: value" in a single span ---
    consumed = set()
    for idx, s in enumerate(spans):
        t = s["text"]
        if ":" in t:
            left, right = t.split(":", 1)
            field = _match_label(left)
            if field and right.strip():
                fields.setdefault(field, right.strip())
                consumed.add(idx)

    # --- method B: standalone label span, value on same row to the right ---
    label_idx = {}
    for idx, s in enumerate(spans):
        if idx in consumed:
            continue
        t = s["text"].strip().rstrip(":")
        nt = _norm_label(t)
        field = _match_label(t)
        # only treat as a standalone label if the span is essentially just the
        # label text (short, no embedded value)
        if field is not None and len(nt) >= 4 and len(t) <= 24:
            label_idx[idx] = (field, s["bbox"])
    for idx, (field, bbox) in label_idx.items():
        if field in fields:
            continue
        lyc = _center_y(bbox)
        lx1 = bbox[2]
        # collect ALL value spans on the same row to the right of the label and
        # concatenate them left-to-right (a multi-word value like "reactor
        # maintenance" may be split across several spans)
        parts = []
        for j, s in enumerate(spans):
            if j == idx or j in label_idx:
                continue
            b = s["bbox"]
            t = s["text"].strip()
            if not t or _NON_VALUE_RE.search(t):
                continue
            if abs(_center_y(b) - lyc) <= 6 and b[0] >= lx1 - 4:
                parts.append((b[0], t))
        if parts:
            parts.sort()
            fields[field] = " ".join(t for _, t in parts)

    # --- narrative forms (sponsor letter / adjudicator note) from full text ---
    text_join = "\n".join(s["text"] for s in spans)
    _parse_narrative(text_join, fields, from_ocr=False)

    # --- OCR lines ---
    ocr_join = "\n".join(page.get("ocr_lines", []))
    if ocr_join:
        for ln in page.get("ocr_lines", []):
            if ":" in ln:
                left, right = ln.split(":", 1)
                field = _match_label(left, fuzzy=True)
                if field and right.strip():
                    fields.setdefault("ocr::" + field, right.strip())
        _parse_narrative(ocr_join, fields, from_ocr=True)
        # value-spotting: scan OCR text directly against known vocabularies,
        # scoped by form type -- robust to mangled OCR labels.
        _spot_values(ocr_join, page.get("form_type", "UNKNOWN"), fields,
                     species_vocab, world_vocab)

    return fields


VISA_TOKEN_RE = re.compile(r"[A-Za-z]{2,4}\s?[-—]?\s?\d")
WORLD_TOKEN_RE = re.compile(r"[A-Za-z][\w][\w\-]{1,}")
LONG_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z_]{4,}")


def _spot_values(text, form_type, fields, species_vocab, world_vocab):
    ft = form_type
    intakeish = ft in ("I8090", "REGISTRY", "UNKNOWN")

    def put(field, value):
        if value:
            fields.setdefault("ocr::" + field, value)

    if intakeish:
        # visa
        best_v, best_vs = None, 0
        for m in VISA_TOKEN_RE.finditer(text):
            tok = re.sub(r"\s", "", m.group(0)).upper().replace("—", "-")
            for v in vocab.VISA_CLASSES:
                sc = fuzz.ratio(tok, v)
                if sc > best_vs:
                    best_vs, best_v = sc, v
        if best_v and best_vs >= 74:
            put("visa_class", best_v)
        # species (sorted() learned vocab -> deterministic tie-break)
        sp = _best_vocab_match(text, list(vocab.SPECIES_SEED) + sorted(species_vocab),
                               LONG_TOKEN_RE, 74, normalize=vocab._clean_enum)
        if sp:
            put("species_code", sp)
        # home world (single + bigram tokens)
        wd = _best_world(text, list(vocab.HOME_WORLD_SEED) + sorted(world_vocab))
        if wd:
            put("home_world", wd)
        # sponsor + date
        sp_id = vocab.canon_sponsor(text)
        if sp_id:
            put("sponsor_id", sp_id)
        d = vocab.canon_date(text)
        if d:
            put("arrival_date", d)

    if ft == "FEE":
        low = text.lower()
        best_f, best_fs = None, 0
        for tok in re.findall(r"[a-z]{4,}", low):
            for f in vocab.FEE_STATUSES:
                sc = fuzz.ratio(tok, f)
                if sc > best_fs:
                    best_fs, best_f = sc, f
        if best_f and best_fs >= 80:
            put("fee_status", best_f)

    if ft == "B13":
        flags = vocab.canon_flags(text)
        if flags and flags != "none":
            put("risk_flags", flags)
        sp = _best_vocab_match(text, list(vocab.SPECIES_SEED) + sorted(species_vocab),
                               LONG_TOKEN_RE, 74, normalize=vocab._clean_enum)
        if sp:
            put("species_code", sp)

    # note-like pages: spot flags the note asserts (feeds disqualifier union)
    note_like = ft == "NOTE" or (
        ft == "UNKNOWN"
        and re.search(r"adjudicat|finding|reason|denied|embarg|disqualif|risk flag", text, re.I)
    )
    if note_like:
        flags = vocab.canon_flags(text)
        if flags and flags != "none":
            put("note_flags", flags)


def _best_vocab_match(text, choices, token_re, threshold, normalize=None):
    if not choices:
        return None
    keys = [normalize(c) if normalize else c for c in choices]
    best, best_sc = None, 0
    for m in token_re.finditer(text):
        tok = normalize(m.group(0)) if normalize else m.group(0)
        if len(tok) < 4:
            continue
        for i, k in enumerate(keys):
            sc = fuzz.ratio(tok, k)
            if sc > best_sc:
                best_sc, best = sc, choices[i]
    return best if best_sc >= threshold else None


def _best_world(text, worlds):
    words = re.findall(r"[A-Za-z][\w\-]+", text)
    cands = list(words)
    for i in range(len(words) - 1):
        cands.append(words[i] + " " + words[i + 1])
    best, best_sc = None, 0
    for c in cands:
        for w in worlds:
            sc = fuzz.ratio(c.lower(), w.lower())
            if sc > best_sc:
                best_sc, best = sc, w
    return best if best_sc >= 78 else None


def _has_disqualifier_phrase(text):
    """Fuzzy-detect an adjudicator note asserting a disqualifying risk flag.
    Handles OCR that splits/merges words (e.g. "Disqus tying tisk flag")."""
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)]
    cands = list(words)
    for i in range(len(words) - 1):
        cands.append(words[i] + words[i + 1])
    has_disq = any(fuzz.ratio(c, "disqualifying") >= 72 for c in cands)
    has_flag = re.search(r"[ftr]isk\s+fl|risk\s+fl", text, re.I) is not None \
        or any(fuzz.ratio(w, "flag") >= 80 for w in words)
    return has_disq and has_flag


def _fuzzy_finding(text):
    """Recover a mangled adjudicator finding from OCR.  DENIED only -- we never
    infer an APPROVED from noisy OCR (that would risk a catastrophic false
    approval); a genuine approval must come from a clean text-layer finding."""
    for tok in re.findall(r"[A-Za-z]{4,}", text):
        if fuzz.ratio(tok.upper(), "DENIED") >= 80:
            return "DENIED"
    return None


def _parse_narrative(text, fields, from_ocr):
    pref = "ocr::" if from_ocr else ""
    # sponsor attestation
    # NOTE: the declared purpose frequently wraps across a line break in the
    # attestation body ("expected on Earth for field\nrepair."), so the capture
    # must run to the sentence-ending period (with re.S) -- stopping at the first
    # newline truncated multi-word purposes to their first word ("field repair"
    # -> "field").  Whitespace is normalized by the caller.
    m = re.search(
        r"Sponsor\s+(SPN[-\s]?\d{3,4}).{0,60}?attests that\s+(.+?)\s+is expected on Earth for\s+(.+?)\s*\.",
        text, re.I | re.S)
    if m:
        fields.setdefault(pref + "sp_sponsor_id", m.group(1))
        fields.setdefault(pref + "sp_name", " ".join(m.group(2).split()))
        fields.setdefault(pref + "sp_purpose", " ".join(m.group(3).split()))
    mc = re.search(r"class\s+([A-Z]{2,7}-?\d)\s+compliance", text, re.I)
    if mc:
        fields.setdefault(pref + "sp_visa", mc.group(1))
    # adjudicator finding (exact, then fuzzy for OCR-mangled notes)
    mf = re.search(r"Finding:\s*(APPROVED|DENIED|NEEDS[_ ]?REVIEW|REVIEW)", text, re.I)
    if mf:
        val = mf.group(1).upper().replace(" ", "_")
        if val == "REVIEW":
            val = "NEEDS_REVIEW"
        fields.setdefault(pref + "note_finding", val)
    elif re.search(r"adjudicat|finding|reason", text, re.I):
        val = _fuzzy_finding(text)
        if val:
            fields.setdefault(pref + "note_finding", val)
    # flag(s) asserted by the note, e.g. "Disqualifying risk flag: planetary_embargo"
    mrf = re.search(r"risk flag[s]?\s*[:.\-]?\s*([A-Za-z_ ,|]+)", text, re.I)
    if mrf:
        fl = vocab.canon_flags(mrf.group(1))
        if fl and fl != "none":
            fields.setdefault(pref + "note_flags", fl)
    # An adjudicator note that asserts a *disqualifying* risk flag is a denial
    # signal even when OCR mangles which flag it is.  Detect the phrase fuzzily
    # (e.g. "Disqus tying tisk flag" -> "Disqualifying risk flag").
    if _has_disqualifier_phrase(text) and not re.search(r"no\s+disqualif|none", text, re.I):
        fields[pref + "note_disqualifier"] = "1"
    if re.search(r"sample denial", text, re.I):
        fields[pref + "note_sample"] = "1"
    if re.search(r"rescind", text, re.I):
        fields[pref + "note_rescinded"] = "1"
    if re.search(r"waiver (?:confirmed|approved|granted|applies|valid)|hardship waiver|"
                 r"diplomatic waiver|waiver on file", text, re.I):
        fields[pref + "waiver_confirmed"] = "1"
    # explicit in-document "Manual correction: sponsor is SPN-XXXX." annotation
    # supersedes the printed Sponsor ID (which may be a stale / superseded value
    # that coincidentally collides with the revoked set -> false denial).  Only
    # honored from the trusted text layer, never from OCR.
    if not from_ocr:
        mcorr = re.search(r"correction[^\n]{0,30}?sponsor\s+is\s+(SPN[-\s]?\d{3,4})",
                          text, re.I)
        if mcorr:
            fields["sponsor_corrected"] = mcorr.group(1)
    # in-document sponsor-revoked signal
    if re.search(r"sponsor[^\n]{0,40}revoked|status\s*:\s*revoked", text, re.I):
        fields[pref + "sponsor_revoked_signal"] = "1"
    # registry embargo status
    if re.search(r"\bEMBARGO\b", text, re.I):
        fields[pref + "registry_embargo"] = "1"


# ---- cross-page merge --------------------------------------------------------

# form precedence per output field (higher = preferred). Text-layer always beats
# OCR regardless of form rank.
FORM_RANK = {
    "applicant_name": {"I8090": 4, "B13": 3, "REGISTRY": 2, "SPONSOR": 1},
    "species_code": {"I8090": 3, "REGISTRY": 2, "B13": 1},
    "home_world": {"I8090": 2, "REGISTRY": 1},
    "visa_class": {"I8090": 2, "SPONSOR": 1},
    "sponsor_id": {"I8090": 2, "SPONSOR": 1},
    "arrival_date": {"I8090": 2, "REGISTRY": 1},
    "declared_purpose": {"I8090": 2, "SPONSOR": 1},
    "fee_status": {"FEE": 2},
    "risk_flags": {"B13": 2, "I8090": 1},
    "waiver_code": {"FEE": 2},
    "registry_status": {"REGISTRY": 2},
}


def _add_candidate(cands, field, value, form_type, from_ocr):
    if value is None:
        return
    value = str(value).strip()
    if not value:
        return
    cands.setdefault(field, []).append((value, form_type, from_ocr))


def collect_candidates(pages, species_vocab=frozenset(), world_vocab=frozenset()):
    """Return {output_field: [(value, form_type, from_ocr), ...]} and aux info."""
    cands = {}
    aux = {"note_finding": None, "note_finding_trusted": False,
           "note_sample": False, "note_rescinded": False,
           "sponsor_revoked_signal": False, "registry_embargo": False,
           "waiver_code": [], "registry_status": [], "note_flags": "none",
           "waiver_confirmed": False, "illegible_page": False,
           "uncertain_flags": False, "note_disqualifier": False,
           "damaged_key": False,
           # C2: a decision-relevant page can be PRESENT but UNREADABLE.
           "has_fee_page": False, "fee_page_read": False,
           # provenance (C6/A4/A2): filled in resolve_fields
           "sponsor_id_trusted": False, "sponsor_corroborated": False,
           "home_world_trusted": False, "sponsor_corrected": None,
           # --- evidence-quality signals (E-gate): captured for the positive
           # clean-flags approval gate.  Populated below / in resolve_fields.
           "n_pages": 0, "n_unknown_pages": 0, "n_ocr_pages": 0,
           "has_b13_page": False, "has_registry_page": False,
           "has_i8090_page": False,
           "flags_candidate_present": False, "flags_source_ocr": False,
           "positive_clean_flags": False, "registry_clear": False}
    aux["n_pages"] = len(pages)
    for page in pages:
        ft = page.get("form_type", "UNKNOWN")
        if page.get("illegible"):
            aux["illegible_page"] = True
        if ft == "FEE":
            aux["has_fee_page"] = True
        if ft == "UNKNOWN":
            aux["n_unknown_pages"] += 1
        if ft == "B13":
            aux["has_b13_page"] = True
        if ft == "REGISTRY":
            aux["has_registry_page"] = True
        if ft == "I8090":
            aux["has_i8090_page"] = True
        if page.get("from_ocr"):
            aux["n_ocr_pages"] += 1
        # C2b: a biometric slip is present but its observed-flags line could not
        # be read at all -> we cannot rule out a disqualifier -> force review.
        if ft == "B13" and page.get("illegible"):
            aux["uncertain_flags"] = True
        raw = parse_page_fields(page, species_vocab, world_vocab)
        for key, value in raw.items():
            from_ocr = key.startswith("ocr::")
            k = key[5:] if from_ocr else key
            if k == "note_finding":
                # prefer a clean text-layer finding over an OCR one
                if aux["note_finding"] is None or not from_ocr:
                    aux["note_finding"] = value
                    aux["note_finding_trusted"] = not from_ocr
                continue
            if k == "note_sample":
                aux["note_sample"] = True
                continue
            if k == "note_rescinded":
                aux["note_rescinded"] = True
                continue
            if k == "sponsor_revoked_signal":
                aux["sponsor_revoked_signal"] = True
                continue
            if k == "registry_embargo":
                aux["registry_embargo"] = True
                continue
            if k == "note_flags":
                cur = set(x for x in aux["note_flags"].split("|") if x and x != "none")
                cur |= set(value.split("|"))
                aux["note_flags"] = "|".join(sorted(cur)) if cur else "none"
                continue
            if k == "waiver_confirmed":
                aux["waiver_confirmed"] = True
                continue
            if k == "note_disqualifier":
                aux["note_disqualifier"] = True
                continue
            if k == "sponsor_corrected":
                # trusted text-layer correction supersedes the printed id
                aux["sponsor_corrected"] = value
                continue
            if k == "reg_name":
                _add_candidate(cands, "applicant_name", value, "REGISTRY", from_ocr)
                continue
            if k == "sp_name":
                _add_candidate(cands, "applicant_name", value, "SPONSOR", from_ocr)
                continue
            if k == "sp_purpose":
                _add_candidate(cands, "declared_purpose", value, "SPONSOR", from_ocr)
                continue
            if k == "sp_visa":
                _add_candidate(cands, "visa_class", value, "SPONSOR", from_ocr)
                continue
            if k == "sp_sponsor_id":
                _add_candidate(cands, "sponsor_id", value, "SPONSOR", from_ocr)
                continue
            if k == "waiver_code":
                aux["waiver_code"].append(value)
                continue
            if k == "registry_status":
                aux["registry_status"].append(value)
                _add_candidate(cands, "registry_status", value, ft, from_ocr)
                continue
            if k in ("amount", "biometric_conf", "case_id"):
                continue
            _add_candidate(cands, k, value, ft, from_ocr)
    return cands, aux


def _best_candidate_full(field, candidates):
    """Like _best_candidate but returns the full (value, form_type, from_ocr)
    tuple so callers can inspect provenance (text-layer vs OCR)."""
    ranks = FORM_RANK.get(field, {})
    def score(c):
        value, form_type, from_ocr = c
        return (0 if from_ocr else 100) + ranks.get(form_type, 0)
    return max(candidates, key=score)


def _best_candidate(field, candidates):
    return _best_candidate_full(field, candidates)[0]


def resolve_fields(pages, species_vocab, world_vocab):
    cands, aux = collect_candidates(pages, species_vocab, world_vocab)
    out = {}

    # applicant_name
    if "applicant_name" in cands:
        out["applicant_name"] = _clean_name(_best_candidate("applicant_name", cands["applicant_name"]))
    # species
    if "species_code" in cands:
        raw = _best_candidate("species_code", cands["species_code"])
        out["species_code"] = vocab.canon_species(raw, species_vocab)
    # home world
    if "home_world" in cands:
        best_hw = _best_candidate_full("home_world", cands["home_world"])
        raw = best_hw[0]
        out["home_world"] = vocab.canon_home_world(raw, world_vocab) if not _is_damaged(raw) else ""
        # A2: record whether the chosen home_world came from a trusted text-layer
        # span (not OCR) -- the gated embargo rule only fires on trusted worlds.
        if out.get("home_world") and not best_hw[2]:
            aux["home_world_trusted"] = True
    # visa
    if "visa_class" in cands:
        out["visa_class"] = vocab.canon_visa(_best_candidate("visa_class", cands["visa_class"]))
    # sponsor
    if "sponsor_id" in cands:
        # prefer a text-layer (non-OCR) candidate; record provenance +
        # corroboration for the revoked-sponsor robustness gate (C6/A4).
        canon_by_ocr = {False: [], True: []}
        for value, _ft, ocr in cands["sponsor_id"]:
            sp = vocab.canon_sponsor(value)
            if sp:
                canon_by_ocr[bool(ocr)].append(sp)
        chosen = None
        chosen_trusted = False
        if canon_by_ocr[False]:
            chosen = canon_by_ocr[False][0]
            chosen_trusted = True
        elif canon_by_ocr[True]:
            chosen = canon_by_ocr[True][0]
        if chosen:
            out["sponsor_id"] = chosen
            aux["sponsor_id_trusted"] = chosen_trusted
            all_canon = canon_by_ocr[False] + canon_by_ocr[True]
            aux["sponsor_corroborated"] = all_canon.count(chosen) >= 2
    # a trusted "Manual correction: sponsor is SPN-XXXX" annotation overrides the
    # printed id (which may be stale and collide with the revoked set).
    if aux.get("sponsor_corrected"):
        corr = vocab.canon_sponsor(aux["sponsor_corrected"])
        if corr:
            out["sponsor_id"] = corr
            aux["sponsor_id_trusted"] = True
            aux["sponsor_corroborated"] = False
    # arrival date
    if "arrival_date" in cands:
        for c in sorted(cands["arrival_date"], key=lambda c: (c[2],)):
            d = vocab.canon_date(c[0])
            if d:
                out["arrival_date"] = d
                break
    # declared purpose
    if "declared_purpose" in cands:
        dp = _best_candidate("declared_purpose", cands["declared_purpose"])
        if not _is_damaged(dp):
            out["declared_purpose"] = " ".join(dp.split())
    # fee status
    if "fee_status" in cands:
        fee_val = vocab.canon_fee(_best_candidate("fee_status", cands["fee_status"]))
        if fee_val in ("paid", "waived", "unpaid", "unknown"):
            out["fee_status"] = fee_val
    # C2a: a fee-receipt page is PRESENT but its status could not be read ->
    # treat the fee as "unknown" (both for output and adjudication) rather than
    # silently letting it fall through to an APPROVAL.  Clean cases where the fee
    # WAS read are unaffected (out["fee_status"] already set above).
    if aux.get("has_fee_page") and not out.get("fee_status"):
        out["fee_status"] = "unknown"
    # risk flags
    if "risk_flags" in cands:
        aux["flags_candidate_present"] = True
        best_rf = _best_candidate_full("risk_flags", cands["risk_flags"])
        raw = best_rf[0]
        aux["flags_source_ocr"] = bool(best_rf[2])
        out["risk_flags"] = vocab.canon_flags(raw)
        # A biometric slip that clearly lists observed flags we cannot read
        # (non-empty, not "none", but nothing canonicalizes) is a red flag: we
        # cannot rule out a disqualifier -> force review, not approval.
        r = str(raw).strip().lower()
        none_like = (not r) or re.fullmatch(r"(none|null|n/?a|-|\.)+", r) is not None
        if out["risk_flags"] == "none" and not none_like and len(r) >= 4:
            aux["uncertain_flags"] = True
        # POSITIVE clean-flags attestation: a trusted source EXPLICITLY read
        # "none" (not merely absent/empty).  This is the evidence that a packet
        # is clean, as opposed to us simply failing to find any flag.
        if out["risk_flags"] == "none" and none_like and r:
            aux["positive_clean_flags"] = True

    # A Planetary Registry that explicitly reads "Registry Status: CLEAR" is an
    # independent positive clean attestation.
    for rs in aux.get("registry_status", []):
        s = re.sub(r"[^a-z]", "", str(rs).lower())
        if s and (s.startswith("clear") or fuzz.ratio(s, "clear") >= 80):
            aux["registry_clear"] = True
            break

    # detect damaged/torn decision-relevant fields (value present but redacted)
    for fld in ("visa_class", "species_code", "home_world", "sponsor_id"):
        v = out.get(fld, "")
        if v and _is_damaged(v):
            aux["damaged_key"] = True
            out[fld] = ""  # do not emit a torn placeholder as a value

    aux["waiver_code"] = [w for w in aux["waiver_code"]]
    return out, aux, cands


def _is_damaged(v):
    return bool(re.search(
        r"\[.*\]|unreadable|registry lost|name cut|redacted|illegible|"
        r"\btorn\b|\blost\b|\bblank\b|cut out|missing|\bt0rn\b",
        v, re.I))


def _clean_name(v):
    v = " ".join(v.split())
    if _is_damaged(v):
        return ""
    return v
