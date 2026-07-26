"""Controlled vocabularies + fuzzy canonicalization.

Enums are small closed sets (visa, fee, risk flags) or open-but-learnable sets
(species, home_world) built from the *clean text-layer values observed across
the whole batch* plus a static seed.  OCR mangles these badly
("VFNUISIADL MNCFI"->VENUSIAN_MYCELIAL, "Walf-in6ic"->Wolf-1061c) so every
extracted enum value is fuzzy-matched back to the canonical vocabulary.
"""
import re

from rapidfuzz import fuzz, process

# ---- Fixed closed sets (general policy constants) -----------------------------
VISA_CLASSES = ["XW-1", "XW-2", "DIP-1", "MED-3", "TRANSIT-7"]
FEE_STATUSES = ["paid", "waived", "unpaid", "unknown"]

RISK_FLAGS = [
    "memory_tampering",
    "planetary_embargo",
    "active_warrant",
    "biohazard_red",
    "identity_conflict",
    "sponsor_mismatch",
    "illegible_biometrics",
    "rescinded_denial",
]
DISQUALIFYING_FLAGS = {
    "planetary_embargo",
    "biohazard_red",
    "active_warrant",
    "memory_tampering",
}
REVIEW_FLAGS = {
    "sponsor_mismatch",
    "identity_conflict",
    "illegible_biometrics",
    "rescinded_denial",
}

# Static seed for the open sets; runtime augments these from clean text layers.
SPECIES_SEED = [
    "ALPHA_DRACONIAN", "ANDROMEDAN", "AQUARIAN_MANTIS", "ARCTURIAN",
    "CENTAURI_SYNTH", "JOVIAN_GASFORM", "KAIJU_MICRO", "LUNA_SECURID",
    "ORION_GRAYS", "SIRIUS_AVIAN", "TRIANGULAN", "VENUSIAN_MYCELIAL",
]
HOME_WORLD_SEED = [
    "Barnard-c", "Eris Relay", "Europa Station", "Gliese-581g", "Kepler-186f",
    "Luyten-b", "Mars Dome-7", "Proxima-b", "Sirius Outpost", "TRAPPIST-1e",
    "Titan Freeport", "Wolf-1061c", "Zeta Reticuli",
]

# Revoked sponsors: field-manual public list {SPN-0007, SPN-0139, SPN-4040}
# plus additional revoked ids learned from labeled examples.  General policy
# table, NOT a per-case lookup.
REVOKED_SPONSORS = {
    "SPN-0007", "SPN-0139", "SPN-4040", "SPN-7331", "SPN-2718", "SPN-9090",
}
# Embargoed home world (soft signal for non-DIP-1).
EMBARGO_WORLDS = {"Wolf-1061c"}


