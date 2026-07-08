#!/usr/bin/env python3
"""Points-lost error analysis: joins case_scores.jsonl with truth + predictions,
ranks failure buckets by total points lost, prints worst cases per bucket."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FIELD_WEIGHTS = {"applicant_name": 5, "species_code": 6, "home_world": 5,
                 "visa_class": 5, "sponsor_id": 5, "arrival_date": 4,
                 "declared_purpose": 3, "risk_flags": 8, "fee_status": 4}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    run = Path(args.run)

    truth = {r["case_id"]: r for r in csv.DictReader(open(REPO / "data/train_labels.csv"))}
    preds = {}
    for line in open(run / "predictions.jsonl"):
        row = json.loads(line)
        preds[row["case_id"]] = row
    scores = [json.loads(line) for line in open(run / "case_scores.jsonl")]

    n = len(scores)
    field_lost = Counter()
    field_examples = defaultdict(list)
    class_lost = Counter()
    class_examples = defaultdict(list)
    brier_worst = []

    for s in scores:
        cid = s["case_id"]
        for field, res in s["field_results"].items():
            if res["status"] == "missed":
                pts = res["max_points"] * 50.0 / (45.0 * n)
                field_lost[field] += pts
                if len(field_examples[field]) < 200:
                    field_examples[field].append(
                        (cid, truth[cid][field], preds.get(cid, {}).get(field)))
        raw = s["classification_raw"]
        lost = (8 - raw) * 10.0 / n
        if raw < 8 and s["present"]:
            key = f'{s["truth_adjudication"]}->{s["pred_adjudication"]} ({s["classification_reason"]})'
            class_lost[key] += lost
            if len(class_examples[key]) < 200:
                class_examples[key].append(cid)
        if s.get("confidence_brier") is not None:
            brier_worst.append((s["confidence_brier"], cid, s["pred_adjudication"],
                                s["truth_adjudication"], preds.get(cid, {}).get("confidence")))

    print("=" * 70)
    print("CLASSIFICATION points lost by bucket (of 80):")
    for key, pts in class_lost.most_common():
        ex = " ".join(class_examples[key][:6])
        print(f"  {pts:6.2f}  {key}   e.g. {ex}")
    print(f"  total classification lost: {sum(class_lost.values()):.2f}")
    print()
    print("EXTRACTION points lost by field (of 50):")
    for field, pts in field_lost.most_common():
        print(f"  {pts:6.2f}  {field}")
        for cid, t, p in field_examples[field][:args.top // 3]:
            print(f"          {cid}: truth={t!r} pred={p!r}")
    print(f"  total extraction lost: {sum(field_lost.values()):.2f}")
    print()
    brier_worst.sort(reverse=True)
    mean_brier = sum(b for b, *_ in brier_worst) / len(brier_worst) if brier_worst else 0
    print(f"CALIBRATION mean brier {mean_brier:.4f} -> score {20*max(0,1-2*mean_brier):.2f}/20; worst:")
    for b, cid, pred, tr, conf in brier_worst[:args.top // 2]:
        print(f"  {b:.3f} {cid} pred={pred} truth={tr} conf={conf}")


if __name__ == "__main__":
    main()
