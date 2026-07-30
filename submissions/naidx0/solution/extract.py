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
    # the compact scanned intake variant labels the same field just "Purpose",
    # which is too far from "declared purpose" for the fuzzy label matcher
    ("purpose", "declared_purpose"),
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


# ---- batch-learned vocabularies ---------------------------------------------
#
# declared_purpose and the applicant name tokens are drawn from small closed
# pools, exactly like species_code / home_world, so an OCR'd value can be
# snapped back onto the set of values observed in CLEAN text layers elsewhere in
# the batch.  solution.py owns the vocabulary plumbing and is not ours to
# change, so these extra vocabularies travel inside the species set behind a
# private prefix and are split back out here.
VOCAB_PURPOSE_PREFIX = "\x01P"
VOCAB_NAME_PREFIX = "\x01N"


def split_vocab(species_vocab):
    """(species, declared_purposes, name_tokens) from the packed species set."""
    species, purposes, names = set(), set(), set()
    for value in species_vocab:
        if value.startswith(VOCAB_PURPOSE_PREFIX):
            purposes.add(value[len(VOCAB_PURPOSE_PREFIX):])
        elif value.startswith(VOCAB_NAME_PREFIX):
            names.add(value[len(VOCAB_NAME_PREFIX):])
        else:
            species.add(value)
    return frozenset(species), frozenset(purposes), frozenset(names)


# Declared purposes form a small closed pool and the value has already been
# located behind a "Purpose" label, so the only question is WHICH pool member a
# mangled read is -- not whether it is a purpose at all.  The acceptance ratio is
# therefore low: a two-word purpose read through a bad scan ("reseter metaronce")
# sits well under the usual 70s cut-off but is still unambiguous within the pool.
_PURPOSE_MIN_RATIO = 60


def _canon_purpose(value, purpose_vocab):
    """Snap an OCR'd declared purpose onto the batch-learned purpose set."""
    if not value or not purpose_vocab:
        return value
    v = " ".join(value.split()).lower()
    best, best_score = None, 0
    for choice in sorted(purpose_vocab):  # sorted -> deterministic tie-break
        score = fuzz.ratio(v, choice.lower())
        if score > best_score:
            best_score, best = score, choice
    return best if best_score >= _PURPOSE_MIN_RATIO else value


def _canon_name(value, name_vocab):
    """Repair an OCR'd applicant name token-by-token against the learned name
    tokens.  A token is only replaced on an unambiguous win (high score AND a
    clear margin over the runner-up), so a genuinely unseen name is left alone
    rather than snapped onto some other applicant's name."""
    if not value or not name_vocab:
        return value
    choices = sorted(name_vocab)
    out = []
    for token in value.split():
        core = re.sub(r"[^A-Za-z]", "", token)
        if token in name_vocab or len(core) < 4:
            out.append(token)
            continue
        best, best_score, runner_up = None, 0, 0
        for choice in choices:
            score = fuzz.ratio(core.lower(), choice.lower())
            if score > best_score:
                runner_up = best_score
                best_score, best = score, choice
            elif score > runner_up:
                runner_up = score
        if best is not None and best_score >= 80 and best_score - runner_up >= 6:
            out.append(best)
        else:
            out.append(token)
    return " ".join(out)


# ---- OCR line -> (label, value) ---------------------------------------------
#
# On a degraded scan the label/value separator is routinely lost ("Fee Status
# Paig") and the label itself is mangled ("Species Mitac ALPHA_DRAGEETAN"), so
# the plain 'split on ":"' path recovers nothing.  The helpers below recover the
# same evidence by fuzzy-matching the leading words of a line against the known
# label vocabulary.  They never invent a value: whatever follows the label is
# passed through verbatim to the normal canonicalizers.

# Page furniture (stamps / watermarks) that OCR merges into a field value
# ("Applicant: Qorix Arivara CASEWORK").  Never part of a real value.
_STAMP_PHRASES = [
    "casework", "copy artifact", "duplicate", "eyes only", "mib eyes only",
    "passport image", "primary intake record", "registry image", "sample denial",
    "scan image", "scan tab", "specimen image",
    "synthetic hiring challenge document",
]
_STAMP_KEYS = sorted({_norm_label(p) for p in _STAMP_PHRASES})
_STAMP_MAXWORDS = max(len(p.split()) for p in _STAMP_PHRASES)


