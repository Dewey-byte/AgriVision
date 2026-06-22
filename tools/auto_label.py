"""Auto-draft YOLO labels using the current AgriVision models (review in label_yolo.py).

Usage:
  python tools/auto_label.py --input datasets/inbox
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.detection import run_detection
from utils.drawing import draw_boxes

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_TO_ID = {
    "black_sigatoka": 0,
    "healthy": 1,
    "moko": 2,
    "panama": 3,
}


def _class_id_from_label(label: str) -> int:
    low = label.lower()
    for name, cid in CLASS_TO_ID.items():
        if name in low:
            return cid
    return 1


def _save_yolo(path: Path, dets: list[dict], w: int, h: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for det in dets:
        x1, y1, x2, y2 = det["bbox"]
        cid = _class_id_from_label(det.get("label", ""))
        cx = ((x1 + x2) / 2.0) / w
        cy = ((y1 + y2) / 2.0) / h
        bw = abs(x2 - x1) / w
        bh = abs(y2 - y1) / h
        lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets" / "inbox")
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--preview", type=Path, default=None)
    args = parser.parse_args()

    image_dir = args.input.resolve()
    label_dir = (args.labels or image_dir / "labels").resolve()
    preview_dir = (args.preview or image_dir / "preview").resolve()
    preview_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise SystemExit(f"No images in {image_dir}")

    for img_path in images:
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue
        h, w = frame.shape[:2]
        dets = run_detection(frame)
        _save_yolo(label_dir / f"{img_path.stem}.txt", dets, w, h)
        prev = draw_boxes(frame.copy(), dets)
        cv2.imwrite(str(preview_dir / img_path.name), prev)
        print(f"{img_path.name}: {len(dets)} box(es)")

    print(f"Labels -> {label_dir}")
    print(f"Preview -> {preview_dir}")
    print("Review and fix with: python tools/label_yolo.py --input", image_dir)


if __name__ == "__main__":
    main()
