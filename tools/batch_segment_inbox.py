"""Batch semantic segmentation masks for aerial inbox images.

Builds per-pixel class masks (PNG) using vegetation detection + block classifier.

Usage:
  python tools/batch_segment_inbox.py --input datasets/inbox
  python tools/batch_segment_inbox.py --input datasets/inbox --export datasets/seg_banana
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.classification import run_classification_crop
from tools.seg_common import (
    CLASS_TO_MASK,
    export_seg_dataset,
    export_yolo_seg_from_masks,
    list_images,
    mask_path,
    overlay_mask,
    save_mask,
    vegetation_mask,
)
from utils.drawing import detection_category
from utils.frame_quality import frame_green_ratio


def _classify_block(crop: np.ndarray, min_conf: float) -> int:
    if crop.size == 0 or frame_green_ratio(crop) < 0.08:
        return 0
    try:
        cls = run_classification_crop(crop)
    except Exception:
        return 0
    if cls.get("skip"):
        return 0
    conf = float(cls.get("confidence", 0.0))
    if conf < min_conf:
        return 0
    label = str(cls.get("label", "")).lower()
    if detection_category(label) == "none":
        return 0
    return CLASS_TO_MASK.get(label, CLASS_TO_MASK["healthy"])


def segment_image(
    frame: np.ndarray,
    block: int = 64,
    min_conf: float = 0.50,
    smooth: int = 3,
    max_side: int = 1280,
) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        small = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        small_mask = _segment_at_scale(small, block, min_conf, smooth)
        mask = cv2.resize(small_mask, (w, h), interpolation=cv2.INTER_NEAREST)
        veg = vegetation_mask(frame)
        return np.where(veg > 0, mask, 0).astype(np.uint8)
    return _segment_at_scale(frame, block, min_conf, smooth)


def _segment_at_scale(
    frame: np.ndarray,
    block: int,
    min_conf: float,
    smooth: int,
) -> np.ndarray:
    h, w = frame.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    veg = vegetation_mask(frame)

    for y in range(0, h, block):
        y2 = min(h, y + block)
        for x in range(0, w, block):
            x2 = min(w, x + block)
            crop = frame[y:y2, x:x2]
            veg_block = veg[y:y2, x:x2]
            if not np.any(veg_block):
                continue
            class_id = _classify_block(crop, min_conf)
            if class_id == 0:
                continue
            block_mask = mask[y:y2, x:x2]
            block_mask[veg_block > 0] = class_id
            mask[y:y2, x:x2] = block_mask

    if smooth > 0 and np.any(mask):
        # Light smoothing keeps block edges but removes single-pixel noise.
        smooth_mask = cv2.medianBlur(mask, smooth | 1)
        mask = np.where(veg > 0, smooth_mask, 0).astype(np.uint8)

    return mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets" / "inbox")
    parser.add_argument("--masks", type=Path, default=None)
    parser.add_argument("--preview", type=Path, default=None)
    parser.add_argument("--block", type=int, default=64, help="Classifier block size at working resolution")
    parser.add_argument("--max-side", type=int, default=1280, help="Downscale long edge before labeling")
    parser.add_argument("--min-conf", type=float, default=0.50)
    parser.add_argument("--smooth", type=int, default=3, help="Median blur kernel (0=off)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--export", type=Path, default=None, help="Export mask PNG dataset")
    parser.add_argument("--export-yolo-seg", type=Path, default=None, help="Export YOLO-seg polygons")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    args = parser.parse_args()

    image_dir = args.input.resolve()
    mask_dir = (args.masks or image_dir / "masks").resolve()
    preview_dir = (args.preview or image_dir / "preview_seg").resolve()
    preview_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    images = list_images(image_dir, recursive=not args.no_recursive)
    if args.limit > 0:
        images = images[: args.limit]
    if not images:
        raise SystemExit(f"No images in {image_dir}")

    labeled = 0
    total_pixels = 0

    for i, img_path in enumerate(images, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[{i}/{len(images)}] skip unreadable: {img_path.name}")
            continue
        mask = segment_image(
            frame,
            block=args.block,
            min_conf=args.min_conf,
            smooth=args.smooth,
            max_side=args.max_side,
        )
        save_mask(mask_path(mask_dir, img_path), mask)
        veg_pixels = int(np.count_nonzero(mask))
        if veg_pixels:
            labeled += 1
            total_pixels += veg_pixels
            prev = overlay_mask(frame, mask)
            thumb_max = 1280
            h, w = prev.shape[:2]
            if w > thumb_max:
                scale = thumb_max / w
                prev = cv2.resize(prev, (thumb_max, max(1, int(h * scale))))
            cv2.imwrite(str(preview_dir / img_path.name), prev)
        if i % 10 == 0 or i == len(images):
            print(f"[{i}/{len(images)}] {img_path.name}: {veg_pixels:,} labeled px")

    print(f"Done. {labeled}/{len(images)} images with masks, {total_pixels:,} total labeled pixels.")
    print(f"Masks: {mask_dir}")
    print(f"Previews: {preview_dir}")
    print("Review/fix: python tools/label_masks.py --input", image_dir)

    if args.export:
        export_seg_dataset(images, mask_dir, args.export.resolve(), args.val_ratio)
        print(f"Exported mask dataset: {args.export}")
    if args.export_yolo_seg:
        export_yolo_seg_from_masks(images, mask_dir, args.export_yolo_seg.resolve(), args.val_ratio)
        print(f"Exported YOLO-seg dataset: {args.export_yolo_seg}")


if __name__ == "__main__":
    main()