def _strip_stamps(value):
    """Remove stamp/watermark words OCR merged into a field value."""
    words = value.split()
    n = len(words)
    if not n:
        return ""
    drop = [False] * n
    for i in range(n):
        for ln in range(1, _STAMP_MAXWORDS + 1):
            if i + ln > n:
                break
            frag = _norm_label(" ".join(words[i:i + ln]))
            if len(frag) < 7:
                continue
            if any(fuzz.ratio(frag, k) >= 85 for k in _STAMP_KEYS):
                for j in range(i, i + ln):
                    drop[j] = True
                break
    kept = [w for j, w in enumerate(words) if not drop[j]]
    return " ".join(kept).strip(" |*_-.,;:'\"()[]")


def _fuzzy_label(frag, threshold):
    """Best internal field for a normalized label fragment, or None."""
    best_field, best_score = None, 0
    for key, field in _NORM_LABEL_KEYS:
        sc = fuzz.ratio(frag, key)
        if sc > best_score:
            best_score, best_field = sc, field
    return best_field if best_score >= threshold else None


def _ocr_label_value(line):
    """Parse one OCR line into (field, value); (None, None) if it is not a
    'label [:] value' line.  Shorter label prefixes are tried first so that a
    longer prefix can never swallow the value itself."""
    if ":" in line:
        left, right = line.split(":", 1)
        field = _match_label(left, fuzzy=True)
        if field and right.strip():
            return field, right.strip()
    words = line.split()
    for n in (1, 2, 3):
        if len(words) <= n:
            break
        frag = _norm_label(" ".join(words[:n]))
        if len(frag) < 6:
            continue
        field = _fuzzy_label(frag, 82)
        if field:
            value = " ".join(words[n:]).strip()
            if value:
                return field, value
    return None, None


def _ocr_bare_label(line):
    """Field for a line that is JUST a label (stacked layout), else None."""
    t = line.strip().rstrip(":").strip()
    if not t or len(t.split()) > 3 or len(t) > 26:
        return None
    frag = _norm_label(t)
    if len(frag) < 6:
        return None
    return _fuzzy_label(frag, 85)


def _ocr_value_accepted(field, value, species_vocab, world_vocab):
    """Gate an OCR label/value read for the strongly-typed fields.

    The label pass and the value-spotting pass write to the SAME key and the
    first writer wins, so an unusable label read ("Sponsor ID: 5°N-@71") would
    otherwise shadow a good value recovered by the pattern scan later on the
    same page.  For fields whose value space is closed (or a strict pattern) we
    therefore only accept a read that actually canonicalizes; anything else is
    dropped so another pass or another page can supply the value.  Free-text
    fields (name, purpose, flags, waiver code) are accepted as-is.
    """
    if field == "sponsor_id":
        return bool(vocab.canon_sponsor(value))
    if field == "arrival_date":
        return bool(vocab.canon_date(value))
    if field == "fee_status":
        return vocab.canon_fee(value) in vocab.FEE_STATUSES
    if field == "visa_class":
        return vocab.canon_visa(value) in vocab.VISA_CLASSES
    if field == "species_code":
        known = set(vocab.SPECIES_SEED) | set(species_vocab)
        return vocab.canon_species(value, species_vocab) in known
    if field == "home_world":
        known = set(vocab.HOME_WORLD_SEED) | set(world_vocab)
        return vocab.canon_home_world(value, world_vocab) in known
    return True


# Words a biometric slip uses to attest that NO flags were observed.
_NONE_WORDS = ("na", "nil", "none", "null")


