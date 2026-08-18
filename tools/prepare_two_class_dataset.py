"""Build a 2-class YOLO dataset (healthy + panama) from newdata/ exports.

Label Studio YOLO folders in newdata/Healthy and newdata/Panama share many of
the same DJI photos. This script:

  * keeps only healthy and panama boxes (drops black_sigatoka / bunchy_top)
  * de-duplicates by DJI stem + image size
  * unions boxes from all exports of the same photo
  * NMS-merges overlapping same-class boxes
  * if a healthy box overlaps a panama box, keeps panama
  * writes an 80/10/10 train/val/test split

Usage:
    python tools/prepare_two_class_dataset.py
    python tools/prepare_two_class_dataset.py --source newdata --output datasets/yolo_healthy_panama
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
STEM_RE = re.compile(r"(DJI_\d+)", re.IGNORECASE)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SOURCE_NAMES = ["black_sigatoka", "bunchy_top", "healthy", "panama"]
KEEP_NAMES = ["healthy", "panama"]
SPLITS = ("train", "val", "test")


def canonical_stem(filename: str) -> str:
    match = STEM_RE.search(filename)
    if match:
        return match.group(1).upper()
    stem = Path(filename).stem
    if "-" in stem:
        return stem.split("-", 1)[1]
    return stem


def parse_boxes(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    boxes: list[tuple[int, float, float, float, float]] = []
    if not label_path.is_file():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        cls = int(float(parts[0]))
        cx, cy, w, h = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
        boxes.append((cls, cx, cy, w, h))
    return boxes


def iou_xywh(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def nms_class(
    boxes: list[tuple[int, float, float, float, float]], iou_thresh: float
) -> list[tuple[int, float, float, float, float]]:
    """Keep the larger box when two same-class boxes overlap."""
    ordered = sorted(boxes, key=lambda b: b[3] * b[4], reverse=True)
    kept: list[tuple[int, float, float, float, float]] = []
    for box in ordered:
        if all(iou_xywh(box[1:], other[1:]) < iou_thresh for other in kept):
            kept.append(box)
    return kept


def resolve_conflicts(
    boxes: list[tuple[int, float, float, float, float]], iou_thresh: float
) -> tuple[list[tuple[int, float, float, float, float]], int]:
    """If healthy overlaps panama, keep panama (disease takes priority)."""
    healthy = [b for b in boxes if b[0] == 0]
    panama = [b for b in boxes if b[0] == 1]
    kept_healthy: list[tuple[int, float, float, float, float]] = []
    dropped = 0
    for hbox in healthy:
        if any(iou_xywh(hbox[1:], pbox[1:]) >= iou_thresh for pbox in panama):
            dropped += 1
            continue
        kept_healthy.append(hbox)
    return kept_healthy + panama, dropped


def collect_groups(source: Path) -> dict[tuple[str, int, int], dict]:
    """Group labeled images by (DJI stem, width, height)."""
    groups: dict[tuple[str, int, int], dict] = {}
    exports = sorted(p for p in source.glob("*/*") if p.is_dir() and (p / "images").is_dir())
    if not exports:
        raise SystemExit(f"No Label Studio export folders found under {source}")

    src_to_keep = {SOURCE_NAMES.index(name): KEEP_NAMES.index(name) for name in KEEP_NAMES}

    for export in exports:
        img_dir = export / "images"
        lbl_dir = export / "labels"
        for img in img_dir.iterdir():
            if not img.is_file() or img.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            with Image.open(img) as im:
                width, height = im.size
            key = (canonical_stem(img.name), width, height)
            entry = groups.setdefault(
                key,
                {"image": img, "bytes": img.stat().st_size, "boxes": []},
            )
            if img.stat().st_size > entry["bytes"]:
                entry["image"] = img
                entry["bytes"] = img.stat().st_size
            for cls, cx, cy, w, h in parse_boxes(lbl_dir / f"{img.stem}.txt"):
                if cls not in src_to_keep:
                    continue
                entry["boxes"].append((src_to_keep[cls], cx, cy, w, h))
    return groups


def split_for_key(key: str, train_ratio: float, val_ratio: float) -> str:
    bucket = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def write_data_yaml(dataset: Path) -> None:
    (dataset / "data.yaml").write_text(
        "\n".join(
            [
                f"path: {dataset.resolve().as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "names:",
                *[f"  {idx}: {name}" for idx, name in enumerate(KEEP_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )


def prepare(
    source: Path,
    output: Path,
    train_ratio: float,
    val_ratio: float,
    nms_iou: float,
) -> None:
    groups = collect_groups(source)
    samples: list[tuple[str, Path, list[tuple[int, float, float, float, float]]]] = []
    dropped_empty = 0
    conflict_drops = 0
    box_counts = {name: 0 for name in KEEP_NAMES}

    for (stem, width, height), entry in groups.items():
        boxes = nms_class(entry["boxes"], nms_iou)
        boxes, dropped = resolve_conflicts(boxes, nms_iou)
        conflict_drops += dropped
        if not boxes:
            dropped_empty += 1
            continue
        samples.append((f"{stem}_{width}x{height}", entry["image"], boxes))
        for cls, *_ in boxes:
            box_counts[KEEP_NAMES[cls]] += 1

    if not samples:
        raise SystemExit("No healthy/panama labeled images found.")

    if output.exists():
        shutil.rmtree(output)
    for split in SPLITS:
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)

    counts = {split: 0 for split in SPLITS}
    split_boxes = {split: {name: 0 for name in KEEP_NAMES} for split in SPLITS}
    for key, img, boxes in samples:
        split = split_for_key(key, train_ratio, val_ratio)
        dest_img = output / "images" / split / img.name
        dest_lbl = output / "labels" / split / f"{img.stem}.txt"
        shutil.copy2(img, dest_img)
        dest_lbl.write_text(
            "".join(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n" for cls, cx, cy, w, h in boxes),
            encoding="utf-8",
        )
        counts[split] += 1
        for cls, *_ in boxes:
            split_boxes[split][KEEP_NAMES[cls]] += 1

    write_data_yaml(output)
    total = sum(counts.values())
    print(f"Prepared {total} unique images under {output}")
    print(f"  skipped empty after filter: {dropped_empty}")
    print(f"  healthy boxes dropped (overlapped panama): {conflict_drops}")
    print(f"  boxes: {box_counts}")
    for split in SPLITS:
        pct = 100.0 * counts[split] / total if total else 0
        print(f"  {split}: {counts[split]} images ({pct:.1f}%)  boxes={split_boxes[split]}")
    print(f"Updated {output / 'data.yaml'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "newdata")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets" / "yolo_healthy_panama")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--nms-iou", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise SystemExit(f"Source folder not found: {source}")
    if args.train_ratio + args.val_ratio >= 1.0:
        raise SystemExit("train-ratio + val-ratio must be less than 1.0")
    prepare(source, output, args.train_ratio, args.val_ratio, args.nms_iou)


if __name__ == "__main__":
    main()
