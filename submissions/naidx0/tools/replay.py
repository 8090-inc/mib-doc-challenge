#!/usr/bin/env python3
"""Score adjudication changes against the cached extraction in ~1 second.

Development tooling -- NOT copied into the Docker image.

Reimplements the scorer's arithmetic (scripts/evaluate.py) over cached
(fields, aux, cands) so a change to adjudicate.py / calibration / policy tables
can be evaluated without re-running OCR.  Verify any winner with the real
pipeline before shipping it -- this replays the decision layer only.

    python3 replay.py <cache.pkl> <truth.csv>            # score current code
    python3 replay.py <cache.pkl> <truth.csv> --by-reason # per-rule accuracy
"""
import csv
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solution"))

import adjudicate  # noqa: E402

FIELD_W = {"applicant_name": 5, "species_code": 6, "home_world": 5,
           "visa_class": 5, "sponsor_id": 5, "arrival_date": 4,
           "declared_purpose": 3, "risk_flags": 8, "fee_status": 4}


def norm(v):
    return " ".join(str(v or "").strip().split()).casefold()


def norm_flags(v):
    raw = norm(v)
    if raw in {"", "none", "null", "unknown"}:
        return "none"
    return "|".join(sorted(p.strip() for p in raw.split("|") if p.strip()))


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


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    by_reason = "--by-reason" in sys.argv

    cache = pickle.load(open(cache_path, "rb"))["results"]
    truth = {r["case_id"]: r for r in csv.DictReader(open(truth_path))}

    dates = [c["fields"].get("arrival_date") for c in cache.values()
             if c["fields"].get("arrival_date")]
    ref = adjudicate.compute_ref_date(dates)

    ext_raw = ext_max = cls_raw = 0.0
    cata = 0
    briers = []
    reasons = {}
    confusion = {}

    for cid, t in sorted(truth.items()):
        res = cache.get(cid)
        if res is None:
            continue
        fields, aux, cands = res["fields"], res["aux"], res["cands"]
        if res.get("ok"):
            adj, conf, reason = adjudicate.adjudicate(fields, aux, cands, ref)
        else:
            adj, conf, reason = "NEEDS_REVIEW", 0.6, "extract_failed"

        for f, w in FIELD_W.items():
            ext_max += w
            got, want = fields.get(f, ""), t.get(f, "")
            hit = (norm_flags(got) == norm_flags(want) if f == "risk_flags"
                   else norm(got) == norm(want))
            ext_raw += w if hit else 0

        tadj = str(t.get("adjudication", "")).strip().upper()
        raw, is_cata = classification_raw(tadj, adj)
        cls_raw += raw
        cata += int(is_cata)
        correct = (tadj == adj)
        briers.append((conf - (1.0 if correct else 0.0)) ** 2)
        confusion[(tadj, adj)] = confusion.get((tadj, adj), 0) + 1
        n, ok = reasons.get(reason, (0, 0))
        reasons[reason] = (n + 1, ok + int(correct))

    n = len(briers)
    ext = 50.0 * ext_raw / ext_max if ext_max else 0.0
    cls = 80.0 * cls_raw / (8.0 * n) if n else 0.0
    brier = sum(briers) / n if n else 0.0
    cal = 20.0 * max(0.0, 1.0 - 2.0 * brier)

    print(f"cases {n}")
    print(f"Field extraction: {ext:.2f} / 50")
    print(f"Classification:   {cls:.2f} / 80")
    print(f"Calibration:      {cal:.2f} / 20   (Brier {brier:.4f})")
    print(f"TOTAL:            {ext + cls + cal:.2f} / 150")
    print(f"Catastrophic false approvals: {cata}")
    print("Confusion:")
    for k in sorted(confusion):
        print(f"  {k[0]:12s} -> {k[1]:12s} {confusion[k]}")

    if by_reason:
        print("\nper-rule accuracy (n, correct, rate) -- for calibration work:")
        for r in sorted(reasons, key=lambda r: -reasons[r][0]):
            cnt, ok = reasons[r]
            print(f"  {r:28s} n={cnt:4d} ok={ok:4d} rate={ok / cnt:.3f}")


if __name__ == "__main__":
    main()
