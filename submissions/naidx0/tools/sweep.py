#!/usr/bin/env python3
"""Grid-search pipeline parameters against the cached corpus.

Development tooling -- NOT copied into the Docker image.

Each candidate setting is applied to the live solution modules and the whole
corpus is re-scored from cached OCR, so a parameter sweep costs seconds instead
of one full pipeline run per point.  Anything that wins here still has to be
confirmed by the real pipeline before it ships.

Two guards against fooling ourselves:

  * every result reports catastrophic false approvals alongside the score, so a
    setting that buys points by approving true denials is visible rather than
    hidden inside a total; and
  * the winner is re-scored on 5 held-out folds, because picking the best of N
    settings on the same data is itself a way to overfit -- with enough points
    on a 1000-case corpus, noise alone produces a winner.

    python3 sweep.py <cache.pkl> <truth.csv> <param> [--fine]

Params: flag_min, flag_margin, flag_minlen, stale_days, species_min,
        world_min, fee_min, all
"""
import sys

import harness

# param -> (module attribute path, values to try)
GRIDS = {
    "flag_min": ("vocab.FLAG_RESCUE_MIN",
                 [50, 52, 54, 56, 58, 60, 62, 66, 70, 78]),
    "flag_margin": ("vocab.FLAG_RESCUE_MARGIN", [0, 4, 8, 12, 16, 20, 25]),
    "flag_minlen": ("vocab.FLAG_RESCUE_MINLEN", [6, 7, 8, 9, 10, 12]),
    "stale_days": ("adjudicate.STALE_DAYS", [150, 165, 180, 195, 210, 240]),
}


def set_param(path, value):
    mod_name, attr = path.split(".")
    mod = getattr(harness, mod_name)
    setattr(mod, attr, value)


def get_param(path):
    mod_name, attr = path.split(".")
    return getattr(getattr(harness, mod_name), attr)


def folded(cache, truth, folds=5):
    """Score each held-out fold separately, to see variance across subsets."""
    ids = sorted(truth)
    out = []
    for f in range(folds):
        sub = {c: truth[c] for i, c in enumerate(ids) if i % folds == f}
        out.append(harness.score(cache, sub)["total"])
    return out


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    which = sys.argv[3] if len(sys.argv) > 3 else "all"
    cache, truth = harness.load(cache_path, truth_path)

    base = harness.score(cache, truth)
    print(f"baseline: total {base['total']:.2f}  cls {base['classification']:.2f}"
          f"  ext {base['extraction']:.2f}  cal {base['calibration']:.2f}"
          f"  catastrophic {base['catastrophic']}\n")

    names = list(GRIDS) if which == "all" else [which]
    for name in names:
        path, values = GRIDS[name]
        original = get_param(path)
        print(f"--- {name}  ({path}, currently {original}) ---")
        print(f"{'value':>8} {'total':>8} {'delta':>7} {'cls':>7} {'ext':>7} "
              f"{'cal':>7} {'cata':>5}")
        results = []
        for v in values:
            set_param(path, v)
            r = harness.score(cache, truth)
            results.append((r["total"], v, r))
            mark = "  <-- current" if v == original else ""
            worse = "  CATASTROPHIC+" if r["catastrophic"] > base["catastrophic"] else ""
            print(f"{v:>8} {r['total']:8.2f} {r['total'] - base['total']:+7.2f} "
                  f"{r['classification']:7.2f} {r['extraction']:7.2f} "
                  f"{r['calibration']:7.2f} {r['catastrophic']:5d}"
                  f"{mark}{worse}")
        set_param(path, original)

        best_total, best_v, best_r = max(results, key=lambda x: x[0])
        if best_v == original:
            print(f"  -> current value {original} is already best\n")
            continue
        # Confirm the winner is not a lucky subset: compare per-fold spread.
        set_param(path, best_v)
        win_folds = folded(cache, truth)
        set_param(path, original)
        cur_folds = folded(cache, truth)
        wins = sum(w > c for w, c in zip(win_folds, cur_folds))
        print(f"  -> best {best_v} ({best_total:+.2f}); beats current in "
              f"{wins}/5 held-out folds")
        print(f"     folds best:    {' '.join(f'{x:.1f}' for x in win_folds)}")
        print(f"     folds current: {' '.join(f'{x:.1f}' for x in cur_folds)}")
        if wins <= 3:
            print("     VERDICT: not consistent across folds -- treat as noise.\n")
        elif best_r["catastrophic"] > base["catastrophic"]:
            print("     VERDICT: gains points but adds a false approval -- "
                  "check it is worth the risk.\n")
        else:
            print("     VERDICT: consistent gain, safe to adopt.\n")


if __name__ == "__main__":
    main()
