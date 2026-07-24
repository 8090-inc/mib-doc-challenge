"""PDF -> per-page evidence.

Each page yields:
  * form_type      (I8090 / B13 / FEE / SPONSOR / REGISTRY / NOTE / UNKNOWN)
  * text_spans     list of trusted {bbox,text} from the text layer
  * ocr_lines      list of trusted OCR text lines (image pages only)
Only VISIBLE, on-crop, normal-color spans survive (see trust.py).
"""
import os
os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # keep tesseract single-threaded per worker

import io
import re

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image

from trust import color_to_rgb, span_is_trusted, scrub_ocr_line

FORM_TITLES = [
    ("I8090", "FORM I-8090"),
    ("B13", "FORM B-13"),
    ("FEE", "MIB Fee Receipt"),
    ("SPONSOR", "Sponsor Attestation"),
    ("REGISTRY", "Planetary Registry"),
    ("NOTE", "Manual Adjudicator Note"),
]

HEADER_FOOTER_RE = re.compile(
    r"(Packet MIB-\d{6}|MIB Eyes Only|Synthetic hiring challenge|"
    r"PASSPORT IMAGE|REGISTRY IMAGE|SCAN IMAGE|Primary intake record)",
    re.I,
)


# Distinctive field labels / phrases per form type, used to classify a degraded
# scan whose TITLE line was mangled beyond recognition.  Getting form_type right
# is upstream of everything else -- if we do not know a page is a B-13 we never
# look for its "Observed flags" line.  Only cues that are long enough to be
# unambiguous are listed (short ones like "Case ID" appear on every form).
_FORM_CUES = {
    "B13": ("biometric scan slip", "observed flags", "species match",
            "biometric confidence"),
    "I8090": ("work authorization intake", "declared purpose",
              "primary intake record", "extraterrestrial work"),
    "FEE": ("mib fee receipt", "fee status", "waiver code"),
    "REGISTRY": ("planetary registry extract", "registry name",
                 "registry status"),
    "SPONSOR": ("sponsor attestation letter", "attests that",
                "acknowledges responsibility"),
    "NOTE": ("manual adjudicator note", "adjudicator"),
}
# fixed order -> deterministic tie-break
_FORM_CUE_ITEMS = tuple(
    (ft, tuple((c, re.sub(r"[^a-z]", "", c)) for c in cues))
    for ft, cues in sorted(_FORM_CUES.items())
)


def _cue_form_type(blob):
    """Classify a page by fuzzy-matching distinctive field labels."""
    from rapidfuzz import fuzz as _fz
    lines = [re.sub(r"[^a-z]", "", ln.lower()) for ln in blob.splitlines()]
    lines = [ln for ln in lines if len(ln) >= 8]
    if not lines:
        return None
    best_ft, best_hits = None, 0
    for ft, cues in _FORM_CUE_ITEMS:
        hits = 0
        for _raw, key in cues:
            if any(_fz.partial_ratio(key, ln) >= 86 for ln in lines):
                hits += 1
        if hits > best_hits:
            best_hits, best_ft = hits, ft
    return best_ft if best_hits >= 1 else None


def _detect_form_type(text_join, ocr_join=""):
    blob = text_join + "\n" + ocr_join
    for ftype, needle in FORM_TITLES:
        if needle.lower() in blob.lower():
            return ftype
    low = blob.lower()
    # keyword / substring recovery from (possibly mangled) OCR
    if "8090" in low or "authorization intake" in low or "intake record" in low:
        return "I8090"
    if "biometric" in low or "scan slip" in low or "observed flag" in low or "species match" in low:
        return "B13"
    if "fee receipt" in low or "waiver code" in low or ("fee status" in low):
        return "FEE"
    if "attestation" in low or "attests" in low or "sponsor" in low and "attest" in low:
        return "SPONSOR"
    if "registry" in low:
        return "REGISTRY"
    if "adjudicator" in low or "finding:" in low or "adjudicater" in low:
        return "NOTE"
    # fuzzy title match on the first lines
    from rapidfuzz import fuzz as _fz
    head = "\n".join(blob.strip().splitlines()[:4])
    best, bscore = "UNKNOWN", 0
    for ftype, needle in FORM_TITLES:
        sc = _fz.partial_ratio(needle.lower(), head.lower())
        if sc > bscore:
            bscore, best = sc, ftype
    if bscore >= 78:
        return best
    # last resort: the title is gone, but the field labels still identify the form
    cued = _cue_form_type(blob)
    if cued:
        return cued
    return "UNKNOWN"


