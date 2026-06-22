"""Batch-label aerial DJI images in datasets/inbox using grid + classifier.

Each green grid cell becomes one YOLO box with a disease class.

Usage:
  python tools/batch_label_inbox.py --input datasets/inbox
  python tools/batch_label_inbox.py --input datasets/inbox --export datasets/yolo_banana
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.classification import run_classification_crop
from utils.drawing import detection_category, draw_boxes
from utils.frame_quality import frame_green_ratio

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}
CLASS_TO_ID = {
    "black_sigatoka": 0,
    "healthy": 1,
    "moko": 2,
    "panama": 3,
}


SKIP_DIR_NAMES = {"labels", "preview", "__pycache__"}


def _list_images(folder: Path, recursive: bool = True) -> list[Path]:
    out = []
    if recursive:
        paths = sorted(folder.rglob("*"))
    else:
        paths = sorted(folder.iterdir())
    for p in paths:
        if not p.is_file() or p.suffix not in IMAGE_SUFFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(folder).parts[:-1]):
            continue
        out.append(p)
    return out


def _label_path(label_dir: Path, image_path: Path) -> Path:
    return label_dir / f"{image_path.stem}.txt"


def _grid_label_image(frame, grid: int, min_green: float, min_conf: float) -> list[dict]:
    h, w = frame.shape[:2]
    boxes: list[dict] = []
    for row in range(grid):
        for col in range(grid):
            y1 = int(row * h / grid)
            y2 = int((row + 1) * h / grid)
            x1 = int(col * w / grid)
            x2 = int((col + 1) * w / grid)
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            if frame_green_ratio(crop) < min_green:
                continue
            try:
                cls = run_classification_crop(crop)
            except Exception:
                continue
            if cls.get("skip"):
                continue
            conf = float(cls.get("confidence", 0.0))
            if conf < min_conf:
                continue
            label = cls.get("display", cls.get("label", "plant"))
            if detection_category(str(label)) == "none":
                continue
            boxes.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": CLASS_TO_ID.get(str(cls.get("label", "")).lower(), 1),
                    "label": f"{label} ({conf:.2f})",
                }
            )
    return boxes


def _save_yolo(path: Path, boxes: list[dict], w: int, h: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for b in boxes:
        x1, y1, x2, y2 = b["bbox"]
        cid = b.get("class_id", 1)
        cx = ((x1 + x2) / 2.0) / w
        cy = ((y1 + y2) / 2.0) / h
        bw = abs(x2 - x1) / w
        bh = abs(y2 - y1) / h
        lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _export_yolo(
    images: list[Path],
    label_dir: Path,
    export_root: Path,
    val_ratio: float,
    seed: int,
) -> None:
    rng = random.Random(seed)
    shuffled = images[:]
    rng.shuffle(shuffled)
    val_n = max(1, int(round(len(shuffled) * val_ratio)))
    val_set = set(shuffled[:val_n])

    for img in images:
        split = "val" if img in val_set else "train"
        dst_img = export_root / "images" / split / img.name
        dst_lbl = export_root / "labels" / split / f"{img.stem}.txt"
        dst_img.parent.mkdir(parents=True, exist_ok=True)
        dst_lbl.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, dst_img)
        lbl = _label_path(label_dir, img)
        if lbl.is_file():
            shutil.copy2(lbl, dst_lbl)
        else:
            dst_lbl.write_text("", encoding="utf-8")

    data_yaml = export_root / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {export_root.as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: black_sigatoka",
                "  1: healthy",
                "  2: moko",
                "  3: panama",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets" / "inbox")
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only label images directly in --input (not subfolders)",
    )
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--preview", type=Path, default=None)
    parser.add_argument("--grid", type=int, default=6)
    parser.add_argument("--min-green", type=float, default=0.12)
    parser.add_argument("--min-conf", type=float, default=0.50)
    parser.add_argument("--limit", type=int, default=0, help="Process first N images only (0=all)")
    parser.add_argument("--export", type=Path, default=None, help="Copy to YOLO train/val layout")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    args = parser.parse_args()

    image_dir = args.input.resolve()
    label_dir = (args.labels or image_dir / "labels").resolve()
    preview_dir = (args.preview or image_dir / "preview").resolve()
    preview_dir.mkdir(parents=True, exist_ok=True)

    images = _list_images(image_dir, recursive=not args.no_recursive)
    if args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No images in {image_dir}")

    total_boxes = 0
    labeled_images = 0

    for i, img_path in enumerate(images, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[{i}/{len(images)}] skip unreadable: {img_path.name}")
            continue
        h, w = frame.shape[:2]
        boxes = _grid_label_image(frame, args.grid, args.min_green, args.min_conf)
        _save_yolo(_label_path(label_dir, img_path), boxes, w, h)
        if boxes:
            labeled_images += 1
            total_boxes += len(boxes)
            prev = draw_boxes(frame.copy(), boxes)
            thumb_max = 1280
            if w > thumb_max:
                scale = thumb_max / w
                prev = cv2.resize(prev, (thumb_max, max(1, int(h * scale))))
            cv2.imwrite(str(preview_dir / img_path.name), prev)
        if i % 10 == 0 or i == len(images):
            print(f"[{i}/{len(images)}] {img_path.name}: {len(boxes)} boxes")

    print(f"Done. {labeled_images}/{len(images)} images labeled, {total_boxes} total boxes.")
    print(f"Labels: {label_dir}")
    print(f"Previews: {preview_dir}")
    print("Review/fix: python tools/label_yolo.py --input", image_dir)

    if args.export:
        _export_yolo(images, label_dir, args.export.resolve(), args.val_ratio, 42)
        print(f"Exported YOLO dataset: {args.export}")


if __name__ == "__main__":
    main()
