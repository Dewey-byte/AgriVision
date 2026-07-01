"""Merge Label Studio YOLO-format zip export(s) into datasets/yolo_banana.

Label Studio's "YOLO" export is a zip containing:
    images/<hash>-DJI_XXXX.JPG
    labels/<hash>-DJI_XXXX.txt
    classes.txt
    notes.json

Each export uses a fresh <hash> prefix, so the same photo re-exported gets a new
filename. This tool de-duplicates by the *original* DJI stem (e.g. ``DJI_0257``):

  * If the stem already exists in the dataset, its image + label are replaced
    in-place (kept in whatever train/val split it was already in -> no leakage).
  * New stems are split into train/val deterministically by the requested ratio.

Usage:
    python tools/merge_yolo_export.py \
        --zip "C:/Users/me/Downloads/project-2-....zip" \
        --zip "C:/Users/me/Downloads/project-3-....zip" \
        --dataset datasets/yolo_banana \
        --val-ratio 0.2
"""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEM_RE = re.compile(r"(DJI_\d+)", re.IGNORECASE)


def canonical_stem(filename: str) -> str:
    """Original photo key, ignoring the Label Studio hash prefix and extension."""
    name = Path(filename).name
    match = STEM_RE.search(name)
    if match:
        return match.group(1).upper()
    stem = Path(name).stem
    # Fallback: drop a leading "<hash>-" prefix if present.
    if "-" in stem:
        return stem.split("-", 1)[1]
    return stem


def index_existing(dataset: Path) -> dict[str, dict[str, object]]:
    """Map canonical stem -> {split, image, label} for the current dataset."""
    index: dict[str, dict[str, object]] = {}
    for split in ("train", "val", "test"):
        img_dir = dataset / "images" / split
        if not img_dir.is_dir():
            continue
        for img in img_dir.iterdir():
            if not img.is_file():
                continue
            key = canonical_stem(img.name)
            label = dataset / "labels" / split / f"{img.stem}.txt"
            index[key] = {"split": split, "image": img, "label": label}
    return index


def collect_from_zip(zip_path: Path) -> dict[str, dict[str, object]]:
    """Map canonical stem -> {name, image_bytes, ext, label_text} from one zip."""
    items: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        images = [n for n in names if n.startswith("images/") and not n.endswith("/")]
        label_by_stem: dict[str, str] = {}
        for n in names:
            if n.startswith("labels/") and n.endswith(".txt"):
                label_by_stem[Path(n).stem] = n

        for img_name in images:
            img_stem = Path(img_name).stem
            label_name = label_by_stem.get(img_stem)
            if label_name is None:
                # Image with no annotations -> skip (no boxes to learn from).
                continue
            key = canonical_stem(img_name)
            items[key] = {
                "name": Path(img_name).name,
                "image_bytes": zf.read(img_name),
                "ext": Path(img_name).suffix.lower(),
                "label_text": zf.read(label_name).decode("utf-8"),
            }
    return items


def split_for_new_key(key: str, train_ratio: float = 0.8, val_ratio: float = 0.1) -> str:
    """Deterministic train/val/test assignment (default 80-10-10 buckets)."""
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def write_pair(
    dataset: Path,
    split: str,
    name: str,
    ext: str,
    image_bytes: bytes,
    label_text: str,
) -> None:
    stem = Path(name).stem
    img_out = dataset / "images" / split / f"{stem}{ext}"
    lbl_out = dataset / "labels" / split / f"{stem}.txt"
    img_out.parent.mkdir(parents=True, exist_ok=True)
    lbl_out.parent.mkdir(parents=True, exist_ok=True)
    img_out.write_bytes(image_bytes)
    if not label_text.endswith("\n"):
        label_text += "\n"
    lbl_out.write_text(label_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", dest="zips", action="append", required=True, type=Path)
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "yolo_banana")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    existing = index_existing(dataset)
    print(f"Existing dataset: {len(existing)} unique photos")

    # Collect new items; later zips win on intra-batch duplicate stems.
    incoming: dict[str, dict[str, object]] = {}
    for zip_path in args.zips:
        zp = zip_path.resolve()
        if not zp.is_file():
            raise FileNotFoundError(f"Zip not found: {zp}")
        found = collect_from_zip(zp)
        print(f"  {zp.name}: {len(found)} labeled photos")
        incoming.update(found)

    updated = added_train = added_val = added_test = 0
    for key, item in incoming.items():
        if key in existing:
            split = str(existing[key]["split"])
            old_img = existing[key]["image"]
            old_lbl = existing[key]["label"]
            if isinstance(old_img, Path) and old_img.is_file():
                old_img.unlink()
            if isinstance(old_lbl, Path) and old_lbl.is_file():
                old_lbl.unlink()
            updated += 1
        else:
            split = split_for_new_key(key, args.train_ratio, args.val_ratio)
            if split == "val":
                added_val += 1
            elif split == "test":
                added_test += 1
            else:
                added_train += 1

        write_pair(
            dataset,
            split,
            str(item["name"]),
            str(item["ext"]),
            item["image_bytes"],  # type: ignore[arg-type]
            str(item["label_text"]),
        )

    n_train = len(list((dataset / "images" / "train").glob("*.*")))
    n_val = len(list((dataset / "images" / "val").glob("*.*")))
    n_test = len(list((dataset / "images" / "test").glob("*.*")))
    print("\nMerge complete:")
    print(f"  updated (replaced existing): {updated}")
    print(f"  added new -> train: {added_train}, val: {added_val}, test: {added_test}")
    print(f"  dataset now: {n_train} train, {n_val} val, {n_test} test ({n_train + n_val + n_test} total)")


if __name__ == "__main__":
    main()
