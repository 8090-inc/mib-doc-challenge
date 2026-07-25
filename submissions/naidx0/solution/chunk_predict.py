#!/usr/bin/env python3
"""Restart-resilient chunked prediction runner.

This environment restarts every 20-80 minutes and restores both the repo working
tree and the scratchpad from a snapshot, so the ONLY durable storage is a pushed
git commit.  This runner therefore processes the input in small chunks and
commits+pushes each chunk's predictions as soon as it lands.  Re-running after a
restart skips chunks already present in git and resumes from the first gap.

Usage:  python3 chunk_predict.py <input_dir> <tag> [chunk_size]
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = "/home/user/mib-doc-challenge"
SC = "/tmp/claude-0/-home-user-mib-doc-challenge/32d0b6d7-fa43-56fb-b0c0-046f84554b9a/scratchpad"
PY = f"{SC}/venv/bin/python"
SOLUTION = f"{REPO}/submissions/naidx0/solution/solution.py"
CHUNKDIR = Path(REPO) / "submissions/naidx0/_chunks"


def git(*args):
    return subprocess.call(["git", "-C", REPO] + list(args))


def main():
    input_dir, tag = sys.argv[1], sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 250

    pdfs = sorted(Path(input_dir).rglob("*.pdf"))
    chunks = [pdfs[i:i + size] for i in range(0, len(pdfs), size)]
    CHUNKDIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(pdfs)} pdfs -> {len(chunks)} chunks of {size}", flush=True)

    for idx, chunk in enumerate(chunks):
        out = CHUNKDIR / f"{tag}_{idx:03d}.jsonl"
        if out.exists() and sum(1 for _ in open(out)) == len(chunk):
            print(f"chunk {idx:03d}: already done", flush=True)
            continue

        staging = Path("/tmp") / f"stage_{tag}_{idx:03d}"
        subprocess.call(["rm", "-rf", str(staging)])
        staging.mkdir(parents=True, exist_ok=True)
        for p in chunk:
            (staging / p.name).symlink_to(p.resolve())

        print(f"chunk {idx:03d}: running {len(chunk)} pdfs", flush=True)
        subprocess.call([PY, SOLUTION, str(staging), str(out)])
        n = sum(1 for _ in open(out)) if out.exists() else 0
        print(f"chunk {idx:03d}: wrote {n}", flush=True)
        subprocess.call(["rm", "-rf", str(staging)])

        # Durable checkpoint: only a pushed commit survives a restart.
        git("add", str(out))
        git("-c", "user.name=naidx0", "-c", "user.email=pro79be@gmail.com",
            "commit", "-q", "-m", f"Add {tag} predictions chunk {idx:03d}")
        for _ in range(3):
            if git("push", "-q", "origin", "naidx0/mib-doc-challenge") == 0:
                break
        print(f"chunk {idx:03d}: checkpointed to git", flush=True)

    print("CHUNK_PREDICT_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
