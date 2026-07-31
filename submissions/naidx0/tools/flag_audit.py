#!/usr/bin/env python3
"""Per-flag precision/recall for risk_flags, the heaviest extraction field.

Development tooling -- NOT copied into the Docker image.

risk_flags carries weight 8 of the 45 total field weight, i.e. 8.89 of the 50
extraction points -- more than any other field -- and it is scored as an exact
set match, so one missing member zeroes the whole field for that case.  This
prints, per flag, how often it is in the truth, how often we emit it, and how
the two overlap, plus what the field would score if each flag were fixed on its
own.

The motivating question: several flag names describe *derivable conditions*
rather than printed strings -- `illegible_biometrics` (the slip could not be
read), `sponsor_mismatch` / `identity_conflict` (two pages disagree).  The
pipeline already computes those states internally to drive review routing but
never emits them into the output field.  This measures what emitting them is
worth before any code is changed.

    python3 flag_audit.py <cache.pkl> <truth.csv>
"""
import sys
from collections import Counter

import harness
import vocab

TOTAL_W = 45.0
FLAG_W = 8.0


def parse(v):
    v = " ".join(str(v or "").strip().split()).casefold()
    if v in {"", "none", "null", "unknown"}:
        return frozenset()
    return frozenset(p.strip() for p in v.split("|") if p.strip())


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    cache, truth = harness.load(cache_path, truth_path)

    tp = Counter()
    fp = Counter()
    fn = Counter()
    n = exact = 0
    # what the field would score if one flag's errors vanished
    fixable = Counter()

    for cid, t, fields, aux, cands, adj, conf, reason in harness.run(cache, truth):
        n += 1
        want = parse(t.get("risk_flags"))
        got = parse(fields.get("risk_flags"))
        if want == got:
            exact += 1
        for f in want & got:
            tp[f] += 1
        for f in got - want:
            fp[f] += 1
        for f in want - got:
            fn[f] += 1
        diff = want ^ got
        if len(diff) == 1:
            fixable[next(iter(diff))] += 1

    print(f"cases {n}   risk_flags exact-match {exact} ({exact / n:.1%})")
    print(f"field is worth {FLAG_W / TOTAL_W * 50:.2f} of the 50 extraction "
          f"points; currently earning {FLAG_W / TOTAL_W * 50 * exact / n:.2f}\n")

    print(f"{'flag':24s} {'truth':>6} {'ours':>6} {'TP':>5} {'FP':>5} "
          f"{'FN':>5} {'prec':>6} {'rec':>6}  {'sole-cause':>10}")
    for f in sorted(set(tp) | set(fp) | set(fn),
                    key=lambda f: -(tp[f] + fn[f])):
        t_n, o_n = tp[f] + fn[f], tp[f] + fp[f]
        prec = tp[f] / o_n if o_n else 0.0
        rec = tp[f] / t_n if t_n else 0.0
        kind = ("DQ" if f in vocab.DISQUALIFYING_FLAGS
                else "REV" if f in vocab.REVIEW_FLAGS else "?")
        print(f"{f:24s} {t_n:6d} {o_n:6d} {tp[f]:5d} {fp[f]:5d} {fn[f]:5d} "
              f"{prec:6.3f} {rec:6.3f}  {fixable[f]:10d}  {kind}")

    print("\n'sole-cause' = cases where this flag is the ONLY difference "
          "between\nour set and the truth, so fixing it alone flips the case "
          "to an exact match:")
    gain = 0
    for f, c in fixable.most_common():
        pts = FLAG_W / TOTAL_W * 50 * c / n
        gain += pts
        print(f"  {f:24s} {c:4d} cases  -> +{pts:.2f} extraction points")
    print(f"  {'TOTAL':24s} {sum(fixable.values()):4d} cases  "
          f"-> +{gain:.2f} extraction points if every single-flag error were "
          f"fixed")


if __name__ == "__main__":
    main()
