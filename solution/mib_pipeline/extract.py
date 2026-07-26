"""Anchored field extraction over a unified token stream.

Both channels (visible text-layer spans and OCR words) are converted to
positioned tokens, grouped into lines, and parsed with fuzzy label anchors
("Applicant Name", "Visa Class", ...). Values snap to the closed domain
vocabularies with an OCR-confusion-aware distance and a margin requirement
over the runner-up; below-threshold values are kept raw with low confidence.
"""

import re
from dataclasses import dataclass, field as dfield

from rapidfuzz import fuzz

from . import vocab


@dataclass
class Token:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float          # 0-100


@dataclass
class FieldValue:
    value: str
    conf: float          # 0-1
    source: str          # channel: "text" | "ocr"
    page_index: int
    page_type: str = ""
    anchored: bool = True


# ---------------------------------------------------------------- lines

def group_lines(tokens):
    """Group tokens into reading-order lines by vertical overlap."""
    tokens = sorted(tokens, key=lambda t: (t.y0, t.x0))
    lines = []
    for tok in tokens:
        placed = False
        for line in lines:
            ref = line[-1]
            mid = (tok.y0 + tok.y1) / 2
            if ref.y0 - 2 <= mid <= ref.y1 + 2:
                line.append(tok)
                placed = True
                break
        if not placed:
            lines.append([tok])
    for line in lines:
        line.sort(key=lambda t: t.x0)
    lines.sort(key=lambda l: min(t.y0 for t in l))
    return lines


# ------------------------------------------------------------ anchors

ANCHORS = {
    "case_id": ["case id", "case number", "case no"],
    "applicant_name": ["applicant name", "name of applicant", "full name",
                       "applicant"],
    "species_code": ["species code", "species"],
    "home_world": ["home world", "homeworld", "world of origin", "origin world"],
    "visa_class": ["visa class", "visa type", "visa category", "visa"],
    "sponsor_id": ["sponsor id", "sponsor number", "sponsor ref", "sponsor"],
    "arrival_date": ["arrival date", "date of arrival", "arrival"],
    "declared_purpose": ["declared purpose", "purpose of visit", "purpose"],
    "risk_flags": ["risk flags", "risk flag", "flags", "risk indicators"],
    "fee_status": ["fee status", "fee", "payment status"],
    "receipt_date": ["receipt date", "received", "packet received",
                     "date received", "intake date", "processed", "inspection date"],
}

_WORD_RE = re.compile(r"[A-Za-z0-9|_-]+")


def _norm(text: str) -> str:
    return " ".join(_WORD_RE.findall(text)).lower()


def find_anchored_values(lines, min_score: float = 82.0):
    """Yield (field, value_tokens, anchor_score) for label anchors in lines."""
    results = []
    for li, line in enumerate(lines):
        joined = " ".join(t.text for t in line)
        norm_line = _norm(joined)
        if not norm_line:
            continue
        for field_name, phrases in ANCHORS.items():
            best = None
            for phrase in phrases:
                nwords = len(phrase.split())
                # try anchor at each token offset, spanning nwords tokens
                for start in range(len(line)):
                    for span_len in (nwords, nwords + 1):
                        chunk = line[start:start + span_len]
                        if not chunk:
                            continue
                        chunk_text = _norm(" ".join(t.text for t in chunk))
                        score = fuzz.ratio(chunk_text, phrase)
                        if score >= min_score and (best is None or score > best[0] or
                                                   (score == best[0] and len(phrase) > best[3])):
                            best = (score, start, start + span_len, len(phrase), phrase)
            if best:
                score, start, end, _, phrase = best
                value_tokens = line[end:]
                # value may continue on the next line when empty after anchor
                if not value_tokens and li + 1 < len(lines):
                    nxt = lines[li + 1]
                    if nxt and abs(nxt[0].y0 - line[0].y1) < 2.5 * (line[0].y1 - line[0].y0):
                        value_tokens = nxt
                results.append((field_name, value_tokens, score, li))
    return results


# --------------------------------------------------------- normalizers

