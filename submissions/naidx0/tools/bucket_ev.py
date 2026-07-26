#!/usr/bin/env python3
"""Per-rule expected value: is each rule emitting the decision it should?

Development tooling -- NOT copied into the Docker image.

Every case decided by one rule is a bucket with some mix of true labels.  The
scorer pays a fixed raw amount per (truth, prediction) pair, so once the mix is
known the best decision for that bucket is pure arithmetic -- no tuning:

    truth == pred                 +8
    truth DENIED, pred APPROVED   -4   (catastrophic)
    pred NEEDS_REVIEW             +2
    truth NEEDS_REVIEW            +1
    otherwise                      0

The asymmetry that matters: moving a bucket from NEEDS_REVIEW to APPROVED gains
+6 on every truly-approved case and loses 6 on every truly-denied one, so a
bucket that is mostly true approvals is being *underpaid* by a conservative
review.  This prints, for each rule, the raw score of the decision it currently
emits against the best alternative, so over-review shows up as a number instead
of an intuition.

Buckets are also split by whether the packet is DIP-1, since the exempt classes
behave differently and a rule can be right for one and wrong for the other.

    python3 bucket_ev.py <cache.pkl> <truth.csv> [--min N]
"""
import sys
from collections import defaultdict

import harness

DECISIONS = ("APPROVED", "DENIED", "NEEDS_REVIEW")


def raw(truth, pred):
    if truth == pred:
        return 8.0
    if truth == "DENIED" and pred == "APPROVED":
        return -4.0
    if pred == "NEEDS_REVIEW":
        return 2.0
    if truth == "NEEDS_REVIEW":
        return 1.0
    return 0.0


def rule_key(reason):
    return reason.split(":", 1)[0]


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    min_n = 1
    if "--min" in sys.argv:
        min_n = int(sys.argv[sys.argv.index("--min") + 1])

    cache, truth = harness.load(cache_path, truth_path)

    buckets = defaultdict(lambda: {"A": 0, "D": 0, "R": 0, "cur": None})
    total_n = 0
    for cid, t, fields, aux, cands, adj, _conf, reason in harness.run(cache, truth):
        dip = fields.get("visa_class") == "DIP-1"
        b = buckets[(rule_key(reason), "DIP-1" if dip else "other")]
        b["cur"] = adj
        b[{"APPROVED": "A", "DENIED": "D", "NEEDS_REVIEW": "R"}[
            str(t.get("adjudication", "")).strip().upper()]] += 1
        total_n += 1

    print(f"cases {total_n}   raw denominator {8 * total_n}   "
          f"(1 classification point = {8 * total_n / 80:.0f} raw)\n")
    print(f"{'rule':26s} {'cls':6s} {'n':>4} {'trueA':>6} {'trueD':>6} "
          f"{'trueR':>6}  {'now':>12} {'rawNow':>8} {'best':>12} "
          f"{'rawBest':>8} {'gain':>7}")

    rows = []
    for (rule, cls), b in buckets.items():
        n = b["A"] + b["D"] + b["R"]
        if n < min_n:
            continue
        counts = {"APPROVED": b["A"], "DENIED": b["D"], "NEEDS_REVIEW": b["R"]}
        sc = {d: sum(counts[t] * raw(t, d) for t in DECISIONS)
              for d in DECISIONS}
        best = max(DECISIONS, key=lambda d: sc[d])
        rows.append((sc[best] - sc[b["cur"]], rule, cls, n, b, sc, best))

    gain_total = 0.0
    for gain, rule, cls, n, b, sc, best in sorted(rows, key=lambda r: -r[0]):
        gain_total += max(0.0, gain)
        mark = "  <== " + best if gain > 0 else ""
        print(f"{rule:26s} {cls:6s} {n:4d} {b['A']:6d} {b['D']:6d} {b['R']:6d}"
              f"  {b['cur']:>12} {sc[b['cur']]:8.0f} {best:>12} "
              f"{sc[best]:8.0f} {gain:7.0f}{mark}")

    print(f"\nupper bound if every rule emitted its best single decision: "
          f"+{gain_total:.0f} raw = +{80 * gain_total / (8 * total_n):.2f} "
          f"classification points")
    print("NOTE: this is an oracle bound -- it picks the best decision using the\n"
          "      true labels.  It says which rules are mispriced and by how much,\n"
          "      not that the full amount is reachable.  Splitting a mixed bucket\n"
          "      with a real signal is what converts it into actual score.")


if __name__ == "__main__":
    main()
