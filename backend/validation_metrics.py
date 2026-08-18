"""Held-out validation metrics for YOLOv8 banana disease detection."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

try:
    import torch
except ImportError:
    torch = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "datasets" / "yolo_banana"
DEFAULT_WEIGHTS = ROOT / "models" / "best.pt"
DEFAULT_OUT = ROOT / "output" / "metrics"
SPLITS = ("train", "val", "test")


def f1_score(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def default_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def load_class_names(dataset_dir: Path) -> list[str]:
    data_yaml = dataset_dir / "data.yaml"
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Missing dataset config: {data_yaml}")

    raw = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = raw.get("names")
    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=lambda x: int(x))]
    if isinstance(names, list):
        return list(names)
    raise ValueError(f"Unsupported names format in {data_yaml}")


def resolve_data_yaml(dataset_dir: Path, *, cache_dir: Path | None = None) -> Path:
    """Write a data.yaml with an absolute dataset path (portable across machines)."""
    dataset_dir = dataset_dir.resolve()
    for split in SPLITS:
        images = dataset_dir / "images" / split
        labels = dataset_dir / "labels" / split
        if not images.is_dir() or not labels.is_dir():
            raise FileNotFoundError(
                f"Incomplete dataset under {dataset_dir} (missing images/{split} or labels/{split})"
            )

    class_names = load_class_names(dataset_dir)
    out_dir = (cache_dir or DEFAULT_OUT).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = out_dir / "_resolved_data.yaml"
    lines = [
        f"path: {dataset_dir.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
        *[f"  {idx}: {name}" for idx, name in enumerate(class_names)],
        "",
    ]
    resolved.write_text("\n".join(lines), encoding="utf-8")
    return resolved


def split_dataset_stats(dataset_dir: Path, split: str) -> dict[str, Any]:
    """Count images and bounding boxes per class for one split."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")

    class_names = load_class_names(dataset_dir)
    images_dir = dataset_dir / "images" / split
    labels_dir = dataset_dir / "labels" / split

    instances_by_class = {name: 0 for name in class_names}
    images_with_class = {name: 0 for name in class_names}
    image_count = 0
    instance_count = 0

    for img_path in sorted(images_dir.iterdir()):
        if not img_path.is_file():
            continue
        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.is_file():
            continue

        image_count += 1
        seen_classes: set[int] = set()
        for line in label_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            class_id = int(float(parts[0]))
            if class_id < 0 or class_id >= len(class_names):
                continue
            instance_count += 1
            name = class_names[class_id]
            instances_by_class[name] += 1
            seen_classes.add(class_id)

        for class_id in seen_classes:
            images_with_class[class_names[class_id]] += 1

    return {
        "split": split,
        "images": image_count,
        "instances": instance_count,
        "instances_by_class": instances_by_class,
        "images_with_class": images_with_class,
        "class_names": class_names,
    }


def _class_metric_values(box: Any, class_id: int) -> tuple[float, float, float, float]:
    """Return (precision, recall, mAP50, mAP50-95) for one class id."""
    ap_index = getattr(box, "ap_class_index", None)
    if ap_index is not None:
        lookup = {int(class_idx): pos for pos, class_idx in enumerate(ap_index)}
        if class_id in lookup:
            pos = lookup[class_id]
            return (
                float(box.p[pos]),
                float(box.r[pos]),
                float(box.ap50[pos]),
                float(box.ap[pos]),
            )

    # Class absent from ground truth for this split — report zeros.
    return 0.0, 0.0, 0.0, 0.0


def _extract_per_class_metrics(metrics: Any, class_names: list[str]) -> list[dict[str, Any]]:
    box = metrics.box
    rows: list[dict[str, Any]] = []
    for class_id, name in enumerate(class_names):
        precision, recall, map50, map50_95 = _class_metric_values(box, class_id)
        rows.append(
            {
                "class_id": class_id,
                "name": name,
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1": round(f1_score(float(precision), float(recall)), 4),
                "mAP50": round(float(map50), 4),
                "mAP50_95": round(float(map50_95), 4),
            }
        )
    return rows


