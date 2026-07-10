"""Oversample under-represented classes in the YOLO train split.

Copies training images (and labels) that contain rare disease classes so the
model sees them more often per epoch. Does not touch val/test.

Usage:
    python tools/balance_yolo_dataset.py --dataset datasets/yolo_banana
    python tools/balance_yolo_dataset.py --dataset datasets/yolo_banana --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Target copies per image stem (1 = keep once only).
DEFAULT_BOOST = {
    0: 3,  # black_sigatoka
    1: 8,  # bunchy_top
    2: 1,  # healthy
    3: 3,  # panama
}


def classes_in_label(label_path: Path) -> set[int]:
    out: set[int] = set()
    if not label_path.is_file():
        return out
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.add(int(line.split()[0]))
    return out


def balance_train_split(dataset: Path, boost: dict[int, int], dry_run: bool) -> None:
    img_dir = dataset / "images" / "train"
    lbl_dir = dataset / "labels" / "train"
    if not img_dir.is_dir():
        raise SystemExit(f"Missing {img_dir}")

    added = 0
    for img in sorted(img_dir.glob("*.*")):
        if "_bal" in img.stem:
            continue
        lbl = lbl_dir / f"{img.stem}.txt"
        classes = classes_in_label(lbl)
        if not classes:
            continue
        copies = max(boost.get(cid, 1) for cid in classes)
        for n in range(1, copies):
            stem = f"{img.stem}_bal{n}"
            out_img = img_dir / f"{stem}{img.suffix}"
            out_lbl = lbl_dir / f"{stem}.txt"
            if out_img.exists():
                continue
            if dry_run:
                print(f"would add {out_img.name} (classes {sorted(classes)})")
            else:
                shutil.copy2(img, out_img)
                shutil.copy2(lbl, out_lbl)
            added += 1

    cache = lbl_dir.parent / "train.cache"
    if not dry_run and cache.is_file():
        cache.unlink()

    total = len(list(img_dir.glob("*.*")))
    print(f"Train images now: {total} ({'dry-run' if dry_run else f'+{added} balanced copies'})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "yolo_banana")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    balance_train_split(args.dataset.resolve(), DEFAULT_BOOST, args.dry_run)


if __name__ == "__main__":
    main()