_CONF_ALPHA = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "6": "G",
                             "2": "Z"})
_CONF_DIGIT = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "i": "1",
                             "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2",
                             "G": "6", "D": "0", "Q": "0", "T": "7"})


def snap(raw: str, choices, min_score: float = 78.0, margin: float = 4.0):
    """Snap raw text to the closest vocabulary entry.

    Returns (value, score01) or (None, 0). Requires a margin over the
    runner-up unless the top score is near-perfect, so plausible-but-wrong
    corrections fall through instead of corrupting good OCR.
    """
    cleaned = " ".join(_WORD_RE.findall(raw))
    if not cleaned:
        return None, 0.0
    scored = []
    for choice in choices:
        a = cleaned.lower()
        b = choice.lower()
        score = max(fuzz.ratio(a, b),
                    fuzz.ratio(cleaned.translate(_CONF_ALPHA).lower(), b))
        scored.append((score, choice))
    scored.sort(reverse=True)
    top_score, top = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if top_score >= min_score and (top_score - runner >= margin or top_score >= 97):
        return top, top_score / 100.0
    return None, 0.0


_SPN_STRICT_RE = re.compile(
    r"[S5$][PF₽][NM]\s*[-–—:# ]{0,2}\s*([0-9OolISBZzGDQT]{4})\b", re.IGNORECASE)
# Loose variant for text already known to be a sponsor-field value.
_SPN_LOOSE_RE = re.compile(
    r"(?:[S5$]?[PF₽]?[NM]?\s*[-–—:# ]{0,2})?\b([0-9OolISBZzGDQT]{4})\b")


def parse_sponsor(text: str, anchored: bool = False):
    m = _SPN_STRICT_RE.search(text)
    if not m and anchored:
        m = _SPN_LOOSE_RE.search(text)
    if not m:
        return None
    digits = m.group(1).translate(_CONF_DIGIT)
    if re.fullmatch(r"\d{4}", digits):
        return f"SPN-{digits}"
    return None


_CASE_RE = re.compile(r"M[I1l]B\s*[-–—:# ]{0,2}\s*([0-9OolISBZzGDQT]{6})",
                      re.IGNORECASE)


def parse_case_id(text: str):
    m = _CASE_RE.search(text)
    if not m:
        return None
    digits = m.group(1).translate(_CONF_DIGIT)
    if re.fullmatch(r"\d{6}", digits):
        return f"MIB-{digits}"
    return None


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}

_DATE_PATTERNS = [
    re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b"),                 # 2026-04-17
    re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b"),                 # 17/04/2026
    re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b"),          # Apr 17, 2026
    re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"),          # 17 Apr 2026
]


def parse_date(text: str):
    """Parse a date string to ISO YYYY-MM-DD; None on failure."""
    cleaned = text.translate(_CONF_DIGIT) if sum(c.isdigit() for c in text) >= 2 else text
    for i, pattern in enumerate(_DATE_PATTERNS):
        m = pattern.search(cleaned) or pattern.search(text)
        if not m:
            continue
        try:
            if i == 0:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif i == 1:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if mo > 12 and d <= 12:
                    d, mo = mo, d
            elif i == 2:
                mo = _MONTHS.get(m.group(1)[:3].lower())
                d, y = int(m.group(2)), int(m.group(3))
            else:
                d, y = int(m.group(1)), int(m.group(3))
                mo = _MONTHS.get(m.group(2)[:3].lower())
            if not mo or not (1 <= mo <= 12) or not (1 <= d <= 31) or not (2000 <= y <= 2100):
                continue
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, TypeError):
            continue
    return None


