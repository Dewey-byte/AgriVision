"""Merge Label Studio YOLO exports into AgriVision's datasets/yolo_banana layout.

Label Studio "YOLO" export produces, per project export:
    <export>/images/*.jpg
    <export>/labels/*.txt
    <export>/classes.txt

This script merges one or more such export folders, performs a train/val split,
and writes datasets/yolo_banana/{images,labels}/{train,val} + data.yaml.

Usage:
    python tools/prepare_label_studio.py ^
      --input "C:/Users/<you>/Downloads/project-2-at-A" ^
              "C:/Users/<you>/Downloads/project-2-at-B" ^
      --output datasets/yolo_banana ^
      --val-ratio 0.2
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _read_classes(input_dirs: list[Path]) -> list[str]:
    """Read classes.txt from the inputs and ensure they all agree."""
    class_lists: list[list[str]] = []
    for d in input_dirs:
        cls_file = d / "classes.txt"
        if not cls_file.is_file():
            raise FileNotFoundError(f"Missing classes.txt in {d}")
        names = [ln.strip() for ln in cls_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        class_lists.append(names)

    first = class_lists[0]
    for d, names in zip(input_dirs[1:], class_lists[1:]):
        if names != first:
            raise ValueError(
                f"class mismatch:\n  {input_dirs[0].name}: {first}\n  {d.name}: {names}\n"
                "All exports must share the same classes.txt ordering."
            )
    return first


def _collect_pairs(input_dirs: list[Path]) -> list[tuple[Path, Path]]:
    """Return (image, label) path pairs across all input export folders."""
    pairs: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for d in input_dirs:
        img_dir = d / "images"
        lbl_dir = d / "labels"
        if not img_dir.is_dir() or not lbl_dir.is_dir():
            raise FileNotFoundError(f"{d} must contain images/ and labels/ subfolders")

        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label = lbl_dir / f"{img.stem}.txt"
            if not label.is_file():
                print(f"  ! skip (no label): {img.name}")
                continue
            if img.name in seen:
                print(f"  ! skip (duplicate name): {img.name}")
                continue
            seen.add(img.name)
            pairs.append((img, label))
    return pairs


def prepare(input_dirs: list[Path], output: Path, val_ratio: float, seed: int) -> Path:
    classes = _read_classes(input_dirs)
    pairs = _collect_pairs(input_dirs)
    if not pairs:
        raise RuntimeError("No image/label pairs found in the given inputs.")

    rng = random.Random(seed)
    rng.shuffle(pairs)
    val_count = max(1, int(round(len(pairs) * val_ratio)))
    val_pairs = pairs[:val_count]
    train_pairs = pairs[val_count:]

    if output.exists():
        shutil.rmtree(output)
    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)

    for split, split_pairs in (("train", train_pairs), ("val", val_pairs)):
        for img, label in split_pairs:
            shutil.copy2(img, output / "images" / split / img.name)
            shutil.copy2(label, output / "labels" / split / f"{img.stem}.txt")

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {output.resolve().as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                *[f"  {i}: {name}" for i, name in enumerate(classes)],
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(
        f"Prepared {len(train_pairs)} train / {len(val_pairs)} val images "
        f"across {len(classes)} classes: {classes}"
    )
    print(f"data.yaml -> {data_yaml}")
    return data_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", required=True, help="Label Studio YOLO export folder(s)")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets" / "yolo_banana")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dirs = [Path(p).resolve() for p in args.input]
    for d in input_dirs:
        if not d.is_dir():
            raise FileNotFoundError(f"Input folder not found: {d}")
    prepare(input_dirs, args.output.resolve(), args.val_ratio, args.seed)


if __name__ == "__main__":
    main()
