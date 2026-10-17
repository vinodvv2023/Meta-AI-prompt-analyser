"""Evaluate local label definitions against a JSON list of manually labeled prompts."""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from laya_classifier import MODEL, REVISION, evaluate
from label_store import FIELDS


def metrics(rows, predictions):
    report = {}
    for field in FIELDS:
        tp = sum(row[field] and prediction[field] for row, prediction in zip(rows, predictions))
        fp = sum(not row[field] and prediction[field] for row, prediction in zip(rows, predictions))
        fn = sum(row[field] and not prediction[field] for row, prediction in zip(rows, predictions))
        report[field] = {"true_positive": tp, "false_positive": fp, "false_negative": fn,
                         "precision": tp / (tp + fp) if tp + fp else None,
                         "recall": tp / (tp + fn) if tp + fn else None}
    return report


def run(path):
    load_dotenv(Path(__file__).with_name(".env"))
    model = os.getenv("LAYA_MODEL", MODEL)
    revision = os.getenv("LAYA_MODEL_REVISION", REVISION)
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty JSON list of labeled prompts")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("prompt"), str) or not row["prompt"].strip():
            raise ValueError("Each row needs a nonempty prompt")
        if any(type(row.get(field)) is not bool for field in FIELDS):
            raise ValueError("Each row needs boolean is_xx and is_xxx labels")
    predictions, cases = [], []
    for index, row in enumerate(rows):
        scores = evaluate(row["prompt"], model, revision)
        predicted = {field: scores[field] >= 0.5 for field in FIELDS}
        predictions.append(predicted)
        cases.append({"index": index, "expected": {field: row[field] for field in FIELDS},
                      "predicted": predicted, "scores": scores})
    return {"model": model, "revision": revision, "count": len(rows),
            "note": "Raw 0.5 decisions for evaluation only; this is not a calibrated deployment threshold.",
            "metrics": metrics(rows, predictions), "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", help="JSON list with prompt, is_xx, and is_xxx")
    parser.add_argument("--output", help="Optional report path (never includes prompt text)")
    args = parser.parse_args()
    report = run(args.fixtures)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
