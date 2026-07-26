#!/usr/bin/env python3
"""Score the pipeline against cached OCR in ~1 second.

Development tooling -- NOT copied into the Docker image.

Reimplements the scorer's arithmetic (scripts/evaluate.py) over cached ingested
pages, re-running extraction, canonicalization and adjudication.  Verify any
winner with the real pipeline before shipping it -- this replays everything
downstream of OCR, but not OCR itself.

    python3 replay.py <cache.pkl> <truth.csv>              # score current code
    python3 replay.py <cache.pkl> <truth.csv> --by-reason  # per-rule accuracy
    python3 replay.py <cache.pkl> <truth.csv> --by-field   # per-field extraction
"""
import sys
from collections import Counter

import harness


def main():
    cache_path, truth_path = sys.argv[1], sys.argv[2]
    cache, truth = harness.load(cache_path, truth_path)
    r = harness.score(cache, truth)

    print(f"cases {r['n']}")
    print(f"Field extraction: {r['extraction']:.2f} / 50")
    print(f"Classification:   {r['classification']:.2f} / 80")
    print(f"Calibration:      {r['calibration']:.2f} / 20   "
          f"(Brier {r['brier']:.4f})")
    print(f"TOTAL:            {r['total']:.2f} / 150")
    print(f"Catastrophic false approvals: {r['catastrophic']}")

    confusion = Counter((row[8], row[5]) for row in r["rows"])
    print("Confusion:")
    for k in sorted(confusion):
        print(f"  {k[0]:12s} -> {k[1]:12s} {confusion[k]}")

    if "--by-field" in sys.argv:
        print("\nper-field extraction:")
        for f, w in sorted(harness.FIELD_W.items(), key=lambda kv: -kv[1]):
            hits = sum(harness.field_hit(f, row[2].get(f, ""), row[1].get(f, ""))
                       for row in r["rows"])
            share = 50.0 * w / sum(harness.FIELD_W.values())
            print(f"  {f:16s} w={w}  {hits:4d}/{r['n']} = {hits / r['n']:.3f}  "
                  f"earning {share * hits / r['n']:5.2f} of {share:5.2f} "
                  f"(losing {share * (1 - hits / r['n']):5.2f})")

    if "--by-reason" in sys.argv:
        stats = {}
        for row in r["rows"]:
            reason, adj, tadj = row[7], row[5], row[8]
            n, ok = stats.get(reason, (0, 0))
            stats[reason] = (n + 1, ok + int(adj == tadj))
        print("\nper-rule accuracy (n, correct, rate):")
        for rr in sorted(stats, key=lambda x: -stats[x][0]):
            cnt, ok = stats[rr]
            print(f"  {rr:28s} n={cnt:4d} ok={ok:4d} rate={ok / cnt:.3f}")


if __name__ == "__main__":
    main()
