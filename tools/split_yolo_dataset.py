"""Repartition a YOLO dataset into train / val / test splits.

Default partition: 80-10-10 (deterministic by image stem hash).

Usage:
    python tools/split_yolo_dataset.py --dataset datasets/yolo_banana
    python tools/split_yolo_dataset.py --train-ratio 0.8 --val-ratio 0.1
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "val", "test")
CLASS_NAMES = ["black_sigatoka", "bunchy_top", "healthy", "panama"]


def assign_split(key: str, train_ratio: float, val_ratio: float) -> str:
  """Deterministic split from stem hash."""
  bucket = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
  if bucket < train_ratio:
    return "train"
  if bucket < train_ratio + val_ratio:
    return "val"
  return "test"


def collect_pairs(dataset: Path) -> list[tuple[str, Path, Path]]:
  """Return (stem, image_path, label_path) for every labeled image."""
  pairs: dict[str, tuple[Path, Path]] = {}
  for split in SPLITS:
    img_dir = dataset / "images" / split
    if not img_dir.is_dir():
      continue
    for img in img_dir.iterdir():
      if not img.is_file():
        continue
      lbl = dataset / "labels" / split / f"{img.stem}.txt"
      if not lbl.is_file():
        continue
      pairs[img.stem] = (img, lbl)
  return [(stem, img, lbl) for stem, (img, lbl) in pairs.items()]


def write_data_yaml(dataset: Path) -> None:
  yaml_path = dataset / "data.yaml"
  yaml_path.write_text(
    "\n".join(
      [
        f"path: {dataset.resolve().as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
        *[f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES)],
        "",
      ]
    ),
    encoding="utf-8",
  )


def repartition(dataset: Path, train_ratio: float, val_ratio: float) -> dict[str, int]:
    pairs = collect_pairs(dataset)
    if not pairs:
        raise SystemExit(f"No labeled images found under {dataset}")

    n = len(pairs)
    n_train = int(round(n * train_ratio))
    n_val = int(round(n * val_ratio))
    n_test = n - n_train - n_val
    if n_test < 0:
        raise SystemExit("train-ratio + val-ratio too large for dataset size")

    # Stable order: sort stems by hash so the split is reproducible.
    ordered = sorted(pairs, key=lambda row: hashlib.md5(row[0].encode("utf-8")).hexdigest())
    split_sizes = {"train": n_train, "val": n_val, "test": n_test}

    staging = dataset / "_split_staging"
    if staging.exists():
        shutil.rmtree(staging)
    for split in SPLITS:
        (staging / "images" / split).mkdir(parents=True)
        (staging / "labels" / split).mkdir(parents=True)

    counts = {split: 0 for split in SPLITS}
    idx = 0
    for split in SPLITS:
        for _ in range(split_sizes[split]):
            stem, img, lbl = ordered[idx]
            idx += 1
            dest_img = staging / "images" / split / img.name
            dest_lbl = staging / "labels" / split / lbl.name
            shutil.copy2(img, dest_img)
            shutil.copy2(lbl, dest_lbl)
            counts[split] += 1

    # Replace live split folders.
    for split in SPLITS:
        img_dir = dataset / "images" / split
        lbl_dir = dataset / "labels" / split
        if img_dir.exists():
            shutil.rmtree(img_dir)
        if lbl_dir.exists():
            shutil.rmtree(lbl_dir)
        shutil.move(str(staging / "images" / split), str(img_dir))
        shutil.move(str(staging / "labels" / split), str(lbl_dir))

    shutil.rmtree(staging, ignore_errors=True)

    for cache in (dataset / "labels" / "train.cache", dataset / "labels" / "val.cache"):
        if cache.is_file():
            cache.unlink()

    write_data_yaml(dataset)
    return counts


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "yolo_banana")
  parser.add_argument("--train-ratio", type=float, default=0.8)
  parser.add_argument("--val-ratio", type=float, default=0.1)
  args = parser.parse_args()

  test_ratio = 1.0 - args.train_ratio - args.val_ratio
  if test_ratio <= 0:
    raise SystemExit("train-ratio + val-ratio must be less than 1.0")

  dataset = args.dataset.resolve()
  counts = repartition(dataset, args.train_ratio, args.val_ratio)
  total = sum(counts.values())
  print(f"Repartitioned {total} images under {dataset}")
  for split in SPLITS:
    pct = 100.0 * counts[split] / total
    print(f"  {split}: {counts[split]} ({pct:.1f}%)")
  print(f"Updated {dataset / 'data.yaml'}")


if __name__ == "__main__":
  main()