def _reads_as_none(raw):
    """True iff an observed-flags value is a (possibly OCR-mangled) "none".

    Recovering the "none" reading is what lets a genuinely clean packet be
    approved, so this must never fire on a mangled REAL flag -- that would be a
    catastrophic false approval.  The guard is length: the shortest canonical
    risk flag is 14 characters ("active_warrant"), and OCR garbles characters
    rather than deleting two thirds of them, so a value that survives as <= 7
    alphanumerics cannot be a mangled flag name.  Within that length budget a
    single-character misread of "none" ("nore", "hone", "n0ne") still scores 75.
    """
    s = re.sub(r"[^a-z0-9]", "", str(raw).strip().lower())
    if not s:
        return True
    if len(s) > 7:
        return False
    return max(fuzz.ratio(s, w) for w in _NONE_WORDS) >= 70


def _rescue_flag_token(chunk):
    """Recover a badly OCR-mangled risk-flag name from one value chunk.

    Reached only for text the strict canonicaliser rejected, on a line that
    clearly carried SOME flag (long, not none-like).  Naming a flag can only
    make the decision more conservative -- deny or review, never approve -- so a
    wrong guess here cannot manufacture a false approval; the real cost is a
    wrong risk_flags value, hence the demand for a clear winner.  Length
    agreement is used as an independent cue because OCR substitutes characters
    far more often than it inserts or deletes them.
    """
    s = re.sub(r"[^a-z]", "", str(chunk).lower())
    if len(s) < 8:
        return None
    best, best_score, runner_up = None, 0.0, 0.0
    for flag in vocab.RISK_FLAGS:  # fixed list -> deterministic iteration
        key = flag.replace("_", "")
        score = fuzz.ratio(s, key) - 2.0 * abs(len(s) - len(key))
        if score > best_score:
            runner_up = best_score
            best_score, best = score, flag
        elif score > runner_up:
            runner_up = score
    if best is not None and best_score >= 45 and best_score - runner_up >= 10:
        return best
    return None


def _rescue_flags(raw):
    """canon_flags for OCR text the strict matcher could not resolve."""
    found = set()
    for chunk in re.split(r"[|,;/]+|\s{2,}", str(raw)):
        chunk = chunk.strip()
        if not chunk:
            continue
        got = vocab.canon_flag_token(chunk) or _rescue_flag_token(chunk)
        if got:
            found.add(got)
    if not found:
        # the separators may themselves have been lost -- try the whole line
        got = _rescue_flag_token(raw)
        if got:
            found.add(got)
    return "|".join(sorted(found)) if found else "none"


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
    ocr_lines = page.get("ocr_lines", [])
    ocr_join = "\n".join(ocr_lines)
    if ocr_join:
        pending_label = None
        for ln in ocr_lines:
            field, value = _ocr_label_value(ln)
            if field and value:
                pending_label = None
                value = _strip_stamps(value)
                if value and _ocr_value_accepted(field, value, species_vocab,
                                                 world_vocab):
                    fields.setdefault("ocr::" + field, value)
                continue
            bare = _ocr_bare_label(ln)
            if bare:
                # stacked layout: the value is on the following line
                pending_label = bare
                continue
            if pending_label:
                value = _strip_stamps(ln.strip())
                if value and _ocr_value_accepted(pending_label, value,
                                                 species_vocab, world_vocab):
                    fields.setdefault("ocr::" + pending_label, value)
                pending_label = None
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
    # Explicit in-document "Manual correction: <field> is <value>." annotations.
    # A signed manual note is the TOP of the field manual's trusted-evidence
    # precedence, above the printed form fields, so the correction supersedes
    # whatever the form said -- the printed value may be stale (a superseded
    # sponsor id that collides with the revoked set -> false denial), or may
    # belong to a second applicant whose pages were filed into the same packet.
    # Only honored from the trusted text layer, never from OCR.
    if not from_ocr:
        for pattern, key in _CORRECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                fields[key] = m.group(1)
    # in-document sponsor-revoked signal
    if re.search(r"sponsor[^\n]{0,40}revoked|status\s*:\s*revoked", text, re.I):
        fields[pref + "sponsor_revoked_signal"] = "1"
    # registry embargo status
    if re.search(r"\bEMBARGO\b", text, re.I):
        fields[pref + "registry_embargo"] = "1"


