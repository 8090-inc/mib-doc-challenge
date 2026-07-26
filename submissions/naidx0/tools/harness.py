"""Shared replay plumbing for the analysis tools.

Development tooling -- NOT copied into the Docker image.

The cache holds ingested pages (the expensive OCR output).  Everything from
field extraction downward is re-run here, so a change to vocab.py's fuzzy
thresholds, to extract.py, or to adjudicate.py is measurable without touching a
PDF.  Keeping the load-and-decide path in one place stops the tools from
drifting apart and quietly reporting different numbers for the same code.
"""
import csv
import importlib
import pickle
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solution"))

import adjudicate  # noqa: E402
import extract  # noqa: E402
import ingest  # noqa: E402
import solution  # noqa: E402
import vocab  # noqa: E402

FIELD_W = {"applicant_name": 5, "species_code": 6, "home_world": 5,
           "visa_class": 5, "sponsor_id": 5, "arrival_date": 4,
           "declared_purpose": 3, "risk_flags": 8, "fee_status": 4}


def reload_solution():
    """Pick up edits to the solution modules without restarting the process."""
    importlib.reload(vocab)
    importlib.reload(extract)
    importlib.reload(adjudicate)
    importlib.reload(solution)


def load(cache_path, truth_path):
    cache = pickle.load(open(cache_path, "rb"))["results"]
    truth = {r["case_id"]: r for r in csv.DictReader(open(truth_path))}
    return cache, truth


def _batch_vocab(cache):
    """Reproduce solution.py's pass A over the cached pages.

    The real pipeline first harvests clean text-layer enum values across the
    WHOLE batch and feeds them to resolve_fields, so a species or home world
    printed cleanly on one packet helps canonicalize a mangled OCR read of the
    same value on another.  Replaying with empty vocabularies understates the
    score by about 0.3 -- the gap that first showed up against a real run.

    Mirrors ingest.quick_text_layer_values, but off cached pages: it uses only
    text spans (never OCR), so everything it needs is already in the cache.
    """
    species, worlds = set(), set()
    for res in cache.values():
        for page in res.get("pages") or []:
            spans = page.get("text_spans") or []
            if not spans:
                continue
            fields = extract.parse_page_fields({
                "form_type": ingest._detect_form_type(
                    "\n".join(s["text"] for s in spans)),
                "text_spans": spans, "ocr_lines": [], "from_ocr": False})
            v = fields.get("species_code")
            if v and re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", v.strip()):
                species.add(v.strip())
            w = fields.get("home_world")
            if w and 2 <= len(w.strip()) <= 20 and not w.strip().startswith("["):
                worlds.add(w.strip())
            p = fields.get("declared_purpose")
            if p:
                p = " ".join(p.split())
                if ingest._PURPOSE_RE.fullmatch(p) and not extract._is_damaged(p):
                    species.add(extract.VOCAB_PURPOSE_PREFIX + p)
            n = fields.get("applicant_name")
            if n:
                n = " ".join(n.split())
                if ingest._NAME_RE.fullmatch(n) and not extract._is_damaged(n):
                    for tok in n.split():
                        species.add(extract.VOCAB_NAME_PREFIX + tok)
    return frozenset(species), frozenset(worlds)


