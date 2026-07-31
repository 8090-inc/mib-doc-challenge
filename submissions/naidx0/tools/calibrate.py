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

How much to shrink is itself a fitted quantity, so k is chosen by 5-fold
cross-validation: rates come from the training folds and are scored on the
held-out fold.  The in-sample number always improves and is therefore not
evidence of anything; the cross-validated number is the one to believe, and if
it is negative the honest conclusion is to leave the table alone.

    python3 calibrate.py <cache.pkl> <truth.csv> [k]
"""
import sys

import harness

PRIOR_K = 10.0


def rule_key(reason):
    """Collapse 'review_flag:a,b' -> 'review_flag' so parametrised rules pool."""
    return reason.split(":", 1)[0]


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    k = float(sys.argv[3]) if len(sys.argv) > 3 else PRIOR_K

    cache, truth = harness.load(cache_path, truth_path)

    cases = []       # (rule, current_conf, correct)
    stats = {}       # rule -> [n, correct, sum_of_current_conf]
    for cid, t, fields, aux, cands, adj, conf, reason in harness.run(cache, truth):
        correct = int(str(t.get("adjudication", "")).strip().upper() == adj)
        rule = rule_key(reason)
        cases.append((rule, conf, correct))
        s = stats.setdefault(rule, [0, 0, 0.0])
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

    print(f"\ncalibration now      {cur_s:.2f}/20 (Brier {cur_b:.4f})")
    print(f"calibration in-sample {new_s:.2f}/20 (Brier {new_b:.4f})  "
          f"[{new_s - cur_s:+.2f}, optimistic -- fitted on these same cases]")

    # --- cross-validated gain: the number that actually predicts the test set --
    print("\n5-fold cross-validated gain by shrink strength:")
    folds = 5
    best = None
    for kk in (0.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0):
        cv = 0.0
        for f in range(folds):
            tr = [c for i, c in enumerate(cases) if i % folds != f]
            te = [c for i, c in enumerate(cases) if i % folds == f]
            agg = {}
            for rule, _conf, ok in tr:
                a = agg.setdefault(rule, [0, 0])
                a[0] += 1
                a[1] += ok
            gp = (sum(a[1] for a in agg.values())
                  / max(1, sum(a[0] for a in agg.values())))
            for rule, _conf, ok in te:
                n_r, ok_r = agg.get(rule, [0, 0])
                c = (ok_r + kk * gp) / (n_r + kk) if (n_r + kk) else gp
                cv += (c - ok) ** 2
        cv_b = cv / len(cases)
        cv_s = 20.0 * max(0.0, 1.0 - 2.0 * cv_b)
        flag = ""
        if best is None or cv_s > best[1]:
            best, flag = (kk, cv_s), ""
        print(f"  k={kk:6g}  held-out {cv_s:6.2f}/20 (Brier {cv_b:.4f})  "
              f"{cv_s - cur_s:+.2f} vs current{flag}")
    print(f"\nbest shrink k={best[0]:g} -> held-out {best[1]:.2f}/20 "
          f"({best[1] - cur_s:+.2f} vs current {cur_s:.2f})")
    if best[1] <= cur_s:
        print("VERDICT: no honest gain here -- the current table already "
              "generalises at least as well.  Leave it alone.")
    else:
        print("VERDICT: real gain -- rebuild the table with this k, then "
              "confirm with replay.py on the full set.")

    print("\nCONFIDENCE = {")
    for n, rule, now, p, sm in sorted(rows, key=lambda r: r[1]):
        print(f'    "{rule}": {sm:.2f},'.ljust(40) + f"# n={n}, acc={p:.3f}")
    print("}")


if __name__ == "__main__":
    main()