# "Manual correction: <subject> is <value>." -- (compiled pattern, aux key).
# Each value pattern is deliberately narrow so the annotation can only supply a
# well-formed value; whatever it yields still goes through the normal
# canonicalizer before it is used.
# Case-insensitivity is scoped to the ANNOUNCEMENT only: the applicant value
# pattern relies on capitalisation to tell a name from the prose around it.
_CORRECTION_PATTERNS = tuple(
    (re.compile(r"(?i:correction[^\n]{0,30}?" + subject + r"\s+is\s+)" + value_re),
     key)
    for subject, value_re, key in (
        (r"sponsor", r"(SPN[-\s]?\d{3,4})", "sponsor_corrected"),
        (r"visa\s+class", r"([A-Za-z]{2,8}\s?-\s?\d)", "visa_corrected"),
        (r"fee\s+status", r"([A-Za-z]{4,8})", "fee_corrected"),
        (r"applicant",
         r"([A-Z][A-Za-z'\-]{1,15}(?:\s+[A-Z][A-Za-z'\-]{1,15}){0,2})",
         "applicant_corrected"),
    )
)


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


_FLAG_CONTEXT_RE = re.compile(r"obs|flag|risk|reason|finding", re.I)
_UNDERSCORE_TOKEN_RE = re.compile(r"[A-Za-z]{3,25}_[A-Za-z_]{3,30}")


def _page_flag_scan(page):
    """Recover risk flags from the WHOLE page text of a flag-bearing page.

    The labeled "Observed flags:" line is the primary channel, but on degraded
    scans the label is often destroyed while the flag word itself survives
    elsewhere in the OCR soup.  Three additional channels, page-gated to the
    two form types that legitimately print flags (B-13 slip, adjudicator
    note), each of which can only ADD flags -- never assert a clean "none":

      1. canonical-name substring over space->underscore-folded lines (a flag
         name printed intact but on an unlabeled line);
      2. fuzzy 1-3-word n-grams, restricted to lines carrying an
         obs/flag/risk/reason/finding context word, matched >= 76 against the
         flag names with underscores stripped (label survived, value mangled);
      3. underscore-shaped tokens anywhere on the page, through the standard
         canonicalizer -- the token shape itself (letters_letters) keeps
         ordinary prose out.
    """
    lines = list(page.get("ocr_lines") or [])
    for s in page.get("text_spans") or []:
        lines.append(s.get("text", ""))
    found = set()
    for line in lines:
        low = " ".join(str(line).lower().split())
        folded = low.replace(" ", "_")
        for fl in vocab.RISK_FLAGS:
            if fl in folded:
                found.add(fl)
        if _FLAG_CONTEXT_RE.search(low):
            words = [w for w in re.split(r"[^a-z]+", low) if len(w) >= 3]
            for i in range(len(words)):
                for j in (1, 2, 3):
                    if i + j > len(words):
                        break
                    gram = "".join(words[i:i + j])
                    for fl in vocab.RISK_FLAGS:
                        if fuzz.ratio(gram, fl.replace("_", "")) >= 76:
                            found.add(fl)
        for tok in _UNDERSCORE_TOKEN_RE.findall(str(line)):
            c = vocab.canon_flag_token(tok)
            if c:
                found.add(c)
    return found


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
           "applicant_corrected": None, "visa_corrected": None,
           "fee_corrected": None,
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
        # Whole-page flag recovery on the two flag-bearing form types; the
        # candidates join the risk_flags union in resolve_fields.
        if ft in ("B13", "NOTE"):
            scanned = _page_flag_scan(page)
            if scanned:
                _add_candidate(cands, "risk_flags", "|".join(sorted(scanned)),
                               ft, bool(page.get("from_ocr")))
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
            if k in ("applicant_corrected", "visa_corrected", "fee_corrected"):
                aux[k] = value
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
            if k == "amount":
                # The receipt's amount corroborates the fee status when the
                # status word itself is unreadable: the fee is a fixed charge, so
                # a non-zero amount means it was paid and a zero amount means it
                # was waived.  Stored only as a fallback; a directly-read status
                # always wins.
                aux.setdefault("fee_amounts", []).append(value)
                continue
            if k in ("biometric_conf", "case_id"):
                continue
            _add_candidate(cands, k, value, ft, from_ocr)
    return cands, aux


