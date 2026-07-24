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

def _preprocess(gray):
    """Return a cleaned binary (black text on white) for a degraded scan.

    The body text is very faint (values ~180-223) and unevenly lit, so a global
    threshold fails.  Instead we flatten illumination by dividing the image by a
    morphological background estimate (this makes faint text pop), Otsu-threshold
    the result, then remove the ruled-line / border-tick background via
    morphology and thicken broken strokes.
    """
    # upscale small embedded scans so glyphs are large enough for tesseract
    h0 = gray.shape[0]
    if h0 < 2200:
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    elif h0 > 3600:
        f = 3300.0 / h0
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)

    bg = cv2.morphologyEx(
        gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    )
    norm = cv2.divide(gray, bg, scale=255)
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


def _ocr_image(pil_gray, page_rotation=0):
    arr = np.array(pil_gray)
    clean = _preprocess(arr)
    try:
        best_text = pytesseract.image_to_string(clean, config="--psm 6")
    except Exception:
        best_text = ""
    best_score = _ocr_quality(best_text)
    # psm 4 fallback only when psm 6 looks weak
    if best_score < 4:
        try:
            txt = pytesseract.image_to_string(clean, config="--psm 4")
        except Exception:
            txt = ""
        if _ocr_quality(txt) > best_score:
            best_text, best_score = txt, _ocr_quality(txt)
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


def quick_text_layer_values(path):
    """Fast pass (no OCR): return clean species/home_world values from text
    layers to build the batch vocabulary."""
    species, worlds = set(), set()
    try:
        doc = fitz.open(path)
    except Exception:
        return species, worlds
    for page in doc:
        pw, ph = page.rect.width, page.rect.height
        spans = _trusted_text_spans(page, pw, ph)
        from extract import parse_page_fields  # local import to avoid cycle at module load
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
    doc.close()
    return species, worlds