def _trusted_text_spans(page, w, h):
    spans = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for s in line["spans"]:
                text = s.get("text", "")
                if not text.strip():
                    continue
                rgb = color_to_rgb(s.get("color", 0))
                bbox = s["bbox"]
                if not span_is_trusted(text, rgb, bbox, w, h):
                    continue
                spans.append({"bbox": tuple(bbox), "text": text})
    return spans


def _content_len(spans):
    total = 0
    for s in spans:
        t = s["text"].strip()
        if HEADER_FOOTER_RE.search(t):
            continue
        total += len(t)
    return total


# ---- OCR ---------------------------------------------------------------------

def _rescale(gray):
    """Bring an embedded scan into tesseract's comfortable glyph-size range."""
    h0 = gray.shape[0]
    if h0 < 2200:
        return cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    if h0 > 3600:
        f = 3300.0 / h0
        return cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    return gray


def _flatten(gray):
    """Divide out the uneven illumination so faint body text pops."""
    bg = cv2.morphologyEx(
        gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    )
    return cv2.divide(gray, bg, scale=255)


def _preprocess_plain(gray):
    """Illumination-flattened Otsu binarisation, with NO line/blob surgery.

    The aggressive variant below (`_preprocess`) strips ruled lines and stamp
    blobs, but on the faintest scans its morphology and connected-component
    filtering also eat the thin strokes of the body text, turning a legible
    "biohazard_red" into "otc.cenrd_ped".  Keeping a plain binarisation in the
    variant set recovers those pages.
    """
    norm = _flatten(_rescale(gray))
    _, out = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def _preprocess_norm(gray):
    """Illumination-flattened GRAYSCALE (tesseract does its own thresholding).
    Best on scans where any hard threshold breaks strokes apart."""
    return _flatten(_rescale(gray))


def _preprocess(gray):
    """Return a cleaned binary (black text on white) for a degraded scan.

    The body text is very faint (values ~180-223) and unevenly lit, so a global
    threshold fails.  Instead we flatten illumination by dividing the image by a
    morphological background estimate (this makes faint text pop), Otsu-threshold
    the result, then remove the ruled-line / border-tick background via
    morphology and thicken broken strokes.
    """
    gray = _rescale(gray)
    norm = _flatten(gray)
    _, mask = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    horiz = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1))
    )
    vert = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 34))
    )
    txt = cv2.subtract(mask, cv2.bitwise_or(horiz, vert))
    # drop large blobs (photos / stamps) and long line remnants (vectorized)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(txt, 8)
    if n > 1:
        area = stats[:, cv2.CC_STAT_AREA]
        cw = stats[:, cv2.CC_STAT_WIDTH]
        ch = stats[:, cv2.CC_STAT_HEIGHT]
        keep_lbl = (
            (area >= 8)
            & ~((cw < 4) & (ch > 40))
            & ~((ch < 4) & (cw > 55))
            & ~((area > 6000) & (cw > 120) & (ch > 120))  # solid photo/stamp blob
        )
        keep_lbl[0] = False
        txt = np.where(keep_lbl[lab], np.uint8(255), np.uint8(0))
    txt = cv2.morphologyEx(txt, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return 255 - txt


def _text_axis(clean):
    """(horizontal_runs, vertical_runs) on a cleaned binary (white bg).

    Printed text lines close up into long HORIZONTAL runs when the page is
    upright and into long VERTICAL runs when the scan is 90/270-rotated, so the
    two counts tell us which axis the glyph baselines run along.  Used only to
    order the rotation retries, never to accept/reject a value.
    """
    txt = 255 - clean
    out = []
    for horiz in (True, False):
        k = (25, 1) if horiz else (1, 25)
        m = cv2.morphologyEx(txt, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_RECT, k))
        n, _lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        if n <= 1:
            out.append(0)
            continue
        w = stats[1:, cv2.CC_STAT_WIDTH]
        h = stats[1:, cv2.CC_STAT_HEIGHT]
        if horiz:
            out.append(int(np.sum((w > 90) & (h < 45))))
        else:
            out.append(int(np.sum((h > 90) & (w < 45))))
    return out[0], out[1]