def _extract_overall_metrics(metrics: Any) -> dict[str, float]:
    box = metrics.box
    precision = float(box.mp)
    recall = float(box.mr)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1_score(precision, recall), 4),
        "mAP50": round(float(box.map50), 4),
        "mAP50_95": round(float(box.map), 4),
    }


def run_validation(
    *,
    weights: Path | str = DEFAULT_WEIGHTS,
    dataset_dir: Path | str = DEFAULT_DATASET,
    split: Literal["train", "val", "test"] = "test",
    imgsz: int = 640,
    batch: int = 8,
    device: str | None = None,
    workers: int = 0,
    plots: bool = True,
    project: Path | str | None = None,
    name: str = "eval",
) -> dict[str, Any]:
    """Run Ultralytics validation on a held-out split and return a structured report."""
    from ultralytics import YOLO

    dataset_dir = Path(dataset_dir).resolve()
    weights = Path(weights).resolve()
    if not weights.is_file():
        raise FileNotFoundError(f"Missing weights: {weights}")

    data_yaml = resolve_data_yaml(dataset_dir)
    class_names = load_class_names(dataset_dir)
    dataset_stats = split_dataset_stats(dataset_dir, split)

    run_project = Path(project).resolve() if project else (DEFAULT_OUT / "runs")
    run_project.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(weights))
    metrics = model.val(
        data=str(data_yaml),
        split=split,
        imgsz=imgsz,
        batch=batch,
        device=device or default_device(),
        workers=workers,
        verbose=False,
        plots=plots,
        project=str(run_project),
        name=name,
        exist_ok=True,
    )

    per_class = _extract_per_class_metrics(metrics, class_names)
    for row in per_class:
        name_key = row["name"]
        row["instances_in_split"] = dataset_stats["instances_by_class"].get(name_key, 0)
        row["images_with_class"] = dataset_stats["images_with_class"].get(name_key, 0)

    speed = getattr(metrics, "speed", {}) or {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "AgriVision",
        "split": split,
        "weights": str(weights.relative_to(ROOT)) if weights.is_relative_to(ROOT) else str(weights),
        "dataset": str(dataset_dir.relative_to(ROOT)) if dataset_dir.is_relative_to(ROOT) else str(dataset_dir),
        "data_yaml": str(data_yaml.relative_to(ROOT)) if data_yaml.is_relative_to(ROOT) else str(data_yaml),
        "hyperparameters": {
            "imgsz": imgsz,
            "batch": batch,
            "device": device or default_device(),
            "workers": workers,
        },
        "dataset_stats": dataset_stats,
        "overall": _extract_overall_metrics(metrics),
        "per_class": per_class,
        "speed_ms_per_image": {
            key.replace("_ms", ""): round(float(value), 3)
            for key, value in speed.items()
            if isinstance(value, (int, float))
        },
        "ultralytics": {
            "save_dir": str(getattr(metrics, "save_dir", "")),
            "results_dict": {
                k: float(v) if isinstance(v, (int, float)) else v
                for k, v in getattr(metrics, "results_dict", {}).items()
                if k.startswith("metrics/")
            },
        },
    }


