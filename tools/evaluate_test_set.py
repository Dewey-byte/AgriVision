"""Evaluate YOLOv8 on the held-out test (or val) split and export metrics reports.

Writes:
  - output/metrics/test_report_{timestamp}.json
  - output/metrics/test_report_{timestamp}.csv
  - output/metrics/test_report_{timestamp}.md
  - output/metrics/test_report_latest.{json,csv,md}
  - output/metrics/runs/test_eval/  (Ultralytics plots when --plots)

Usage:
    python tools/evaluate_test_set.py
    python tools/evaluate_test_set.py --split val
    python tools/evaluate_test_set.py --weights models/best.pt --no-plots
    python tools/evaluate_test_set.py --stats-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.validation_metrics import (  # noqa: E402
    DEFAULT_DATASET,
    DEFAULT_OUT,
    DEFAULT_WEIGHTS,
    evaluate_and_export,
    split_dataset_stats,
    write_validation_report,
)


def print_summary(report: dict) -> None:
    split = report["split"]
    stats = report["dataset_stats"]
    overall = report["overall"]
    print(f"\nAgriVision {split} set evaluation")
    print(f"  images:    {stats['images']}")
    print(f"  instances: {stats['instances']}")
    print(
        f"  overall:   P={overall['precision']:.3f}  R={overall['recall']:.3f}  "
        f"F1={overall['f1']:.3f}  mAP50={overall['mAP50']:.3f}  mAP50-95={overall['mAP50_95']:.3f}"
    )
    print("\n  Per class:")
    for row in report["per_class"]:
        print(
            f"    {row['name']:<16}  inst={row['instances_in_split']:>4}  "
            f"P={row['precision']:.3f}  R={row['recall']:.3f}  "
            f"mAP50={row['mAP50']:.3f}"
        )

    artifacts = report.get("artifacts") or report.get("artifact_paths") or {}
    if artifacts:
        print("\n  Artifacts:")
        for key in ("json", "csv", "markdown", "md"):
            if key in artifacts:
                print(f"    {key}: {artifacts[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--split", choices=("train", "val", "test"), default="test")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default=None)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--plots", dest="plots", action="store_true", default=True)
    parser.add_argument("--no-plots", dest="plots", action="store_false")
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Print dataset split statistics without running YOLO validation",
    )
    args = parser.parse_args()

    if args.stats_only:
        stats = split_dataset_stats(args.dataset.resolve(), args.split)
        print(json.dumps(stats, indent=2))
        return 0

    report = evaluate_and_export(
        weights=args.weights,
        dataset_dir=args.dataset,
        split=args.split,
        out_dir=args.out,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        plots=args.plots,
    )
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