def parse_flags(text: str):
    """Parse a risk-flag list; returns (set, unparsed_leftovers)."""
    norm = _norm(text)
    if not norm or norm in ("none", "n a", "na", "nil", "no flags", "none reported"):
        return set(), []
    parts = re.split(r"[|,;/]+|\s{2,}", text)
    flags, leftovers = set(), []
    for part in parts:
        cleaned = _norm(part).replace(" ", "_")
        if not cleaned or cleaned in ("none", "na", "n_a"):
            continue
        snapped, score = snap(cleaned.replace("_", " "),
                              [f.replace("_", " ") for f in vocab.RISK_FLAGS],
                              min_score=80, margin=3)
        if snapped:
            flags.add(snapped.replace(" ", "_"))
        else:
            leftovers.append(cleaned)
    return flags, leftovers


def parse_field(field_name: str, raw: str):
    """Normalize + snap a raw anchored value. Returns (value|None, conf01)."""
    raw = raw.strip().strip(":;.,")
    if not raw:
        return None, 0.0
    if field_name == "species_code":
        cleaned = re.sub(r"[^A-Za-z0-9_ ]", "", raw).strip()
        if not cleaned:
            return None, 0.0
        val, score = snap(cleaned.replace("_", " "),
                          [s.replace("_", " ") for s in vocab.SPECIES])
        return (val.replace(" ", "_"), score) if val else (None, 0.0)
    if field_name == "home_world":
        return snap(raw, vocab.HOME_WORLDS)
    if field_name == "visa_class":
        cleaned = raw.upper().translate(str.maketrans({"1": "1"}))
        val, score = snap(cleaned, vocab.VISA_CLASSES, min_score=70, margin=6)
        return val, score
    if field_name == "declared_purpose":
        return snap(raw.lower(), vocab.PURPOSES)
    if field_name == "fee_status":
        return snap(raw.lower(), vocab.FEE_STATUSES, min_score=70, margin=8)
    if field_name == "sponsor_id":
        spn = parse_sponsor(raw, anchored=True)
        return (spn, 0.9) if spn else (None, 0.0)
    if field_name in ("arrival_date", "receipt_date"):
        dt = parse_date(raw)
        return (dt, 0.9) if dt else (None, 0.0)
    if field_name == "case_id":
        cid = parse_case_id(raw)
        return (cid, 0.95) if cid else (None, 0.0)
    if field_name == "applicant_name":
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]+", raw)][:2]
        if len(words) >= 2:
            return " ".join(w.capitalize() for w in words), 0.75
        if words:
            return words[0].capitalize(), 0.4
        return None, 0.0
    return raw, 0.5


def extract_fields(tokens, page_index: int, source: str, channel_conf: float = 1.0):
    """Run anchored extraction over one page's tokens.

    Returns {field: [FieldValue, ...]} candidates (may be several per field).
    """
    lines = group_lines(tokens)
    out = {}
    for field_name, value_tokens, anchor_score, _ in find_anchored_values(lines):
        raw = " ".join(t.text for t in value_tokens)
        # snapping value text: only use tokens up to the next anchor-ish gap
        value, conf = parse_field(field_name, raw)
        if field_name == "risk_flags":
            flags, leftovers = parse_flags(raw)
            value = "|".join(sorted(flags)) if flags else ("none" if not leftovers else None)
            conf = 0.85 if value is not None else 0.0
        if value is None:
            continue
        tok_conf = (sum(t.conf for t in value_tokens) / len(value_tokens) / 100.0
                    if value_tokens else 0.5)
        overall = conf * (0.5 + 0.5 * tok_conf) * channel_conf * (anchor_score / 100.0)
        out.setdefault(field_name, []).append(
            FieldValue(value=value, conf=overall, source=source,
                       page_index=page_index))
    # Pattern fallbacks anywhere on the page (case ids, sponsor ids, dates).
    page_text = " ".join(t.text for t in tokens)
    if "case_id" not in out:
        cid = parse_case_id(page_text)
        if cid:
            out["case_id"] = [FieldValue(cid, 0.6 * channel_conf, source,
                                         page_index, anchored=False)]
    if "sponsor_id" not in out:
        spn = parse_sponsor(page_text)
        if spn:
            out["sponsor_id"] = [FieldValue(spn, 0.5 * channel_conf, source,
                                            page_index, anchored=False)]
    return out


# ------------------------------------------------- specialized page parsers

