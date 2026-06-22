"""Interactive semantic segmentation mask editor (brush painting).

Usage:
  python tools/label_masks.py --input datasets/inbox
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

from tools.seg_common import (
    CLASS_NAMES,
    MASK_COLORS_BGR,
    list_images,
    load_mask,
    mask_path,
    overlay_mask,
    save_mask,
)


class MaskLabelSession:
    def __init__(self, image_dir: Path, mask_dir: Path, recursive: bool = True):
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        self.images = list_images(image_dir, recursive=recursive)
        if not self.images:
            raise SystemExit(f"No images in {image_dir}")
        self.idx = 0
        self.brush = 24
        self.class_id = 1  # mask value 1..4
        self.erase = False
        self._frame: np.ndarray | None = None
        self._mask: np.ndarray | None = None
        self._path: Path | None = None
        self._painting = False

    def load(self) -> bool:
        self._path = self.images[self.idx]
        self._frame = cv2.imread(str(self._path))
        if self._frame is None:
            return False
        h, w = self._frame.shape[:2]
        self._mask = load_mask(mask_path(self.mask_dir, self._path), (h, w))
        return True

    def save(self) -> None:
        if self._mask is None or self._path is None:
            return
        save_mask(mask_path(self.mask_dir, self._path), self._mask)

    def _paint(self, x: int, y: int) -> None:
        if self._mask is None:
            return
        value = 0 if self.erase else self.class_id
        cv2.circle(self._mask, (x, y), self.brush, int(value), -1)

    def render(self) -> np.ndarray:
        assert self._frame is not None and self._mask is not None and self._path is not None
        vis = overlay_mask(self._frame, self._mask, alpha=0.5)
        bar_h = 40
        bar = np.zeros((bar_h, vis.shape[1], 3), dtype=np.uint8)
        bar[:] = (30, 40, 35)
        cls_name = "erase" if self.erase else CLASS_NAMES[self.class_id - 1]
        msg = (
            f"[{self.idx + 1}/{len(self.images)}] {self._path.name}  "
            f"class={cls_name} (0-3)  e=erase  [/]=brush  drag=paint  n/p  s  q"
        )
        cv2.putText(bar, msg, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 235, 220), 1, cv2.LINE_AA)
        for i, name in enumerate(CLASS_NAMES):
            color = MASK_COLORS_BGR[i + 1]
            x0 = vis.shape[1] - 420 + i * 100
            cv2.rectangle(bar, (x0, 8), (x0 + 16, 24), color, -1)
            cv2.putText(bar, str(i), (x0 + 22, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 210, 200), 1)
        return np.vstack([bar, vis])

    def on_mouse(self, event, x, y, _flags, _param):
        if y < 40:
            return
        y -= 40
        if event == cv2.EVENT_LBUTTONDOWN:
            self._painting = True
            self._paint(x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self._painting:
            self._paint(x, y)
        elif event in (cv2.EVENT_LBUTTONUP, cv2.EVENT_RBUTTONUP):
            self._painting = False
        if event == cv2.EVENT_RBUTTONDOWN:
            self.erase = True
            self._painting = True
            self._paint(x, y)

    def run(self) -> None:
        win = "AgriVision Mask Labeler"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(win, self.on_mouse)

        while True:
            if not self.load():
                print("Skip unreadable:", self._path)
                self.idx = (self.idx + 1) % len(self.images)
                continue
            while True:
                cv2.imshow(win, self.render())
                key = cv2.waitKey(20) & 0xFF
                if key == ord("q"):
                    self.save()
                    cv2.destroyAllWindows()
                    return
                if key == ord("s"):
                    self.save()
                    print("Saved", mask_path(self.mask_dir, self._path))
                if key == ord("n"):
                    self.save()
                    self.idx = (self.idx + 1) % len(self.images)
                    break
                if key == ord("p"):
                    self.save()
                    self.idx = (self.idx - 1) % len(self.images)
                    break
                if key == ord("e"):
                    self.erase = not self.erase
                if key in (ord("0"), ord("1"), ord("2"), ord("3")):
                    self.class_id = key - ord("0") + 1
                    self.erase = False
                if key in (ord("["),):
                    self.brush = max(4, self.brush - 4)
                if key in (ord("]"),):
                    self.brush = min(128, self.brush + 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets" / "inbox")
    parser.add_argument("--masks", type=Path, default=None)
    parser.add_argument("--no-recursive", action="store_true")
    args = parser.parse_args()
    image_dir = args.input.resolve()
    mask_dir = (args.masks or image_dir / "masks").resolve()
    MaskLabelSession(image_dir, mask_dir, recursive=not args.no_recursive).run()


if __name__ == "__main__":
    main()
