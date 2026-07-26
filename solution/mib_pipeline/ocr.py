"""OCR path for scanned/raster pages.

Renders at 200 DPI, fixes orientation (OSD with 4-way fallback), deskews,
conditionally enhances (CLAHE for low contrast, median blur for speckle),
then runs Tesseract via subprocess (TSV output for word confidences) with a
hard per-call timeout. An escalation pass at 300 DPI / different PSM runs
only when the first pass is weak and the time governor allows.
"""

import subprocess
import tempfile
from dataclasses import dataclass, field

import cv2
import fitz
import numpy as np


@dataclass
class OcrResult:
    text: str
    words: list                 # (text, conf, x, y, w, h) in image pixels
    mean_conf: float
    rotation_applied: int       # 0/90/180/270
    skew_applied: float
    scale: float = 1.0          # image pixels per PDF point
    escalated: bool = False


def render_page(doc, page_index: int, dpi: int) -> np.ndarray:
    page = doc[page_index]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom),
                          colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _run_tesseract(img: np.ndarray, psm: int = 6, timeout: float = 20.0,
                   config_extra=()) -> tuple:
    """Return (tsv_text, ok). Subprocess keeps a hard timeout."""
    with tempfile.NamedTemporaryFile(suffix=".png", dir="/tmp") as tmp:
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            return "", False
        tmp.write(buf.tobytes())
        tmp.flush()
        cmd = ["tesseract", tmp.name, "stdout", "--oem", "1", "--psm", str(psm),
               "-c", "tessedit_do_invert=0", "tsv"]
        cmd[3:3] = list(config_extra)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout,
                                  env={"OMP_THREAD_LIMIT": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"})
            return proc.stdout, proc.returncode == 0
        except subprocess.TimeoutExpired:
            return "", False


def _parse_tsv(tsv: str):
    words = []
    for line in tsv.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) != 12 or parts[10] in ("-1", ""):
            continue
        text = parts[11].strip()
        if not text:
            continue
        try:
            conf = float(parts[10])
            x, y, w, h = int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9])
        except ValueError:
            continue
        words.append((text, conf, x, y, w, h))
    return words


def _mean_conf(words) -> float:
    return sum(w[1] for w in words) / len(words) if words else 0.0


def detect_orientation(img: np.ndarray, timeout: float = 8.0) -> int:
    """Tesseract OSD on a downsampled copy; returns rotation to apply."""
    small = cv2.resize(img, None, fx=0.5, fy=0.5) if max(img.shape) > 1200 else img
    with tempfile.NamedTemporaryFile(suffix=".png", dir="/tmp") as tmp:
        ok, buf = cv2.imencode(".png", small)
        if not ok:
            return 0
        tmp.write(buf.tobytes())
        tmp.flush()
        try:
            proc = subprocess.run(
                ["tesseract", tmp.name, "stdout", "--psm", "0"],
                capture_output=True, text=True, timeout=timeout,
                env={"OMP_THREAD_LIMIT": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"})
        except subprocess.TimeoutExpired:
            return 0
    rotate, conf = 0, 0.0
    for line in proc.stdout.splitlines():
        if line.startswith("Rotate:"):
            rotate = int(line.split(":")[1].strip())
        elif line.startswith("Orientation confidence:"):
            conf = float(line.split(":")[1].strip())
    return rotate if conf >= 1.0 else 0


def rotate_image(img: np.ndarray, angle: int) -> np.ndarray:
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def estimate_skew(img: np.ndarray) -> float:
    """Skew angle in degrees from the text mask, [-15, 15]."""
    small = cv2.resize(img, None, fx=0.4, fy=0.4)
    _, mask = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.dilate(mask, np.ones((3, 12), np.uint8))
    coords = cv2.findNonZero(mask)
    if coords is None or len(coords) < 100:
        return 0.0
    angle = cv2.minAreaRect(coords)[2]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle) if abs(angle) <= 15 else 0.0


def deskew(img: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.3:
        return img
    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _stretch(img: np.ndarray, p_lo: float = 0.5, p_hi: float = 90.0) -> np.ndarray:
    lo, hi = np.percentile(img, [p_lo, p_hi])
    if hi - lo < 5:
        return img
    out = np.clip((img.astype(np.float32) - lo) * 255.0 / (hi - lo), 0, 255)
    return out.astype(np.uint8)


def enhance_variants(img: np.ndarray):
    """Candidate enhancements, cheapest/most-likely-good first. OCR keeps the
    best-scoring variant, so a bad transform can only cost time, not accuracy."""
    yield "raw", img
    if img.std() < 45:
        yield "stretch", _stretch(img)
        if img.mean() > 225:
            # Washed-out pages: keep only the darkest ink and drop the
            # (lighter) ruling lines and haze entirely.
            for pct in (0.8, 1.6):
                th = np.percentile(img, pct)
                mask = (img <= th).astype(np.uint8) * 255
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                        np.ones((2, 2), np.uint8))
                if 0.001 < mask.mean() / 255.0 < 0.2:
                    yield f"dark_p{pct}", 255 - mask
        yield "clahe", cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(img)
    binary = (img < 128).astype(np.uint8)
    speckle = cv2.countNonZero(cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) ^ binary)
    if speckle > 0.02 * binary.size:
        yield "median", cv2.medianBlur(img, 3)