def _consensus_name(candidates, name_vocab):
    """Pick the applicant name the packet AGREES on.

    Taking the highest-ranked form's read on its own loses whenever that page is
    the most damaged one -- a garbled "Wiewvors Vests" on the intake form beat a
    clean "Miravara Veeix" printed on two other pages of the same packet.  The
    readings are therefore clustered by fuzzy identity (so OCR noise between two
    renderings of the SAME name counts as agreement) and the cluster with the
    most independent support wins; form precedence only chooses the wording
    INSIDE the winning cluster.  With a single candidate this is exactly the old
    behaviour.
    """
    ranks = FORM_RANK.get("applicant_name", {})
    prepared = []
    for value, form_type, from_ocr in candidates:
        name = _clean_name(value)
        if not name:
            continue
        if from_ocr:
            name = _canon_name(_trim_name_tail(name), name_vocab)
        if not name:
            continue
        prepared.append((name, form_type, bool(from_ocr)))
    if not prepared:
        return None
    clusters = []
    for item in prepared:
        for members in clusters:
            if fuzz.ratio(item[0].lower(), members[0][0].lower()) >= 80:
                members.append(item)
                break
        else:
            clusters.append([item])

    def cluster_score(members):
        # a text-layer reading is worth more than an OCR one; distinct form
        # types (not repeated reads of one page) are what constitute support
        by_ft = {}
        for _name, ft, ocr in members:
            by_ft[ft] = by_ft.get(ft, False) or not ocr
        return (sum(3 if trusted else 1 for trusted in by_ft.values()), len(by_ft))

    def cluster_key(members):
        sc, ndistinct = cluster_score(members)
        # deterministic: score, breadth, then the best member's rank, then text
        best = max(members, key=lambda m: ((0 if m[2] else 100) + ranks.get(m[1], 0)))
        return (sc, ndistinct, (0 if best[2] else 100) + ranks.get(best[1], 0),
                best[0])

    winner = max(clusters, key=cluster_key)
    return max(winner, key=lambda m: ((0 if m[2] else 100) + ranks.get(m[1], 0),
                                      m[0]))[0]


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
    species_vocab, purpose_vocab, name_vocab = split_vocab(species_vocab)
    # Back the batch-harvested repair vocabularies with the static learned
    # seeds (vocab.py), so a token or purpose that never appears cleanly in
    # the scored batch can still be repaired.  The batch harvest remains --
    # it adapts to values the seeds have never seen.
    purpose_vocab = set(purpose_vocab) | set(vocab.PURPOSE_SEED)
    name_vocab = set(name_vocab) | set(vocab.NAME_TOKENS)
    cands, aux = collect_candidates(pages, species_vocab, world_vocab)
    out = {}

    # applicant_name
    if "applicant_name" in cands:
        name = _consensus_name(cands["applicant_name"], name_vocab)
        if name is None:
            # every reading was damaged/empty -- fall back to plain precedence
            best_name = _best_candidate_full("applicant_name",
                                             cands["applicant_name"])
            name = _clean_name(best_name[0])
            if name and best_name[2]:  # OCR -> repair against learned tokens
                name = _canon_name(name, name_vocab)
        out["applicant_name"] = name
    # An explicit "Manual correction: applicant is X." annotation names the
    # applicant attached to the active case id, so it supersedes whatever the
    # printed field said (which may belong to a second applicant whose pages
    # were filed into the same packet -- a documented trap).
    if aux.get("applicant_corrected"):
        corrected = _clean_name(aux["applicant_corrected"])
        if corrected:
            out["applicant_name"] = corrected
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
    if aux.get("visa_corrected"):
        corrected = vocab.canon_visa(aux["visa_corrected"])
        if corrected in vocab.VISA_CLASSES:
            out["visa_class"] = corrected
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
        best_dp = _best_candidate_full("declared_purpose", cands["declared_purpose"])
        dp = best_dp[0]
        if not _is_damaged(dp):
            dp = " ".join(dp.split())
            if best_dp[2]:  # OCR source -> snap onto the learned purpose set
                dp = _canon_purpose(_trim_purpose_tail(dp), purpose_vocab)
            out["declared_purpose"] = dp
    # fee status
    if "fee_status" in cands:
        fee_val = vocab.canon_fee(_best_candidate("fee_status", cands["fee_status"]))
        if fee_val in ("paid", "waived", "unpaid", "unknown"):
            out["fee_status"] = fee_val
    # The receipt's Amount corroborates the status when the status word itself
    # was destroyed.  The charge is fixed, so a non-zero amount means the fee was
    # paid and a zero amount means it was waived.  This only fires when nothing
    # was read directly -- a legible status always wins -- and it never invents
    # "unpaid", which is a denial trigger.
    if not out.get("fee_status"):
        for raw_amt in aux.get("fee_amounts", []):
            m = re.search(r"(\d[\d,]*)(?:\.(\d{2}))?", str(raw_amt))
            if not m:
                continue
            whole = m.group(1).replace(",", "")
            cents = m.group(2) or "00"
            if not whole.isdigit():
                continue
            total = int(whole) * 100 + int(cents)
            out["fee_status"] = "waived" if total == 0 else "paid"
            aux["fee_from_amount"] = True
            break
    # A visible waiver code in the strict grammar (DIP-WAIVER / HARDSHIP-nn)
    # means the fee was waived, even when the status word was destroyed.  It
    # never overrides a directly-read status.
    if not out.get("fee_status"):
        for wc in aux.get("waiver_code", []):
            if re.search(r"DIP[\s_-]?WAIVER|HARDSHIP[\s_-]?\d{2,}",
                         str(wc), re.I):
                out["fee_status"] = "waived"
                break
    # C2a: a fee-receipt page is PRESENT but its status could not be read ->
    # treat the fee as "unknown" (both for output and adjudication) rather than
    # silently letting it fall through to an APPROVAL.  Clean cases where the fee
    # WAS read are unaffected (out["fee_status"] already set above).
    if aux.get("has_fee_page") and not out.get("fee_status"):
        out["fee_status"] = "unknown"
    if aux.get("fee_corrected"):
        corrected = vocab.canon_fee(aux["fee_corrected"])
        if corrected in vocab.FEE_STATUSES:
            out["fee_status"] = corrected
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
        none_like = ((not r) or re.fullmatch(r"(none|null|n/?a|-|\.)+", r) is not None
                     or _reads_as_none(r))
        if out["risk_flags"] == "none" and not none_like:
            # The slip listed something we could not resolve strictly.  Try the
            # OCR-tolerant matcher before giving up; if that also fails, keep
            # "none" but mark the packet uncertain so it cannot be approved.
            rescued = _rescue_flags(raw)
            if rescued != "none":
                out["risk_flags"] = rescued
            else:
                # NEVER let an unreadable flags line pass as a clean "none" --
                # that is a false-clean assertion and a false-approval vector.
                out["risk_flags"] = ""
                aux["uncertain_flags"] = True
        # UNION independent observations rather than letting the winning
        # source erase a second source's flag.  The field is scored as an
        # exact SET match and multi-flag truths are common, so when a second
        # trusted page contributes a flag the winner did not carry, both are
        # real more often than not: per-flag precision of the canonicalizer
        # is high (biohazard_red 1.00, planetary_embargo 0.94 measured), so
        # unioning adds missed members far more often than it invents one.
        # Candidates that canonicalize to nothing contribute nothing, and the
        # uncertain_flags marker above (keyed to the winning candidate's
        # readability) is left standing either way.
        union = set()
        if out["risk_flags"] and out["risk_flags"] != "none":
            union.update(out["risk_flags"].split("|"))
        for _val, _ft, _ocr in cands["risk_flags"]:
            c = vocab.canon_flags(_val)
            if c and c != "none":
                union.update(c.split("|"))
        if union:
            out["risk_flags"] = "|".join(sorted(union))
        # POSITIVE clean-flags attestation: a trusted source EXPLICITLY read
        # "none" (not merely absent/empty) and no other observation
        # contributed a flag.  This is the evidence that a packet is clean,
        # as opposed to us simply failing to find any flag.
        if out["risk_flags"] == "none" and none_like and r:
            aux["positive_clean_flags"] = True

    # The biometric slip is not the only page that PRINTS the flag: an
    # adjudicator note spells it out in its reason line ("Disqualifying risk
    # flag: planetary_embargo"), and that note is often the one page of a
    # degraded packet whose text layer survived.  When the slip itself gave us
    # nothing readable, fall back to the flag the note states.
    #
    # This is a value READ off the document, not an inference, and it is only
    # ever used to FILL an empty result -- measured on the labeled corpus, a
    # note's flag does NOT belong in the output set when the slip already
    # yielded one (a note explaining a rescinded denial adds
    # `rescinded_denial` to packets whose labeled set has only the slip's
    # flags; unioning it flipped 3 exact matches to misses for every 1 it
    # fixed).  It can never turn an unreadable flags line into a clean
    # "none" (aux["uncertain_flags"] set above is left standing either way).
    if not out.get("risk_flags") and aux.get("note_flags", "none") != "none":
        out["risk_flags"] = aux["note_flags"]

    # A Planetary Registry that explicitly reads "Registry Status: CLEAR" is an
    # independent positive clean attestation.
    for rs in aux.get("registry_status", []):
        s = re.sub(r"[^a-z]", "", str(rs).lower())
        if s and (s.startswith("clear") or fuzz.ratio(s, "clear") >= 80):
            aux["registry_clear"] = True
            break

    # A home world on the hard-embargo list IS a planetary_embargo condition:
    # every training packet from those worlds carries the flag in its labeled
    # risk set (50/50), whether or not any page spelled it out.  The
    # adjudicator already prices this for the decision; unioning it into the
    # OUTPUT field makes the extraction consistent with the condition.
    # NOTE: an explicit "Registry Status: EMBARGO" read does NOT qualify --
    # Wolf-1061c registries print EMBARGO while only 5/77 of those packets
    # carry the flag in their labeled set, so keying on the registry line
    # added 21 spurious members for every handful it recovered.
    if out.get("home_world") in ("TRAPPIST-1e", "Eris Relay"):
        have = set()
        if out.get("risk_flags") and out["risk_flags"] != "none":
            have.update(out["risk_flags"].split("|"))
        have.add("planetary_embargo")
        out["risk_flags"] = "|".join(sorted(have))

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