_LETTER_RE = re.compile(
    r"Sponsor\s+(?P<spn>[S5$][PF₽][NM][-–—\s:#]{0,2}[0-9OolISBZzGDQT]{4})\s+"
    r"attests\s+that\s+(?P<name>[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)\s+is\s+expected",
    re.IGNORECASE)
_LETTER_CLASS_RE = re.compile(
    r"class\s+(?P<visa>[A-Z]{2,8}\s*[-–—]?\s*\d)\s+compliance", re.IGNORECASE)
_LETTER_FOR_RE = re.compile(
    r"expected\s+on\s+Earth\s+for\s+(?P<purpose>[a-z][a-z ]{3,30}?)(?:\s+work|\s+duties|[.,]|$)",
    re.IGNORECASE)


def parse_sponsor_letter(text: str) -> dict:
    """Parse 'Sponsor SPN-#### attests that <Name> is expected...' letters."""
    out = {}
    m = _LETTER_RE.search(text)
    if m:
        spn = parse_sponsor(m.group("spn"), anchored=True)
        if spn:
            out["sponsor_id"] = spn
        out["letter_name"] = " ".join(
            w.capitalize() for w in m.group("name").split()[:2])
    m = _LETTER_CLASS_RE.search(text)
    if m:
        from . import vocab
        visa, score = snap(m.group("visa").upper(), vocab.VISA_CLASSES,
                           min_score=70, margin=6)
        if visa:
            out["visa_class"] = visa
    m = _LETTER_FOR_RE.search(text)
    if m:
        from . import vocab
        purpose, score = snap(m.group("purpose").lower().strip(), vocab.PURPOSES,
                              min_score=75, margin=4)
        if purpose:
            out["declared_purpose"] = purpose
    return out


_FINDING_RE = re.compile(
    r"Finding\s*[:\-]\s*(?P<verdict>APPROV\w+|DEN[IY]\w+|NEEDS[\s_]*REVIEW)",
    re.IGNORECASE)
_REASON_RE = re.compile(r"Reason\s*[:\-]\s*(?P<reason>[^\n]{0,160})", re.IGNORECASE)


def parse_adjudicator_note(text: str) -> dict:
    """Parse 'Finding: DENIED. Reason: ...' adjudicator notes."""
    out = {}
    m = _FINDING_RE.search(text)
    if m:
        verdict = m.group("verdict").upper()
        if verdict.startswith("APPROV"):
            out["note_finding"] = "APPROVED"
        elif verdict.startswith("DEN"):
            out["note_finding"] = "DENIED"
        else:
            out["note_finding"] = "NEEDS_REVIEW"
    m = _REASON_RE.search(text)
    if m:
        out["note_reason"] = m.group("reason").strip()
        from . import vocab
        found = set()
        for token in re.findall(r"[a-z][a-z_]{4,}", out["note_reason"].lower()):
            snapped, _ = snap(token.replace("_", " "),
                              [f.replace("_", " ") for f in vocab.RISK_FLAGS],
                              min_score=85, margin=5)
            if snapped:
                found.add(snapped.replace(" ", "_"))
        if found:
            out["note_flags"] = sorted(found)
    if re.search(r"rescind\w+|vacat\w+|withdraw\w+|revers\w+", text, re.IGNORECASE):
        out["note_rescinded"] = True
    return out


_REGISTRY_STATUS_RE = re.compile(
    r"Registry\s+Status\W{0,8}(?P<status>[A-Z][A-Z ]{2,30})", re.IGNORECASE)
_BIO_CONF_RE = re.compile(
    r"Biometric\s+confidence\W{0,6}(?P<pct>\d{1,3})\s*%", re.IGNORECASE)


def parse_registry_status(text: str):
    m = _REGISTRY_STATUS_RE.search(text)
    return m.group("status").strip().upper() if m else None


def parse_bio_confidence(text: str):
    m = _BIO_CONF_RE.search(text)
    if m:
        val = int(m.group("pct"))
        return val if 0 <= val <= 100 else None
    return None