def _tess(img, psm):
    try:
        return pytesseract.image_to_string(img, config="--psm %d" % psm)
    except Exception:
        return ""


# Preprocessing variants, cheapest-and-usually-best first.  We stop as soon as a
# variant reads enough form labels to be trusted, so a clean scan still costs a
# single OCR pass and only the genuinely hard pages pay for the retries.
_VARIANT_FUNCS = (_preprocess_plain, _preprocess, _preprocess_norm)
_GOOD_ENOUGH = 4


def _ocr_variants(arr):
    """Best (text, score) over the preprocessing variants, plus the binary of
    the first variant (reused for orientation detection)."""
    best_text, best_score, best_clean, first_clean = "", 0, None, None
    for fn in _VARIANT_FUNCS:
        clean = fn(arr)
        if first_clean is None:
            first_clean = clean
        txt = _tess(clean, 6)
        score = _ocr_quality(txt)
        if score > best_score or best_clean is None:
            best_text, best_score, best_clean = txt, score, clean
        if best_score >= _GOOD_ENOUGH:
            break
    # single-column psm 4 fallback on the winning variant only
    if best_score < _GOOD_ENOUGH:
        txt = _tess(best_clean, 4)
        if _ocr_quality(txt) > best_score:
            best_text, best_score = txt, _ocr_quality(txt)
    return best_text, best_score, first_clean


def _ocr_image(pil_gray, page_rotation=0):
    """OCR a degraded page scan.

    Two failure modes are handled here.  (1) A sizeable minority of the scans
    are stored 90/180/270 rotated (the PDF /Rotate is 0, so the rotation is
    baked into the raster) and tesseract returns pure noise on those.  (2) No
    single binarisation suits every scan, so several are tried and the one that
    yields the most recognisable form labels wins.  Orientation is probed with
    the cheap variant only; the full variant set is then spent on the winning
    orientation.
    """
    arr = np.array(pil_gray)
    best_text, best_score, first_clean = _ocr_variants(arr)
    if best_score == 0:
        h_runs, v_runs = _text_axis(first_clean)
        order = (1, 3, 2) if v_runs > h_runs else (2, 1, 3)
        best_k = None
        for k in order:
            rot = np.ascontiguousarray(np.rot90(arr, k))
            txt = _tess(_preprocess_plain(rot), 6)
            score = _ocr_quality(txt)
            if score > best_score:
                best_text, best_score, best_k = txt, score, k
            if best_score >= 3:
                break
        if best_k is not None and best_score < _GOOD_ENOUGH:
            rot = np.ascontiguousarray(np.rot90(arr, best_k))
            txt, score, _ = _ocr_variants(rot)
            if score > best_score:
                best_text, best_score = txt, score
    return best_text


_LABEL_HINT_RE = re.compile(
    r"case id|applicant|species|home world|visa|sponsor|arrival|purpose|"
    r"fee status|waiver|amount|observed|registry|biometric|finding|status",
    re.I,
)


def _ocr_quality(txt):
    if not txt:
        return 0
    return len(_LABEL_HINT_RE.findall(txt))


def _page_scan_gray(doc, page):
    """Return the degraded page-scan as a grayscale PIL image.

    Prefer the largest embedded raster (the scanned form itself, at native
    resolution) over rendering the page, which resamples and further softens the
    already-faint text.  Falls back to a page render if no suitable image.
    """
    best = None
    best_area = 0
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            base = doc.extract_image(xref)
            im = Image.open(io.BytesIO(base["image"]))
        except Exception:
            continue
        area = im.size[0] * im.size[1]
        if area > best_area:
            best_area = area
            best = im
    page_area = page.rect.width * page.rect.height
    if best is not None and best_area >= 0.15 * page_area * 4:  # covers most of page
        return best.convert("L")
    # fallback render
    pix = page.get_pixmap(dpi=250)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")


