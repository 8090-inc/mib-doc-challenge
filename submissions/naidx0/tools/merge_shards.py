#!/usr/bin/env python3
"""Merge whatever cache shards exist into a usable cache.

Development tooling -- NOT copied into the Docker image.

Lets the replay/EV tools run against a partially-built cache while the rest is
still being OCR'd.  Any measurement taken this way is on a subset and must be
re-checked on the full 1000 before it is believed -- a 145-case subset once hid
22 catastrophic false approvals, which is exactly the mistake this note exists
to prevent.

    python3 merge_shards.py <cache.pkl>
"""
import pickle
import sys
from pathlib import Path


def main():
    out = Path(sys.argv[1])
    shard_dir = out.with_suffix(".shards")
    results = {}
    shards = sorted(shard_dir.glob("*.pkl"))
    for shard in shards:
        results.update(pickle.load(open(shard, "rb")))
    with open(out, "wb") as fh:
        pickle.dump({"version": 1, "results": results},
                    fh, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"merged {len(shards)} shards -> {len(results)} cases -> {out}")


if __name__ == "__main__":
    main()
