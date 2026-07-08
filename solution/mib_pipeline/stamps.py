"""Stamp, watermark, and adjudicator-note detection on rendered pages.

Red/blue colored regions are candidate stamps: OCR each candidate crop and
look for APPROVED / DENIED / RESCINDED / SAMPLE wording. A "sample" marking
neutralizes a denial stamp (manual trap); a rescinded denial does not deny.
Adjudicator-note pages are detected textually and provide the highest-
precedence override evidence.
"""

import re
from dataclasses import dataclass

import cv2
import fitz
import numpy as np

from .ocr import _parse_tsv, _run_tesseract


@dataclass
class StampEvidence:
    kind: str            # "approve" | "deny" | "rescinded" | "sample_denial"
    text: str
    page_index: int
    color: str           # "red" | "blue" | "text"


def _render_rgb(doc, page_index: int, dpi: int = 150) -> np.ndarray:
    page = doc[page_index]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return img


def find_stamp_regions(rgb: np.ndarray):
    """Return [(mask_color, x, y, w, h)] for saturated red/blue blobs."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    out = []
    masks = {
        "red": cv2.inRange(hsv, (0, 60, 60), (12, 255, 255))
               | cv2.inRange(hsv, (168, 60, 60), (180, 255, 255)),
        "blue": cv2.inRange(hsv, (95, 60, 60), (135, 255, 255)),
    }
    for color, mask in masks.items():
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < 2500 or w < 60 or h < 18:
                continue
            out.append((color, x, y, w, h))
    return out


_APPROVE_RE = re.compile(r"\bAPPROV", re.IGNORECASE)
_DENY_RE = re.compile(r"\bDEN[IY1l]", re.IGNORECASE)
_RESCIND_RE = re.compile(r"\bRESCIND", re.IGNORECASE)
_SAMPLE_RE = re.compile(r"\bSAMPLE\b|\bSPECIMEN\b", re.IGNORECASE)
_VOID_RE = re.compile(r"\bVOID\b|\bCANCELL?ED\b", re.IGNORECASE)


def read_stamps(doc, page_index: int, time_left=lambda: 30.0):
    """OCR colored stamp regions on one page and classify their meaning."""
    evidence = []
    if time_left() < 4:
        return evidence
    rgb = _render_rgb(doc, page_index)
    regions = find_stamp_regions(rgb)
    if not regions:
        return evidence
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    for color, x, y, w, h in regions[:6]:
        if time_left() < 3:
            break
        pad = 8
        crop = rgb[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        if crop.size == 0:
            continue
        # Isolate the colored ink as dark-on-white for OCR.
        crop_hsv = hsv[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
        if color == "red":
            ink = (cv2.inRange(crop_hsv, (0, 50, 50), (14, 255, 255))
                   | cv2.inRange(crop_hsv, (166, 50, 50), (180, 255, 255)))
        else:
            ink = cv2.inRange(crop_hsv, (92, 50, 50), (138, 255, 255))
        mono = 255 - ink
        if mono.shape[0] < 40:
            scale = 40 / mono.shape[0]
            mono = cv2.resize(mono, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
        tsv, _ = _run_tesseract(mono, psm=11, timeout=6.0)
        words = _parse_tsv(tsv)
        text = " ".join(w[0] for w in words)
        if not text.strip():
            continue
        is_sample = bool(_SAMPLE_RE.search(text))
        if _DENY_RE.search(text):
            kind = "sample_denial" if is_sample else "deny"
            if _RESCIND_RE.search(text) or _VOID_RE.search(text):
                kind = "rescinded"
            evidence.append(StampEvidence(kind, text, page_index, color))
        elif _APPROVE_RE.search(text):
            evidence.append(StampEvidence("approve", text, page_index, color))
        elif _RESCIND_RE.search(text):
            evidence.append(StampEvidence("rescinded", text, page_index, color))
    return evidence


_NOTE_APPROVE_RE = re.compile(
    r"(approv\w+|grant\w+|authoriz\w+)[^.\n]{0,60}(work|case|authorization|application)"
    r"|(case|application)[^.\n]{0,60}(approved|granted)"
    r"|override[^.\n]{0,40}approv", re.IGNORECASE)
_NOTE_DENY_RE = re.compile(
    r"(den\w+|reject\w+|refus\w+)[^.\n]{0,60}(work|case|authorization|application)"
    r"|(case|application)[^.\n]{0,60}(denied|rejected)", re.IGNORECASE)
_NOTE_RESCIND_RE = re.compile(
    r"(rescind\w+|withdraw\w+|vacat\w+|revers\w+)[^.\n]{0,60}(denial|decision)"
    r"|denial[^.\n]{0,60}(rescinded|withdrawn|vacated|reversed)", re.IGNORECASE)
_SIGNED_RE = re.compile(r"signed|signature|adjudicator|agent\s+[A-Z]", re.IGNORECASE)


def read_note_text(page_text: str, page_index: int):
    """Interpret adjudicator-note page wording (precedence #1 evidence)."""
    evidence = []
    if _NOTE_RESCIND_RE.search(page_text):
        evidence.append(StampEvidence("rescinded", page_text[:120], page_index, "text"))
    if _NOTE_APPROVE_RE.search(page_text) and _SIGNED_RE.search(page_text):
        evidence.append(StampEvidence("approve", page_text[:120], page_index, "text"))
    if _NOTE_DENY_RE.search(page_text) and not _NOTE_RESCIND_RE.search(page_text):
        evidence.append(StampEvidence("deny", page_text[:120], page_index, "text"))
    return evidence
