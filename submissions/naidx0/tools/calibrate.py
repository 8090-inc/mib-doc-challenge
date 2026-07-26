#!/usr/bin/env python3
"""Derive the per-rule confidence table that minimises the Brier score.

Development tooling -- NOT copied into the Docker image.

The calibration component of the score is `20 * max(0, 1 - 2*meanBrier)` where
Brier = mean (confidence - correct)^2.  For a group of cases decided by the same
rule and emitted with the same confidence c, the group's contribution is

    (c - p)^2 + p(1 - p)      with p = the rule's true accuracy

so the minimum is at c = p exactly, and the residual p(1-p) is irreducible
without changing the decisions themselves.  Confidence tuning is therefore not
a search problem: measure each rule's accuracy and emit it.

The one real risk is overfitting a rule that fired only a handful of times, so
rates are shrunk toward the global accuracy with a Beta(k) prior; k=10 leaves
high-count rules essentially at their measured rate while pulling an n=3 rule
most of the way back to the mean.

    python3 calibrate.py <cache.pkl> <truth.csv> [k]
"""
import csv
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solution"))

import adjudicate  # noqa: E402

PRIOR_K = 10.0


def rule_key(reason):
    """Collapse 'review_flag:a,b' -> 'review_flag' so parametrised rules pool."""
    return reason.split(":", 1)[0]


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    k = float(sys.argv[3]) if len(sys.argv) > 3 else PRIOR_K

    cache = pickle.load(open(cache_path, "rb"))["results"]
    truth = {r["case_id"]: r for r in csv.DictReader(open(truth_path))}

    dates = [c["fields"].get("arrival_date") for c in cache.values()
             if c["fields"].get("arrival_date")]
    ref = adjudicate.compute_ref_date(dates)

    stats = {}       # rule -> [n, correct, sum_of_current_conf]
    for cid, t in sorted(truth.items()):
        res = cache.get(cid)
        if res is None:
            continue
        if res.get("ok"):
            adj, conf, reason = adjudicate.adjudicate(
                res["fields"], res["aux"], res["cands"], ref)
        else:
            adj, conf, reason = "NEEDS_REVIEW", 0.6, "extract_failed"
        correct = int(str(t.get("adjudication", "")).strip().upper() == adj)
        s = stats.setdefault(rule_key(reason), [0, 0, 0.0])
        s[0] += 1
        s[1] += correct
        s[2] += conf

    n_all = sum(s[0] for s in stats.values())
    ok_all = sum(s[1] for s in stats.values())
    prior = ok_all / n_all

    cur = new = 0.0
    rows = []
    for rule, (n, ok, csum) in stats.items():
        p = ok / n
        smoothed = (ok + k * prior) / (n + k)
        cur += n * ((csum / n - p) ** 2 + p * (1 - p))
        new += n * ((smoothed - p) ** 2 + p * (1 - p))
        rows.append((n, rule, csum / n, p, smoothed))

    def score(brier_sum):
        b = brier_sum / n_all
        return 20.0 * max(0.0, 1.0 - 2.0 * b), b

    cur_s, cur_b = score(cur)
    new_s, new_b = score(new)

    print(f"cases {n_all}   global accuracy {prior:.4f}   shrink k={k:g}\n")
    print(f"{'rule':28s} {'n':>5} {'now':>7} {'acc':>7} {'->':>8}")
    for n, rule, now, p, sm in sorted(rows, key=lambda r: -r[0]):
        mark = "  <-- change" if abs(now - sm) >= 0.02 else ""
        print(f"{rule:28s} {n:5d} {now:7.3f} {p:7.3f} {sm:8.3f}{mark}")

    print(f"\ncalibration now {cur_s:.2f}/20 (Brier {cur_b:.4f})")
    print(f"calibration opt {new_s:.2f}/20 (Brier {new_b:.4f})")
    print(f"gain            {new_s - cur_s:+.2f}")

    print("\nCONFIDENCE = {")
    for n, rule, now, p, sm in sorted(rows, key=lambda r: r[1]):
        print(f'    "{rule}": {sm:.2f},'.ljust(40) + f"# n={n}, acc={p:.3f}")
    print("}")


if __name__ == "__main__":
    main()
