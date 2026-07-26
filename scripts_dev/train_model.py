#!/usr/bin/env python3
"""Train the probabilistic adjudication layer + confidence calibration.

Inputs: a debug sidecar (features from OUR OWN extraction - no gold leakage)
plus train labels. Produces:
  solution/models/adjudicator_rf.json   - random forest, pure-JSON trees
  solution/models/calibration.json      - isotonic bins for P(correct)
Reports OOF quality: cascade-only vs model+EV decision, per-section score.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "solution"))

from mib_pipeline import vocab  # noqa: E402
from mib_pipeline.features import FORCED, build_features  # noqa: E402
from mib_pipeline.rules import ev_utility  # noqa: E402

ADJ = ["APPROVED", "DENIED", "NEEDS_REVIEW"]

def export_forest(clf, feature_names):
    trees = []
    for est in clf.estimators_:
        t = est.tree_
        trees.append({
            "feature": t.feature.tolist(),
            "threshold": [round(x, 6) for x in t.threshold.tolist()],
            "left": t.children_left.tolist(),
            "right": t.children_right.tolist(),
            "value": [[round(v, 5) for v in (row[0] / max(1.0, row[0].sum())).tolist()]
                      for row in t.value],
        })
    return {"classes": ADJ, "feature_names": feature_names, "trees": trees}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", default="dev/run5_debug.jsonl")
    ap.add_argument("--trees", type=int, default=300)
    ap.add_argument("--depth", type=int, default=12)
    args = ap.parse_args()

    truth = {r["case_id"]: r for r in
             csv.DictReader(open(REPO / "data/train_labels.csv"))}
    records = [json.loads(l) for l in open(REPO / args.debug)]
    records = [r for r in records if "values" in r]

    feats = [build_features(d) for d in records]
    names = sorted(feats[0])
    X = np.array([[f[n] for n in names] for f in feats])
    y = np.array([ADJ.index(truth[d["case_id"]]["adjudication"]) for d in records])
    reasons = [(d.get("reason") or "clean").split(":")[0] for d in records]

    # OOF probabilities
    oof = np.zeros((len(y), 3))
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    for tr, te in skf.split(X, y):
        clf = RandomForestClassifier(n_estimators=args.trees, max_depth=args.depth,
                                     min_samples_leaf=3, random_state=0, n_jobs=4)
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])

    # Decisions: forced rungs stay forced; everything else EV-decides on model.
    def decide(i):
        reason = reasons[i]
        if reason in FORCED:
            pred = FORCED[reason]
            p = {"APPROVED": oof[i][0], "DENIED": oof[i][1],
                 "NEEDS_REVIEW": oof[i][2]}[pred]
            return pred, max(p, 0.5)
        pa, pd_, pr = oof[i]
        best = max(ADJ, key=lambda a: ev_utility(a, pa, pd_, pr))
        p = {"APPROVED": pa, "DENIED": pd_, "NEEDS_REVIEW": pr}[best]
        return best, p

    preds, praw = zip(*(decide(i) for i in range(len(y))))
    correct = np.array([ADJ.index(p) == y[i] for i, p in enumerate(preds)])

    raw_pts = 0.0
    fa = 0
    conf_counter = Counter()
    for i, p in enumerate(preds):
        t = ADJ[y[i]]
        conf_counter[(t, p)] += 1
        if p == t:
            raw_pts += 8
        elif t == "DENIED" and p == "APPROVED":
            raw_pts -= 4
            fa += 1
        elif p == "NEEDS_REVIEW":
            raw_pts += 2
        elif t == "NEEDS_REVIEW":
            raw_pts += 1
    print(f"OOF model+EV classification: {80*raw_pts/(8*len(y)):.2f}/80  "
          f"acc={correct.mean():.3f}  false_approvals={fa}")
    print("confusion:", dict(sorted(conf_counter.items())))

    # Isotonic-style binned calibration on OOF (monotone pooling).
    order = np.argsort(praw)
    praw_a = np.array(praw)
    n_bins = 12
    bins = []
    for b in range(n_bins):
        idx = order[int(b * len(y) / n_bins): int((b + 1) * len(y) / n_bins)]
        if len(idx) == 0:
            continue
        bins.append({"lo": float(praw_a[idx].min()),
                     "hi": float(praw_a[idx].max()),
                     "p": float(correct[idx].mean()),
                     "n": int(len(idx))})
    # enforce monotonicity (pool adjacent violators)
    changed = True
    while changed:
        changed = False
        for j in range(len(bins) - 1):
            if bins[j]["p"] > bins[j + 1]["p"]:
                a, b2 = bins[j], bins[j + 1]
                merged = {"lo": a["lo"], "hi": b2["hi"],
                          "p": (a["p"] * a["n"] + b2["p"] * b2["n"]) / (a["n"] + b2["n"]),
                          "n": a["n"] + b2["n"]}
                bins[j: j + 2] = [merged]
                changed = True
                break
    def calibrate(p):
        for b in bins:
            if p <= b["hi"]:
                return min(0.97, max(0.05, b["p"]))
        return min(0.97, max(0.05, bins[-1]["p"]))
    briers = [(calibrate(praw[i]) - (1.0 if correct[i] else 0.0)) ** 2
              for i in range(len(y))]
    mb = float(np.mean(briers))
    print(f"OOF calibration: mean brier {mb:.4f} -> {20*max(0,1-2*mb):.2f}/20")

    # Final model on all data + export
    clf = RandomForestClassifier(n_estimators=args.trees, max_depth=args.depth,
                                 min_samples_leaf=3, random_state=0, n_jobs=4)
    clf.fit(X, y)
    models = REPO / "solution" / "models"
    models.mkdir(exist_ok=True)
    with open(models / "adjudicator_rf.json", "w") as f:
        json.dump(export_forest(clf, names), f)
    with open(models / "calibration.json", "w") as f:
        json.dump({"bins": bins}, f, indent=1)
    size = (models / "adjudicator_rf.json").stat().st_size / 1e6
    print(f"exported adjudicator_rf.json ({size:.1f} MB), calibration.json")


if __name__ == "__main__":
    main()
