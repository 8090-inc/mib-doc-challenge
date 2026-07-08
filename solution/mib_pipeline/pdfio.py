"""PDF text harvest with visibility classification.

Visible document evidence is the only trusted channel (challenge rule:
hidden text, off-crop text, and fake layers are adversarial). The core
oracle is a differential render: rasterize each page twice - as-is and
with all text redacted - and call a text span visible only if its bbox
region actually changes between the two renders (i.e. the glyphs
contribute ink). Attribute checks (render mode 3, opacity 0, white fill,
off-crop bbox) provide cheap early labels and trap forensics.
"""

from dataclasses import dataclass

import fitz
import numpy as np

RENDER_DPI = 150
_ZOOM = RENDER_DPI / 72.0
# Mean per-pixel |orig - notext| over a span bbox above which the span
# demonstrably contributes ink to the page.
INK_DIFF_THRESHOLD = 2.0
SCAN_IMAGE_COVERAGE = 0.85


@dataclass
class Span:
    text: str
    bbox: tuple           # (x0, y0, x1, y1) in PDF points
    size: float
    visible: bool
    hide_reason: str      # "" when visible
    page_index: int


@dataclass
class PageRecord:
    index: int
    width: float
    height: float
    rotation: int
    is_scanned: bool      # image page: text layer untrusted wholesale
    spans: list           # list[Span] - all spans, flagged
    gray: np.ndarray      # rendered grayscale image (visible appearance)
    hidden_text: str      # concatenated hidden span text (trap forensics)

    @property
    def visible_text(self) -> str:
        return "\n".join(s.text for s in self.spans if s.visible)


def _render_gray(page, clip=None) -> np.ndarray:
    pix = page.get_pixmap(matrix=fitz.Matrix(_ZOOM, _ZOOM), colorspace=fitz.csGRAY,
                          alpha=False, clip=clip)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _bbox_to_pixels(bbox, crop, shape):
    """Map a PDF-space bbox to array indices of the rendered cropbox."""
    x0 = int((bbox[0] - crop.x0) * _ZOOM)
    y0 = int((bbox[1] - crop.y0) * _ZOOM)
    x1 = int(np.ceil((bbox[2] - crop.x0) * _ZOOM))
    y1 = int(np.ceil((bbox[3] - crop.y0) * _ZOOM))
    h, w = shape
    return max(0, y0), min(h, y1), max(0, x0), min(w, x1)


def _image_coverage(page) -> float:
    area = 0.0
    page_area = abs(page.rect) or 1.0
    for block in page.get_text("dict", flags=fitz.TEXTFLAGS_DICT)["blocks"]:
        if block.get("type") == 1:  # image block
            r = fitz.Rect(block["bbox"]) & page.rect
            area += abs(r)
    return area / page_area


def _vector_text_ink(spans) -> int:
    return sum(len(s["text"].strip()) for s in spans)


def _iter_spans(page):
    d = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT)
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    yield span


def harvest_page(doc, page_index: int) -> PageRecord:
    page = doc[page_index]
    crop = page.rect  # cropbox in rotation-aware coordinates
    gray = _render_gray(page)

    raw_spans = list(_iter_spans(page))
    is_scanned = (_image_coverage(page) >= SCAN_IMAGE_COVERAGE
                  and _vector_text_ink(raw_spans) < 200)

    # Attribute metadata (render mode, opacity) via texttrace, keyed by bbox.
    trace_meta = []
    try:
        for t in page.get_texttrace():
            trace_meta.append((fitz.Rect(t["bbox"]), t.get("type", 0),
                               t.get("opacity", 1.0)))
    except Exception:
        pass

    def trace_lookup(rect):
        for trect, ttype, topa in trace_meta:
            if trect.intersects(rect) and abs(trect & rect) > 0.5 * abs(rect):
                return ttype, topa
        return 0, 1.0

    # Differential render: page with every text span redacted away.
    notext_gray = None
    if raw_spans and not is_scanned:
        shadow = fitz.open()
        shadow.insert_pdf(doc, from_page=page_index, to_page=page_index)
        spage = shadow[0]
        for span in _iter_spans(spage):
            spage.add_redact_annot(fitz.Rect(span["bbox"]))
        try:
            spage.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                   graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        except TypeError:  # older signature
            spage.apply_redactions()
        notext_gray = _render_gray(spage)
        if notext_gray.shape != gray.shape:
            notext_gray = None
        shadow.close()

    spans = []
    hidden_chunks = []
    for span in raw_spans:
        rect = fitz.Rect(span["bbox"])
        text = span["text"]
        size = span.get("size", 0.0)
        visible, reason = True, ""

        if is_scanned:
            visible, reason = False, "scanned_page_text_layer"
        elif not rect.intersects(crop) or abs(rect & crop) < 0.5 * abs(rect):
            visible, reason = False, "off_crop"
        elif size < 1.5:
            visible, reason = False, "tiny_font"
        else:
            ttype, topa = trace_lookup(rect)
            if ttype == 3:
                visible, reason = False, "invisible_render_mode"
            elif topa < 0.05:
                visible, reason = False, "zero_opacity"
            elif notext_gray is not None:
                y0, y1, x0, x1 = _bbox_to_pixels(span["bbox"], crop, gray.shape)
                if y1 > y0 and x1 > x0:
                    diff = np.abs(gray[y0:y1, x0:x1].astype(np.int16)
                                  - notext_gray[y0:y1, x0:x1].astype(np.int16))
                    if float(diff.mean()) < INK_DIFF_THRESHOLD:
                        visible, reason = False, "no_pixel_contribution"

        if not visible:
            hidden_chunks.append(text)
        spans.append(Span(text=text, bbox=tuple(span["bbox"]), size=size,
                          visible=visible, hide_reason=reason,
                          page_index=page_index))

    return PageRecord(index=page_index, width=crop.width, height=crop.height,
                      rotation=page.rotation, is_scanned=is_scanned,
                      spans=spans, gray=gray,
                      hidden_text=" ".join(hidden_chunks))


def harvest(pdf_path) -> list:
    doc = fitz.open(str(pdf_path))
    try:
        return [harvest_page(doc, i) for i in range(doc.page_count)]
    finally:
        doc.close()