def _trim_purpose_tail(value):
    """Same OCR-debris trim as _trim_name_tail, for the declared purpose.

    "Declared Purpose: research a a tN" is the right value plus the noise that
    followed it on the scan line; left in place the debris drags the value below
    the fuzzy threshold that would otherwise snap it onto the learned purpose
    vocabulary.  Every purpose in the corpus is one to three ordinary words.
    """
    kept = []
    for tok in value.split():
        if not tok.isalpha() or len(tok) < 2:
            break
        kept.append(tok)
        if len(kept) == 3:
            break
    return " ".join(kept) if kept else value


def _trim_name_tail(name):
    """Drop OCR debris that ran on past the end of the name.

    A scanned intake line yields "Luix Tekvara - oasePORT" or "Miravoss Ixomora
    on nce 1": the name is right, but neighbouring cell text and stamp fragments
    were merged into it, and the exact-match scorer then rejects the whole
    value.  An applicant name is one to three capitalised word tokens, so keep
    the leading run that still looks like one (the first two tokens are accepted
    regardless of case, because OCR routinely lower-cases a real name).
    """
    kept = []
    for i, tok in enumerate(name.split()):
        letters = sum(c.isalpha() for c in tok)
        if letters < 2 or any(c.isdigit() for c in tok):
            break
        if i >= 2 and not tok[:1].isupper():
            break
        kept.append(tok)
        if len(kept) == 3:
            break
    return " ".join(kept) if kept else name