def ingest_pdf(path, do_ocr=True):
    """Return (case_id, [page_evidence,...])."""
    doc = fitz.open(path)
    pages = []
    case_id = _case_id_from_name(path)
    try:
        w = doc[0].rect.width
        h = doc[0].rect.height
    except Exception:
        w = h = 792.0
    for page in doc:
        pw, ph = page.rect.width, page.rect.height
        spans = _trusted_text_spans(page, pw, ph)
        text_join = "\n".join(s["text"] for s in spans)
        # recover case id from header
        m = re.search(r"MIB-(\d{6})", text_join)
        if m and not case_id:
            case_id = "MIB-" + m.group(1)
        ocr_lines = []
        is_image_page = bool(page.get_images())
        needs_ocr = do_ocr and is_image_page and _content_len(spans) < 25
        if needs_ocr:
            try:
                gray = _page_scan_gray(doc, page)
                raw = _ocr_image(gray)
                for ln in raw.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    ln = scrub_ocr_line(ln)
                    if ln:
                        ocr_lines.append(ln)
            except Exception:
                ocr_lines = []
        ocr_join = "\n".join(ocr_lines)
        ftype = _detect_form_type(text_join, ocr_join)
        alpha = sum(c.isalpha() for c in ocr_join)
        illegible = needs_ocr and _ocr_quality(ocr_join) == 0 and alpha < 60
        pages.append({
            "form_type": ftype,
            "text_spans": spans,
            "ocr_lines": ocr_lines,
            "from_ocr": needs_ocr,
            "illegible": illegible,
        })
    doc.close()
    if not case_id:
        case_id = _case_id_from_name(path) or "MIB-000000"
    return case_id, pages


def _case_id_from_name(path):
    m = re.search(r"MIB-(\d{6})", str(path))
    return "MIB-" + m.group(1) if m else ""


_PURPOSE_RE = re.compile(r"[A-Za-z][A-Za-z \-]{2,31}")
_NAME_RE = re.compile(r"[A-Z][A-Za-z'\-]{2,15}(?: [A-Z][A-Za-z'\-]{2,15}){1,2}")


def quick_text_layer_values(path):
    """Fast pass (no OCR): harvest clean enum values from text layers to build
    the batch vocabulary.

    Returns (species_set, world_set).  declared_purpose values and applicant
    name tokens ride along inside the species set behind the private prefixes
    from extract.py (solution.py owns this call's 2-tuple contract and is not
    ours to change); extract.split_vocab separates them again.
    """
    species, worlds = set(), set()
    try:
        doc = fitz.open(path)
    except Exception:
        return species, worlds
    # local imports to avoid a cycle at module load
    from extract import (VOCAB_NAME_PREFIX, VOCAB_PURPOSE_PREFIX, _is_damaged,
                         parse_page_fields)
    for page in doc:
        pw, ph = page.rect.width, page.rect.height
        spans = _trusted_text_spans(page, pw, ph)
        fields = parse_page_fields({"form_type": _detect_form_type(
            "\n".join(s["text"] for s in spans)), "text_spans": spans,
            "ocr_lines": [], "from_ocr": False})
        for f in ("species_code",):
            v = fields.get(f)
            if v and re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", v.strip()):
                species.add(v.strip())
        w = fields.get("home_world")
        if w and 2 <= len(w.strip()) <= 20 and not w.strip().startswith("["):
            worlds.add(w.strip())
        p = fields.get("declared_purpose")
        if p:
            p = " ".join(p.split())
            if _PURPOSE_RE.fullmatch(p) and not _is_damaged(p):
                species.add(VOCAB_PURPOSE_PREFIX + p)
        n = fields.get("applicant_name")
        if n:
            n = " ".join(n.split())
            if _NAME_RE.fullmatch(n) and not _is_damaged(n):
                for tok in n.split():
                    species.add(VOCAB_NAME_PREFIX + tok)
    doc.close()
    return species, worlds
