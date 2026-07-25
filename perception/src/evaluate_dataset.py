"""Dependency-free classification/performance report for recorded target data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def evaluate_records(records: Iterable[dict[str, object]]) -> dict[str, object]:
    rows = list(records)
    labels = sorted(
        {
            str(value)
            for row in rows
            for value in (row.get("expected"), row.get("predicted"))
            if value is not None
        }
    )
    matrix = {expected: {predicted: 0 for predicted in labels} for expected in labels}
    latencies: list[float] = []
    elapsed: list[float] = []
    for row in rows:
        expected, predicted = str(row["expected"]), str(row["predicted"])
        matrix[expected][predicted] += 1
        if "latencyMs" in row:
            latencies.append(float(row["latencyMs"]))
        if "elapsedSec" in row:
            elapsed.append(float(row["elapsedSec"]))
    metrics: dict[str, dict[str, float]] = {}
    for label in labels:
        true_positive = matrix[label][label]
        predicted_total = sum(matrix[expected][label] for expected in labels)
        expected_total = sum(matrix[label].values())
        metrics[label] = {
            "precision": true_positive / predicted_total if predicted_total else 0.0,
            "recall": true_positive / expected_total if expected_total else 0.0,
        }
    total_elapsed = sum(elapsed)
    return {
        "sampleCount": len(rows),
        "labels": labels,
        "confusionMatrix": matrix,
        "perClass": metrics,
        "meanLatencyMs": sum(latencies) / len(latencies) if latencies else None,
        "fps": len(rows) / total_elapsed if total_elapsed > 0 else None,
        "requiresModelEscalation": any(
            metric["precision"] < 0.85 or metric["recall"] < 0.85
            for metric in metrics.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl")
    parser.add_argument("--output")
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in Path(args.jsonl).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = evaluate_records(records)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
