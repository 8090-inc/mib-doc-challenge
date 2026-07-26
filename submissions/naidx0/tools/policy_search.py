#!/usr/bin/env python3
"""Search for rule buckets whose emitted decision is mispriced.

Development tooling -- NOT copied into the Docker image.

Every rule in adjudicate.py decides a bucket of cases.  If a bucket's true
labels are mostly APPROVED, routing it to NEEDS_REVIEW leaves 6 raw points per
case on the table; if they are mostly DENIED, approving it costs 6.  Rather
than editing rules one at a time and re-running the pipeline, this remaps
(rule -> decision) after the fact and re-scores, so a whole policy variant
costs a second.

Greedy forward selection: repeatedly adopt the single remap that most improves
the *cross-validated* score, stopping when nothing helps.  Every step is scored
with 5-fold CV -- the bucket's decision and its confidence are both fitted on
the training folds and evaluated on the held-out fold -- because choosing the
best of ~60 candidate remaps on the same data it was measured on is a reliable
way to manufacture a gain that does not survive contact with the test set.

Catastrophic false approvals are tracked throughout and a remap that adds them
is reported, since the scorer's -4 already prices them but the headline count
matters independently.

    python3 policy_search.py <cache.pkl> <truth.csv> [--max-steps N]
"""
import sys
from collections import defaultdict

import harness

DECISIONS = ("APPROVED", "DENIED", "NEEDS_REVIEW")
FOLDS = 5


def rule_key(reason):
    return reason.split(":", 1)[0]


def collect(cache, truth):
    """One pass over the corpus -> everything the search needs."""
    rows = []
    for cid, t, rec, aux, cands, adj, conf, reason in harness.run(cache, truth):
        rows.append({
            "cid": cid,
            "rule": rule_key(reason),
            "base_adj": adj,
            "base_conf": conf,
            "truth": str(t.get("adjudication", "")).strip().upper(),
            "fold": len(rows) % FOLDS,
        })
    return rows


def evaluate(rows, remap, fit_conf=True):
    """Cross-validated classification + calibration under a remap.

    Both the decision and the confidence for a remapped bucket are fitted on
    the training folds only, so the returned score is what the change would be
    worth on unseen cases rather than on the cases that suggested it.
    """
    cls_raw = 0.0
    brier = 0.0
    cata = 0
    n = len(rows)
    for f in range(FOLDS):
        tr = [r for r in rows if r["fold"] != f]
        te = [r for r in rows if r["fold"] == f]
        # confidence for each (rule, decision) fitted on training folds
        acc = defaultdict(lambda: [0, 0])
        for r in tr:
            d = remap.get(r["rule"], r["base_adj"])
            a = acc[(r["rule"], d)]
            a[0] += 1
            a[1] += int(r["truth"] == d)
        for r in te:
            d = remap.get(r["rule"], r["base_adj"])
            pts, is_cata = harness.classification_raw(r["truth"], d)
            cls_raw += pts
            cata += int(is_cata)
            if r["rule"] in remap and fit_conf:
                cnt, ok = acc[(r["rule"], d)]
                c = ok / cnt if cnt else r["base_conf"]
            else:
                c = r["base_conf"]
            brier += (c - (1.0 if r["truth"] == d else 0.0)) ** 2
    cls = 80.0 * cls_raw / (8.0 * n)
    b = brier / n
    cal = 20.0 * max(0.0, 1.0 - 2.0 * b)
    return {"classification": cls, "calibration": cal, "sum": cls + cal,
            "catastrophic": cata}


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    max_steps = 6
    if "--max-steps" in sys.argv:
        max_steps = int(sys.argv[sys.argv.index("--max-steps") + 1])

    cache, truth = harness.load(cache_path, truth_path)
    rows = collect(cache, truth)
    rules = sorted({r["rule"] for r in rows})

    base = evaluate(rows, {})
    print(f"cases {len(rows)}   rules {len(rules)}")
    print(f"baseline (cross-validated): classification {base['classification']:.2f}"
          f"  calibration {base['calibration']:.2f}"
          f"  sum {base['sum']:.2f}  catastrophic {base['catastrophic']}\n")

    # Per-rule bucket composition, for context.
    comp = defaultdict(lambda: defaultdict(int))
    for r in rows:
        comp[r["rule"]][r["truth"]] += 1
    print(f"{'rule':26s} {'n':>4} {'A':>4} {'D':>4} {'R':>4}  {'emits':>12}")
    for rule in sorted(rules, key=lambda x: -sum(comp[x].values())):
        c = comp[rule]
        emits = next(r["base_adj"] for r in rows if r["rule"] == rule)
        print(f"{rule:26s} {sum(c.values()):4d} {c['APPROVED']:4d} "
              f"{c['DENIED']:4d} {c['NEEDS_REVIEW']:4d}  {emits:>12}")

    remap = {}
    print("\n--- greedy forward selection (cross-validated) ---")
    for step in range(max_steps):
        best = None
        for rule in rules:
            if rule in remap:
                continue
            cur = next(r["base_adj"] for r in rows if r["rule"] == rule)
            for d in DECISIONS:
                if d == cur:
                    continue
                trial = dict(remap)
                trial[rule] = d
                sc = evaluate(rows, trial)
                if best is None or sc["sum"] > best[0]["sum"]:
                    best = (sc, rule, d)
        if best is None:
            break
        sc, rule, d = best
        gain = sc["sum"] - base["sum"]
        if sc["sum"] <= base["sum"] + 1e-9:
            print(f"step {step + 1}: no remaining remap improves the held-out "
                  f"score (best candidate {rule} -> {d} at {gain:+.2f})")
            break
        cur = next(r["base_adj"] for r in rows if r["rule"] == rule)
        n_rule = sum(comp[rule].values())
        print(f"step {step + 1}: {rule} ({n_rule} cases) {cur} -> {d}"
              f"   sum {sc['sum']:.2f} ({gain:+.2f} vs baseline)"
              f"   catastrophic {sc['catastrophic']}")
        remap[rule] = d
        base_after = sc

    if not remap:
        print("\nNo mispriced buckets found: every rule already emits the "
              "decision that maximises the held-out score.")
        return

    final = evaluate(rows, remap)
    print(f"\nadopted remaps: {remap}")
    print(f"held-out classification {base['classification']:.2f} -> "
          f"{final['classification']:.2f}")
    print(f"held-out calibration    {base['calibration']:.2f} -> "
          f"{final['calibration']:.2f}")
    print(f"held-out sum            {base['sum']:.2f} -> {final['sum']:.2f} "
          f"({final['sum'] - base['sum']:+.2f})")
    print(f"catastrophic            {base['catastrophic']} -> "
          f"{final['catastrophic']}")
    print("\nThese are post-hoc remaps of whole buckets.  Implement each one as "
          "a rule change in\nadjudicate.py, then confirm with replay.py -- and "
          "prefer splitting a mixed bucket on a\nreal signal over flipping it "
          "wholesale, which only trades one error for another.")


if __name__ == "__main__":
    main()