def _clean_enum(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", (text or "").strip().upper()).strip("_")


def canon_species(value, vocab):
    if not value:
        return ""
    cleaned = _clean_enum(value)
    if not cleaned:
        return ""
    # sorted() the learned vocab so choice order (and thus tie-breaking in
    # extractOne) is independent of set/frozenset iteration order / PYTHONHASHSEED.
    choices = list(dict.fromkeys(sorted(vocab) + SPECIES_SEED))
    keys = [_clean_enum(c) for c in choices]
    best = process.extractOne(cleaned, keys, scorer=fuzz.ratio)
    if best and best[1] >= 72:
        return choices[best[2]]
    # token-based fallback for badly split OCR
    best2 = process.extractOne(cleaned, keys, scorer=fuzz.token_sort_ratio)
    if best2 and best2[1] >= 78:
        return choices[best2[2]]
    return cleaned


def canon_home_world(value, vocab):
    if not value:
        return ""
    v = " ".join(value.strip().split())
    choices = list(dict.fromkeys(sorted(vocab) + HOME_WORLD_SEED))
    best = process.extractOne(v, choices, scorer=fuzz.ratio)
    if best and best[1] >= 78:
        return best[0]
    best2 = process.extractOne(v, choices, scorer=fuzz.WRatio)
    if best2 and best2[1] >= 85:
        return best2[0]
    return v


VISA_SUBSTR_RE = re.compile(r"[A-Za-z]{2,7}\s?[-_]?\s?\d")


def canon_visa(value):
    if not value:
        return ""
    v = _clean_enum(value).replace("_", "-")
    keys = VISA_CLASSES
    best = process.extractOne(v, keys, scorer=fuzz.ratio)
    if best and best[1] >= 70:
        return best[0]
    # The field extractor sometimes concatenates neighbouring cell text into the
    # visa value (e.g. "DIP-1 PASSPORT IMAGE" -> "DIP-1-PASSPORT-IMAGE"), which
    # then fails a whole-string match and drops a real visa class (losing e.g.
    # the DIP-1 sponsor exemption -> false denial).  Recover by scanning for the
    # best visa-class token *within* the string.
    best_tok, best_sc = None, 0
    for m in VISA_SUBSTR_RE.finditer(value):
        tok = _clean_enum(m.group(0)).replace("_", "-")
        for k in keys:
            sc = fuzz.ratio(tok, k)
            if sc > best_sc:
                best_sc, best_tok = sc, k
    if best_tok and best_sc >= 80:
        return best_tok
    return v


def canon_fee(value):
    if not value:
        return ""
    v = re.sub(r"[^a-z]", "", (value or "").lower())
    if not v:
        return ""
    best = process.extractOne(v, FEE_STATUSES, scorer=fuzz.ratio)
    if best and best[1] >= 70:
        return best[0]
    return ""


# Closed-vocabulary rescue parameters.  Named constants rather than inline
# literals because they are swept against the labeled corpus (tools/sweep.py);
# see the rationale in canon_flag_token below.
FLAG_RESCUE_MIN = 62      # accept a best match at or above this score
FLAG_RESCUE_MARGIN = 12   # ...only if it beats the runner-up by this much
FLAG_RESCUE_MINLEN = 9    # ...and the token is long enough to be a flag name


def canon_flag_token(tok):
    t = _clean_enum(tok).lower()
    if not t or t in {"none", "null", "na", "n_a"}:
        return None
    best = process.extractOne(t, RISK_FLAGS, scorer=fuzz.ratio)
    if best and best[1] >= 78:
        return best[0]
    best2 = process.extractOne(t, RISK_FLAGS, scorer=fuzz.token_sort_ratio)
    if best2 and best2[1] >= 82:
        return best2[0]
    # Closed-vocabulary rescue.  The eight flag names are mutually distant --
    # the most similar PAIR scores only 42.4 -- so a read scoring well above
    # that against its best match cannot be closer to a different flag.  A
    # degraded scan yields things like "Bohazond_yed" (72 vs biohazard_red)
    # that the thresholds above reject even though they are unambiguous.
    # Accepting them well below the usual thresholds still keeps a wide margin
    # over the confusability ceiling, so this can never substitute one flag for
    # another.  A real example from the corpus: a B-13 slip whose risk panel
    # OCR'd as "Coserved Yaga: | ing':'e_fiomet'se" scores 57 against
    # illegible_biometrics and 37 against the next-best flag -- mangled past
    # recognition, but not remotely ambiguous.
    #
    # The residual risk is matching OCR noise that is not a flag at all, which
    # would invent a disqualifier and wrongly DENY.  Two guards: the token must
    # be long enough to be a flag name at all, and the margin over the
    # runner-up must be decisive.  Note this can only ever add denial signals,
    # so it cannot cause a catastrophic false approval.
    if best and len(t) >= FLAG_RESCUE_MINLEN and best[1] >= FLAG_RESCUE_MIN:
        ranked = process.extract(t, RISK_FLAGS, scorer=fuzz.ratio, limit=2)
        if (len(ranked) < 2
                or (ranked[0][1] - ranked[1][1]) >= FLAG_RESCUE_MARGIN):
            return best[0]
    return None


def canon_flags(raw):
    """raw is a string possibly containing several flags joined by | , ; or
    whitespace.  Returns a sorted pipe-joined canonical string or 'none'."""
    if raw is None:
        return "none"
    s = str(raw).strip()
    if not s or s.lower() in {"none", "null", "n/a", "na", "-"}:
        return "none"
    tokens = re.split(r"[|,;/]+|\s{2,}", s)
    if len(tokens) == 1:
        tokens = re.split(r"\s+", s)
    out = set()
    # try single-token canonicalization, then reassemble multiword flags
    joined = "_".join(re.split(r"\s+", s.strip()))
    single = canon_flag_token(joined)
    if single:
        out.add(single)
    for tok in tokens:
        c = canon_flag_token(tok)
        if c:
            out.add(c)
    # sliding window over words to catch multiword flag names in OCR noise
    words = re.split(r"\s+", s.strip())
    for i in range(len(words)):
        for j in (2, 3):
            if i + j <= len(words):
                c = canon_flag_token("_".join(words[i:i + j]))
                if c:
                    out.add(c)
    if not out:
        return "none"
    return "|".join(sorted(out))


SPONSOR_RE = re.compile(r"\bSPN[-\s]?0*?(\d{2,4})\b", re.I)


def canon_sponsor(value):
    if not value:
        return ""
    m = SPONSOR_RE.search(value)
    if not m:
        # also handle 'SPN' misread with letter substitutions like 5PN/5FN
        m2 = re.search(r"\b[5S][PF]N[-\s]?(\d{2,4})\b", value, re.I)
        if not m2:
            return ""
        digits = m2.group(1)
    else:
        digits = m.group(1)
    digits = digits[-4:].zfill(4)
    return f"SPN-{digits}"


DATE_RE = re.compile(r"(20\d{2})\D?(\d{2})\D?(\d{2})")


def canon_date(value):
    if not value:
        return ""
    if re.search(r"unreadable|illegible|missing|lost", value, re.I):
        return ""
    m = DATE_RE.search(value)
    if not m:
        return ""
    y, mo, d = m.groups()
    try:
        mi = int(mo)
        di = int(d)
        if not (1 <= mi <= 12 and 1 <= di <= 31):
            return ""
    except ValueError:
        return ""
    return f"{y}-{mo}-{d}"
