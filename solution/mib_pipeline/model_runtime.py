"""Pure-python runtime for the JSON-exported adjudication forest and the
binned isotonic calibration. No sklearn/pickle in the container."""

import json
from functools import lru_cache
from pathlib import Path

MODELS = Path(__file__).resolve().parent.parent / "models"

ADJ = ["APPROVED", "DENIED", "NEEDS_REVIEW"]


@lru_cache(maxsize=1)
def _load():
    forest = json.loads((MODELS / "adjudicator_rf.json").read_text())
    calib = json.loads((MODELS / "calibration.json").read_text())
    return forest, calib


def predict_proba(features: dict):
    """Average class distributions across trees. features: name -> float."""
    forest, _ = _load()
    names = forest["feature_names"]
    x = [float(features.get(n, 0.0)) for n in names]
    acc = [0.0, 0.0, 0.0]
    trees = forest["trees"]
    for tree in trees:
        feat = tree["feature"]
        thr = tree["threshold"]
        left = tree["left"]
        right = tree["right"]
        node = 0
        while feat[node] >= 0:
            node = left[node] if x[feat[node]] <= thr[node] else right[node]
        val = tree["value"][node]
        acc[0] += val[0]
        acc[1] += val[1]
        acc[2] += val[2]
    n = float(len(trees))
    return acc[0] / n, acc[1] / n, acc[2] / n


def calibrate(p_raw: float) -> float:
    _, calib = _load()
    bins = calib["bins"]
    for b in bins:
        if p_raw <= b["hi"]:
            return min(0.97, max(0.05, b["p"]))
    return min(0.97, max(0.05, bins[-1]["p"])) if bins else max(0.05, min(0.97, p_raw))


def available() -> bool:
    try:
        _load()
        return True
    except Exception:
        return False