def run(cache, truth):
    """Yield (case_id, truth_row, record, aux, cands, decision, conf, reason).

    ``record`` is what the pipeline would actually emit, not the intermediate
    resolved fields -- solution.py runs a scavenge/placeholder layer on top of
    them (a wrong value and a missing value both score zero, so it guesses
    rather than leaving a field blank).  Scoring the raw fields instead
    understates extraction and would send us off optimising something the
    pipeline already handles.

    Both batch-level quantities solution.py derives -- the reference date and
    the modal fee fallback -- are computed over the whole cache first, exactly
    as the real run does.
    """
    species_vocab, world_vocab = _batch_vocab(cache)

    parsed = {}
    for cid, res in cache.items():
        if not res.get("ok"):
            parsed[cid] = None
            continue
        try:
            parsed[cid] = extract.resolve_fields(
                res["pages"], species_vocab, world_vocab)
        except Exception:
            parsed[cid] = None

    dates = [p[0].get("arrival_date") for p in parsed.values()
             if p and p[0].get("arrival_date")]
    ref = adjudicate.compute_ref_date(dates)

    fee_counts = {}
    for cid in sorted(parsed):
        p = parsed[cid]
        fs = p[0].get("fee_status") if p else None
        if fs in solution.FEE_VALUES:
            fee_counts[fs] = fee_counts.get(fs, 0) + 1
    fee_fallback = (sorted(fee_counts, key=lambda k: (-fee_counts[k], k))[0]
                    if fee_counts else "paid")

    for cid, t in sorted(truth.items()):
        if cid not in parsed:
            continue
        got = parsed[cid]
        if got is None:
            rec = solution._finalize_output(solution._default_record(cid))
            yield (cid, t, rec, {}, {}, "NEEDS_REVIEW", 0.6, "extract_failed")
            continue
        fields, aux, cands = got
        adj, conf, reason = adjudicate.adjudicate(fields, aux, cands, ref)
        rec = solution._finalize_output(solution._build_record(
            {"case_id": cid, "fields": fields, "aux": aux, "cands": cands,
             "ok": True}, ref, fee_fallback))
        yield (cid, t, rec, aux, cands, adj, conf, reason)


def norm(v):
    return " ".join(str(v or "").strip().split()).casefold()


def norm_flags(v):
    raw = norm(v)
    if raw in {"", "none", "null", "unknown"}:
        return "none"
    return "|".join(sorted(p.strip() for p in raw.split("|") if p.strip()))


def field_hit(field, got, want):
    if field == "risk_flags":
        return norm_flags(got) == norm_flags(want)
    return norm(got) == norm(want)


def classification_raw(truth_adj, pred_adj):
    if truth_adj == pred_adj:
        return 8.0, False
    if truth_adj == "DENIED" and pred_adj == "APPROVED":
        return -4.0, True          # catastrophic false approval
    if pred_adj == "NEEDS_REVIEW":
        return 2.0, False
    if truth_adj == "NEEDS_REVIEW":
        return 1.0, False
    return 0.0, False


def score(cache, truth):
    """Full deterministic score, mirroring scripts/evaluate.py.

    One deliberate simplification: the official scorer drops any field listed
    in a case's ``unrecoverable_fields`` from both the numerator and the
    maximum.  The public training labels carry no such column, so on this
    corpus there is nothing to drop and the arithmetic is identical.  It does
    mean the private extraction score should come out somewhat above the local
    one, since the deliberately destroyed fields we cannot read are excluded
    from the maximum there but counted as misses here.
    """
    ext_raw = ext_max = cls_raw = 0.0
    cata = 0
    briers = []
    rows = []
    for cid, t, fields, aux, cands, adj, conf, reason in run(cache, truth):
        for f, w in FIELD_W.items():
            ext_max += w
            if field_hit(f, fields.get(f, ""), t.get(f, "")):
                ext_raw += w
        tadj = str(t.get("adjudication", "")).strip().upper()
        raw_pts, is_cata = classification_raw(tadj, adj)
        cls_raw += raw_pts
        cata += int(is_cata)
        correct = (tadj == adj)
        briers.append((conf - (1.0 if correct else 0.0)) ** 2)
        rows.append((cid, t, fields, aux, cands, adj, conf, reason, tadj))

    n = len(briers)
    ext = 50.0 * ext_raw / ext_max if ext_max else 0.0
    cls = 80.0 * cls_raw / (8.0 * n) if n else 0.0
    brier = sum(briers) / n if n else 0.0
    cal = 20.0 * max(0.0, 1.0 - 2.0 * brier)
    return {"n": n, "extraction": ext, "classification": cls,
            "calibration": cal, "brier": brier, "total": ext + cls + cal,
            "catastrophic": cata, "rows": rows}