def ocr_page(doc, page_index: int, dpi: int = 200, allow_escalation: bool = True,
             time_left=lambda: 60.0) -> OcrResult:
    img = render_page(doc, page_index, dpi)

    rotation = detect_orientation(img) if time_left() > 10 else 0
    img = rotate_image(img, rotation)
    skew = estimate_skew(img)
    img = deskew(img, skew)

    words, conf = [], 0.0
    best_img = img
    for variant_name, candidate in enhance_variants(img):
        tsv, _ = _run_tesseract(candidate, psm=6,
                                timeout=min(20.0, max(5.0, time_left())))
        vwords = _parse_tsv(tsv)
        vconf = _mean_conf(vwords)
        score = vconf * (1 + 0.02 * len(vwords))
        if score > conf * (1 + 0.02 * len(words)):
            words, conf, best_img = vwords, vconf, candidate
        if conf >= 70 and len(words) >= 15:
            break
        if time_left() < 8:
            break
    img = best_img
    escalated = False

    # 4-way rotation rescue when OSD failed and the page reads as garbage.
    if conf < 30 and len(words) < 12 and rotation == 0 and time_left() > 20:
        best = (conf, words, 0)
        for angle in (90, 180, 270):
            alt = rotate_image(img, angle)
            tsv2, _ = _run_tesseract(alt[:alt.shape[0] // 2], psm=6, timeout=8.0)
            words2 = _parse_tsv(tsv2)
            if _mean_conf(words2) > best[0] + 8 and len(words2) >= len(best[1]):
                best = (_mean_conf(words2), words2, angle)
        if best[2]:
            rotation = best[2]
            img = rotate_image(img, rotation)
            tsv, _ = _run_tesseract(img, psm=6, timeout=min(20.0, max(5.0, time_left())))
            words = _parse_tsv(tsv)
            conf = _mean_conf(words)

    # Escalation: re-render at 300 DPI, best-of-variants with block PSM.
    if allow_escalation and (conf < 55 or len(words) < 30) and time_left() > 20:
        img2 = render_page(doc, page_index, 300)
        img2 = rotate_image(img2, rotation)
        img2 = deskew(img2, estimate_skew(img2))
        for variant_name, candidate in enhance_variants(img2):
            if time_left() < 6:
                break
            tsv2, _ = _run_tesseract(candidate, psm=4,
                                     timeout=min(25.0, max(5.0, time_left())))
            words2 = _parse_tsv(tsv2)
            vconf = _mean_conf(words2)
            if (vconf * (1 + 0.02 * len(words2))
                    > conf * (1 + 0.02 * len(words))):
                words, conf = words2, vconf
                dpi, escalated = 300, True
            if conf >= 70 and len(words) >= 15:
                break

    text = " ".join(w[0] for w in words)
    return OcrResult(text=text, words=words, mean_conf=conf,
                     rotation_applied=rotation, skew_applied=skew,
                     scale=dpi / 72.0, escalated=escalated)
