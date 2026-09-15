"""Build a 3-class YOLO-cls dataset from secondary (folder-labeled) ZIPs.

Maps close-range leaf datasets into:
  healthy / panama / black_sigatoka

Does NOT touch the aerial YOLO detection set (datasets/yolo_banana).

Usage:
    python tools/prepare_cls_secondary.py
    python tools/prepare_cls_secondary.py --zip "E:/Users/.../archive (1).zip" --zip "E:/Users/.../archive (2).zip"
"""

from __future__ import annotations

import argparse
import hashlib
import io
import random
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIPS = [
    Path(r"E:\Users\Dewey-Byte\Downloads\archive (1).zip"),
    Path(r"E:\Users\Dewey-Byte\Downloads\archive (2).zip"),
]
CLASS_NAMES = ("healthy", "panama", "black_sigatoka")
SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Folder-name fragments (lowercased) -> class. First match wins.
FOLDER_MAP: list[tuple[str, str]] = [
    ("panama", "panama"),
    ("healthy", "healthy"),
    ("sigatoka", "black_sigatoka"),
]


SKIP_FOLDER_NOISE = (
    "anthracnose",
    "scarring",
    "skipper",
    "split peel",
    "chewing",
    "cordana",
    "insect",
)


def map_class(path_parts: list[str]) -> str | None:
    """Return target class from zip entry path parts, or None to skip."""
    # Ignore filename; map from directory names only.
    dirs = list(path_parts[:-1]) if len(path_parts) > 1 else list(path_parts)
    for part in dirs:
        key = part.lower().replace("_", " ").strip()
        if key in {"train", "test", "val", "images", "labels", "banana", "desktop.ini"}:
            continue
        if any(noise in key for noise in SKIP_FOLDER_NOISE):
            return None
        for needle, cls in FOLDER_MAP:
            if needle in key:
                return cls
    return None


def infer_source_split(path_parts: list[str]) -> str | None:
    for part in path_parts:
        p = part.lower()
        if p in SPLITS:
            return p
    return None


def content_key(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def collect_from_zip(zip_path: Path) -> dict[str, list[tuple[str, bytes, str]]]:
    """class -> list of (content_hash, image_bytes, ext)."""
    by_class: dict[str, list[tuple[str, bytes, str]]] = defaultdict(list)
    seen_hash: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            path = Path(name)
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if path.name.lower() == "desktop.ini":
                continue
            parts = path.parts
            cls = map_class(list(parts))
            if cls is None:
                continue
            data = zf.read(info)
            if len(data) < 1024:
                continue
            # Drop unreadable / corrupt images early.
            try:
                with Image.open(io.BytesIO(data)) as im:
                    im.verify()
            except Exception:
                continue
            h = content_key(data)
            if h in seen_hash:
                continue
            seen_hash.add(h)
            by_class[cls].append((h, data, path.suffix.lower() or ".jpg"))
    return by_class


def assign_split(key: str, train_ratio: float, val_ratio: float) -> str:
    bucket = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def balance_train(
    items: list[tuple[str, bytes, str]],
    target: int,
    rng: random.Random,
) -> list[tuple[str, bytes, str]]:
    """Undersample or oversample (with replacement) to `target` count."""
    if not items:
        return []
    if len(items) >= target:
        return rng.sample(items, target)
    out = list(items)
    while len(out) < target:
        out.append(rng.choice(items))
    return out


def write_dataset(
    by_class: dict[str, list[tuple[str, bytes, str]]],
    output: Path,
    train_ratio: float,
    val_ratio: float,
    balance_to: str,
    seed: int,
) -> None:
    rng = random.Random(seed)
    if output.exists():
        import shutil

        shutil.rmtree(output)
    for split in SPLITS:
        for cls in CLASS_NAMES:
            (output / split / cls).mkdir(parents=True)

    # Split first, then balance train only.
    split_pools: dict[str, dict[str, list[tuple[str, bytes, str]]]] = {
        s: {c: [] for c in CLASS_NAMES} for s in SPLITS
    }
    for cls, items in by_class.items():
        for h, data, ext in items:
            split = assign_split(h, train_ratio, val_ratio)
            split_pools[split][cls].append((h, data, ext))

    counts_before = {c: len(by_class.get(c, [])) for c in CLASS_NAMES}
    print("Collected unique images per class:")
    for c in CLASS_NAMES:
        print(f"  {c}: {counts_before[c]}")

    if balance_to == "min":
        target = min(len(split_pools["train"][c]) for c in CLASS_NAMES)
    elif balance_to == "max":
        target = max(len(split_pools["train"][c]) for c in CLASS_NAMES)
    else:
        target = int(balance_to)
    target = max(1, target)
    print(f"Train balance target per class: {target}")

    written = {s: {c: 0 for c in CLASS_NAMES} for s in SPLITS}
    for cls in CLASS_NAMES:
        train_items = balance_train(split_pools["train"][cls], target, rng)
        pools = {
            "train": train_items,
            "val": split_pools["val"][cls],
            "test": split_pools["test"][cls],
        }
        for split, items in pools.items():
            for i, (h, data, ext) in enumerate(items):
                # Unique filename even when oversampling.
                name = f"{cls}_{h[:10]}_{i}{ext}"
                dest = output / split / cls / name
                dest.write_bytes(data)
                written[split][cls] += 1

    print(f"\nWrote dataset to {output}")
    for split in SPLITS:
        total = sum(written[split].values())
        print(f"  {split}: {total}  {written[split]}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", dest="zips", action="append", type=Path, default=None)
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "datasets" / "cls_healthy_panama_sigatoka",
    )
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--val-ratio", type=float, default=0.1)
    p.add_argument(
        "--balance-to",
        default="min",
        help="'min' = undersample to smallest class, 'max' = oversample to largest, or an int",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    zips = args.zips or DEFAULT_ZIPS
    if args.train_ratio + args.val_ratio >= 1.0:
        raise SystemExit("train-ratio + val-ratio must be < 1.0")

    merged: dict[str, list[tuple[str, bytes, str]]] = defaultdict(list)
    seen: set[str] = set()
    for zp in zips:
        zp = zp.resolve()
        if not zp.is_file():
            raise FileNotFoundError(f"Zip not found: {zp}")
        print(f"Scanning {zp.name} ...")
        found = collect_from_zip(zp)
        for cls, items in found.items():
            added = 0
            for h, data, ext in items:
                if h in seen:
                    continue
                seen.add(h)
                merged[cls].append((h, data, ext))
                added += 1
            print(f"  +{added} unique -> {cls} (zip had {len(items)})")

    if not any(merged.values()):
        raise SystemExit("No mappable images found in the provided zips.")

    write_dataset(
        merged,
        args.output.resolve(),
        args.train_ratio,
        args.val_ratio,
        str(args.balance_to),
        args.seed,
    )


if __name__ == "__main__":
    main()
