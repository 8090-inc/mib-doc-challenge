#!/usr/bin/env python3
"""Fit the EV adjudication tables and validate them out-of-fold.

Development tooling -- NOT copied into the Docker image (the fitted artifact
ev_weights.json is).

For every rule path this measures the empirical outcome mix BY RUNNING THE
REAL PIPELINE over the cached training corpus -- so extraction error is priced
into the probabilities -- then Dirichlet-smooths toward the global prior and
writes the artifact evmodel.py loads at runtime.

The number to believe is the OUT-OF-FOLD one: tables fitted on 4/5 of the
corpus and applied to the held-out fifth, cycled.  In-sample always looks
better; if OOF does not beat the pure-rules baseline the artifact should not
ship, and this tool refuses to write it.

    python3 evtrain.py <cache.pkl> <truth.csv> [--k 4] [--write]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import harness

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "solution"))
import evmodel  # noqa: E402

CLASSES = evmodel.CLASSES
FOLDS = 5


def fit_tables(rows, k):
    """rows: (rule_key, truth). Returns (tables, prior, note_conf)."""
    total = Counter(t for _rk, t in rows)
    n_all = sum(total.values()) or 1
    prior = {c: total.get(c, 0) / n_all for c in CLASSES}
    by_path = defaultdict(Counter)
    for rk, t in rows:
        by_path[rk][t] += 1
    tables = {}
    for rk, cnt in by_path.items():
        n = sum(cnt.values())
        tables[rk] = {c: (cnt.get(c, 0) + k * prior[c]) / (n + k)
                      for c in CLASSES}
    return tables, prior


def note_accuracy(rows_full):
    n = ok = 0
    for rk, truth, adj in rows_full:
        if rk in evmodel._NOTE_KEYS:
            n += 1
            ok += int(adj == truth)
    return (ok + 1.0) / (n + 2.0), n


def score(decisions):
    """decisions: (adj, conf, truth). Returns dict of components."""
    n = len(decisions)
    raw = brier = 0.0
    cata = 0
    for adj, conf, truth in decisions:
        raw += evmodel.PAYOFF[adj][truth] if adj != truth or True else 0
        # PAYOFF[action][truth] handles all cells incl. correct=8
        if truth == "DENIED" and adj == "APPROVED":
            cata += 1
        brier += (conf - (1.0 if adj == truth else 0.0)) ** 2
    cls = 80.0 * raw / (8.0 * n)
    b = brier / n
    cal = 20.0 * max(0.0, 1.0 - 2.0 * b)
    return {"cls": cls, "cal": cal, "sum": cls + cal, "brier": b, "cata": cata}


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    k = 4.0
    if "--k" in sys.argv:
        k = float(sys.argv[sys.argv.index("--k") + 1])
    do_write = "--write" in sys.argv

    cache, truth = harness.load(cache_path, truth_path)
    rows = []          # (cid, rule_key, rule_adj, rule_conf, truth)
    for cid, t, fields, aux, cands, adj, conf, reason, ref in \
            harness.run_raw(cache, truth):
        tadj = str(t.get("adjudication", "")).strip().upper()
        rows.append((cid, evmodel.rule_key(reason), adj, conf, tadj))

    base = score([(a, c, t) for _cid, _rk, a, c, t in rows])
    print(f"cases {len(rows)}")
    print(f"pure rules      : cls {base['cls']:6.2f}  cal {base['cal']:5.2f}  "
          f"sum {base['sum']:6.2f}  brier {base['brier']:.4f}  "
          f"cata {base['cata']}")

    for kk in ([k] if "--k" in sys.argv else [2.0, 4.0, 8.0, 16.0]):
        oof = []
        for f in range(FOLDS):
            tr = [(rk, t) for i, (_c, rk, _a, _cf, t) in enumerate(rows)
                  if i % FOLDS != f]
            nconf, _n_notes = note_accuracy(
                [(rk, t, a) for i, (_c, rk, a, _cf, t) in enumerate(rows)
                 if i % FOLDS != f])
            tables, prior = fit_tables(tr, kk)
            m = evmodel.EVModel({"tables": tables, "prior": prior,
                                 "note_conf": nconf})
            for i, (_cid, rk, adj, conf, t) in enumerate(rows):
                if i % FOLDS != f:
                    continue
                a2, c2, _r2 = m.decide(adj, conf, rk)
                oof.append((a2, c2, t))
        s = score(oof)
        print(f"EV OOF  k={kk:4g} : cls {s['cls']:6.2f}  cal {s['cal']:5.2f}  "
              f"sum {s['sum']:6.2f}  brier {s['brier']:.4f}  "
              f"cata {s['cata']}   ({s['sum'] - base['sum']:+.2f} vs rules)")

    # final fit on everything
    tables, prior = fit_tables([(rk, t) for _c, rk, _a, _cf, t in rows], k)
    nconf, n_notes = note_accuracy(
        [(rk, t, a) for _c, rk, a, _cf, t in rows])
    ins = []
    m = evmodel.EVModel({"tables": tables, "prior": prior, "note_conf": nconf})
    moves = Counter()
    for _cid, rk, adj, conf, t in rows:
        a2, c2, _r2 = m.decide(adj, conf, rk)
        ins.append((a2, c2, t))
        if a2 != adj:
            moves[(rk, adj, a2)] += 1
    s = score(ins)
    print(f"\nEV in-sample k={k:g}: cls {s['cls']:6.2f}  cal {s['cal']:5.2f}  "
          f"sum {s['sum']:6.2f}  brier {s['brier']:.4f}  cata {s['cata']}")
    print(f"note paths: n={n_notes}  smoothed accuracy={nconf:.4f}")
    print("\ndecision moves (path, rules->ev, n):")
    for (rk, a, b), n in moves.most_common():
        print(f"  {rk:24s} {a:12s} -> {b:12s} {n:4d}")
    print("\nper-path tables (n, pA, pD, pR -> EV action):")
    by_path = Counter(rk for _c, rk, _a, _cf, _t in rows)
    for rk, n in by_path.most_common():
        tb = tables[rk]
        ev = {a: sum(evmodel.PAYOFF[a][t] * tb[t] for t in CLASSES)
              for a in CLASSES}
        act = max(CLASSES, key=lambda a: ev[a])
        print(f"  {rk:24s} n={n:4d}  A={tb['APPROVED']:.2f} "
              f"D={tb['DENIED']:.2f} R={tb['NEEDS_REVIEW']:.2f}  -> {act}")

    if do_write:
        out = Path(__file__).resolve().parent.parent / "solution" / "ev_weights.json"
        artifact = {"tables": tables, "prior": prior, "note_conf": nconf,
                    "k": k, "fitted_on": len(rows), "conf_lo": 0.03,
                    "conf_hi": 0.99}
        out.write_text(json.dumps(artifact, indent=1, sort_keys=True))
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