def build_markdown_report(report: dict[str, Any]) -> str:
    split = report["split"].upper()
    overall = report["overall"]
    stats = report["dataset_stats"]
    lines = [
        f"# AgriVision — {split} Set Validation Report",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**Weights:** `{report['weights']}`  ",
        f"**Dataset:** `{report['dataset']}`  ",
        f"**Split:** {report['split']} ({stats['images']} images, {stats['instances']} instances)",
        "",
        "## Overall metrics",
        "",
        "| Precision | Recall | F1-Score | mAP@0.5 | mAP@0.5:0.95 |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {overall['precision']:.3f} | {overall['recall']:.3f} | {overall['f1']:.3f} | "
            f"{overall['mAP50']:.3f} | {overall['mAP50_95']:.3f} |"
        ),
        "",
        f"## Per-class metrics ({split.lower()} set)",
        "",
        "| Class | Images | Instances | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in report["per_class"]:
        lines.append(
            f"| `{row['name']}` | {row['images_with_class']} | {row['instances_in_split']} | "
            f"{row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} | "
            f"{row['mAP50']:.3f} | {row['mAP50_95']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Dataset composition (held-out split)",
            "",
            "| Class | Images containing class | Bounding boxes |",
            "|---|---:|---:|",
        ]
    )
    for name in stats["class_names"]:
        lines.append(
            f"| `{name}` | {stats['images_with_class'][name]} | {stats['instances_by_class'][name]} |"
        )

    lines.extend(
        [
            "",
            "*Regenerate with `python tools/evaluate_test_set.py` or "
            "`python tools/evaluate_test_set.py --split val`.*",
            "",
        ]
    )
    return "\n".join(lines)


def write_validation_report(
    report: dict[str, Any],
    *,
    out_dir: Path | str = DEFAULT_OUT,
    basename: str | None = None,
) -> dict[str, Path]:
    """Write JSON, CSV, and Markdown reports; update `*_latest.*` aliases."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    split = report["split"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = basename or f"{split}_report_{stamp}"

    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "class",
                "class_id",
                "images_with_class",
                "instances_in_split",
                "precision",
                "recall",
                "f1",
                "mAP50",
                "mAP50_95",
            ]
        )
        for row in report["per_class"]:
            writer.writerow(
                [
                    row["name"],
                    row["class_id"],
                    row["images_with_class"],
                    row["instances_in_split"],
                    row["precision"],
                    row["recall"],
                    row["f1"],
                    row["mAP50"],
                    row["mAP50_95"],
                ]
            )
        writer.writerow([])
        overall = report["overall"]
        writer.writerow(
            [
                "ALL",
                "",
                report["dataset_stats"]["images"],
                report["dataset_stats"]["instances"],
                overall["precision"],
                overall["recall"],
                overall["f1"],
                overall["mAP50"],
                overall["mAP50_95"],
            ]
        )

    md_path.write_text(build_markdown_report(report), encoding="utf-8")

    latest = {
        "json": out_dir / f"{split}_report_latest.json",
        "csv": out_dir / f"{split}_report_latest.csv",
        "md": out_dir / f"{split}_report_latest.md",
    }
    for key, src in (("json", json_path), ("csv", csv_path), ("md", md_path)):
        shutil.copy2(src, latest[key])

    artifacts = {"json": json_path, "csv": csv_path, "markdown": md_path, **latest}
    report["artifacts"] = {
        k: str(v.relative_to(ROOT)) if v.is_relative_to(ROOT) else str(v) for k, v in artifacts.items()
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    shutil.copy2(json_path, latest["json"])

    return artifacts


def evaluate_and_export(
    *,
    weights: Path | str = DEFAULT_WEIGHTS,
    dataset_dir: Path | str = DEFAULT_DATASET,
    split: Literal["train", "val", "test"] = "test",
    out_dir: Path | str = DEFAULT_OUT,
    imgsz: int = 640,
    batch: int = 8,
    device: str | None = None,
    workers: int = 0,
    plots: bool = True,
) -> dict[str, Any]:
    """Run validation and write all report artifacts."""
    report = run_validation(
        weights=weights,
        dataset_dir=dataset_dir,
        split=split,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=workers,
        plots=plots,
        project=Path(out_dir) / "runs",
        name=f"{split}_eval",
    )
    paths = write_validation_report(report, out_dir=out_dir)
    report["artifact_paths"] = {k: str(v) for k, v in paths.items()}
    return report
