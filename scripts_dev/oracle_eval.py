#!/usr/bin/env python3
"""Regression gate: run the rule cascade on TRUE train fields (field-oracle
mode) and verify >= 973/1000 accuracy with zero catastrophic false approvals.

This locks the cascade rung order. Run after any change to rules.py.
"""
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "solution"))

from mib_pipeline.rules import CaseBelief, cascade  # noqa: E402


def belief_from_truth(row) -> CaseBelief:
    flags = frozenset(f for f in row["risk_flags"].split("|") if f and f != "none")
    arrival = None
    if row["arrival_date"]:
        arrival = date.fromisoformat(row["arrival_date"])
    # Oracle mode has no per-document receipt date; approximate the batch
    # receipt window from the newest arrival date in the corpus (see caller).
    return CaseBelief(
        visa_class=row["visa_class"],
        fee_status=row["fee_status"],
        risk_flags=flags,
        sponsor_id=row["sponsor_id"],
        sponsor_seen=True,
        home_world=row["home_world"],
        arrival_date=arrival,
    )


def main():
    rows = list(csv.DictReader(open(REPO / "data" / "train_labels.csv")))
    # Batch clock: newest arrival date across the corpus stands in for the
    # packet receipt window (per-document receipt dates only exist in PDFs).
    batch_clock = max(date.fromisoformat(r["arrival_date"]) for r in rows if r["arrival_date"])

    correct = 0
    false_approvals = 0
    confusion = {}
    for row in rows:
        belief = belief_from_truth(row)
        belief.receipt_date = batch_clock
        adjudication, reason = cascade(belief)
        truth = row["adjudication"]
        key = f"{truth}->{adjudication}"
        confusion[key] = confusion.get(key, 0) + 1
        if adjudication == truth:
            correct += 1
        if truth == "DENIED" and adjudication == "APPROVED":
            false_approvals += 1

    print(f"oracle cascade: {correct}/1000 correct, {false_approvals} false approvals")
    for key in sorted(confusion):
        print(f"  {key}: {confusion[key]}")
    if correct < 973 or false_approvals > 0:
        print("REGRESSION: cascade below locked baseline (973, 0 FA)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
