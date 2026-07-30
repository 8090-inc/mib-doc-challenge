#!/usr/bin/env python3
"""Train the within-path review resolver and validate it out-of-fold.

Development tooling -- NOT copied into the Docker image; scikit-learn is a
DEV dependency only.  The fitted forest is exported to plain JSON arrays and
walked at runtime by evmodel.forest_proba (float32 feature cast matching
sklearn's internals), so the scoring container needs nothing new.

The resolver targets the REVIEW-FAMILY paths -- buckets the rules route to
NEEDS_REVIEW for lack of evidence, whose true-label mix is heavily approvable
but not uniformly so.  The path table prices the whole bucket; the forest
separates cases WITHIN the bucket using identity-free structural features
(evidence quality, page composition, enum values -- never names or ids).

Selection is honest: 5-fold out-of-fold, the forest+table blend must beat the
table alone on the held-out sum or nothing is written.

    python3 forest_train.py <cache.pkl> <truth.csv> [--write]
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

import evtrain
import harness

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "solution"))
import evmodel  # noqa: E402

CLASSES = evmodel.CLASSES
FOLDS = 5
# The paths the resolver may act on: review-family only.  Locked denial
# paths, note paths, and clean approvals are out of scope by construction.
TARGET_PATHS = ("unverified_clean", "fee_unverified", "med3_no_biometric",
                "illegible_page", "uncertain_flags", "insufficient_evidence",
                "damaged_field", "missing_arrival", "fee_unknown",
                "unsupported_waiver")
SEEDS = (7, 19, 43, 71, 101)
BLENDS = (0.35, 0.5, 0.65, 0.8, 1.0)


def export_forest(models, feature_names, paths, blend):
    trees = []
    for m in models:
        for est in m.estimators_:
            t = est.tree_
            trees.append({
                "feature": [int(v) for v in t.feature],
                "threshold": [float(v) for v in t.threshold],
                "left": [int(v) for v in t.children_left],
                "right": [int(v) for v in t.children_right],
                "value": [[float(x) for x in row[0]] for row in t.value],
            })
    return {"trees": trees, "feature_names": list(feature_names),
            "paths": list(paths), "blend": blend}


def fit_models(X, y, seeds=SEEDS):
    models = []
    for seed in seeds:
        m = ExtraTreesClassifier(
            n_estimators=300, max_depth=4, max_features=0.7,
            min_samples_leaf=6, random_state=seed, n_jobs=1)
        m.fit(X, y)
        assert list(m.classes_) == list(CLASSES), m.classes_
        models.append(m)
    return models


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    do_write = "--write" in sys.argv

    cache, truth = harness.load(cache_path, truth_path)
    rows = []
    for cid, t, fields, aux, cands, adj, conf, reason, ref in \
            harness.run_raw(cache, truth):
        rk = evmodel.rule_key(reason)
        tadj = str(t.get("adjudication", "")).strip().upper()
        x = evmodel.featurize(fields, aux, cands, reason, ref)
        rows.append((cid, rk, adj, conf, tadj, x))

    in_scope = [r for r in rows if r[1] in TARGET_PATHS]
    mix = Counter(r[4] for r in in_scope)
    print(f"cases {len(rows)}; resolver scope {len(in_scope)} "
          f"(mix {dict(mix)})")

    # baseline: tables-only OOF (k=4), for the same honest comparison
    def run_oof(blend):
        oof = []
        for f in range(FOLDS):
            tr_tab = [(rk, t) for i, (_c, rk, _a, _cf, t, _x)
                      in enumerate(rows) if i % FOLDS != f]
            tables, prior = evtrain.fit_tables(tr_tab, 4.0)
            nconf, _ = evtrain.note_accuracy(
                [(rk, t, a) for i, (_c, rk, a, _cf, t, _x)
                 in enumerate(rows) if i % FOLDS != f])
            art = {"tables": tables, "prior": prior, "note_conf": nconf}
            if blend is not None:
                tr_f = [(x, t) for i, (_c, rk, _a, _cf, t, x)
                        in enumerate(rows)
                        if i % FOLDS != f and rk in TARGET_PATHS]
                X = np.asarray([x for x, _t in tr_f], dtype=np.float32)
                y = np.asarray([t for _x, t in tr_f])
                models = fit_models(X, y)
                art["forest"] = export_forest(
                    models, evmodel.FEATURE_NAMES, TARGET_PATHS, blend)
            m = evmodel.EVModel(art)
            for i, (_cid, rk, adj, conf, t, x) in enumerate(rows):
                if i % FOLDS != f:
                    continue
                # reconstruct enough of (fields..) for featurize? we already
                # have x; decide() only needs it via featurize, so feed a
                # tiny shim that returns the precomputed vector.
                if art.get("forest") and rk in TARGET_PATHS:
                    pf = evmodel.forest_proba(art["forest"], x)
                    w = blend
                    probs = {c: w * pf[c] + (1 - w) * m.probs_for(rk)[c]
                             for c in CLASSES}
                    ev = {a: sum(evmodel.PAYOFF[a][tt] * probs[tt]
                                 for tt in CLASSES) for a in CLASSES}
                    allowed = {"APPROVED": ("APPROVED", "NEEDS_REVIEW"),
                               "DENIED": ("DENIED", "NEEDS_REVIEW"),
                               "NEEDS_REVIEW": CLASSES}[adj]
                    choice, best = adj, ev.get(adj, float("-inf"))
                    for a in allowed:
                        if ev[a] > best + 1e-12:
                            best, choice = ev[a], a
                    cconf = min(0.99, max(0.03, probs[choice]))
                    oof.append((choice, round(cconf, 3), t))
                else:
                    a2, c2, _ = m.decide(adj, conf, rk)
                    oof.append((a2, c2, t))
        return evtrain.score(oof)

    base = evtrain.score([(a, c, t) for _c, _rk, a, c, t, _x in rows])
    print(f"pure rules      : cls {base['cls']:6.2f} cal {base['cal']:5.2f} "
          f"sum {base['sum']:6.2f} cata {base['cata']}")
    tab = run_oof(None)
    print(f"tables OOF      : cls {tab['cls']:6.2f} cal {tab['cal']:5.2f} "
          f"sum {tab['sum']:6.2f} cata {tab['cata']} "
          f"({tab['sum'] - base['sum']:+.2f})")
    results = []
    for b in BLENDS:
        s = run_oof(b)
        results.append((s["sum"], b, s))
        print(f"forest OOF w={b:4g}: cls {s['cls']:6.2f} cal {s['cal']:5.2f} "
              f"sum {s['sum']:6.2f} cata {s['cata']} "
              f"({s['sum'] - base['sum']:+.2f})")

    best_sum, best_b, best_s = max(results)
    winner = max(best_sum, tab["sum"])
    if winner <= base["sum"]:
        print("\nVERDICT: nothing beats the pure rules out-of-fold; "
              "ship no artifact.")
        return
    if do_write:
        tables, prior = evtrain.fit_tables(
            [(rk, t) for _c, rk, _a, _cf, t, _x in rows], 4.0)
        nconf, _ = evtrain.note_accuracy(
            [(rk, t, a) for _c, rk, a, _cf, t, _x in rows])
        art = {"tables": tables, "prior": prior, "note_conf": nconf,
               "k": 4.0, "fitted_on": len(rows),
               "conf_lo": 0.03, "conf_hi": 0.99}
        if best_sum > tab["sum"]:
            tr_f = [(x, t) for _c, rk, _a, _cf, t, x in rows
                    if rk in TARGET_PATHS]
            X = np.asarray([x for x, _t in tr_f], dtype=np.float32)
            y = np.asarray([t for _x, t in tr_f])
            art["forest"] = export_forest(
                fit_models(X, y), evmodel.FEATURE_NAMES, TARGET_PATHS, best_b)
            print(f"\nshipping tables + forest (blend {best_b})")
        else:
            print("\nshipping tables only (forest did not beat them OOF)")
        out = (Path(__file__).resolve().parent.parent / "solution"
               / "ev_weights.json")
        out.write_text(json.dumps(art, sort_keys=True))
        print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
