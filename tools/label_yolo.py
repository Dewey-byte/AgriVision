"""Draw YOLO bounding boxes on banana images (per plant / leaf).

Usage:
  python tools/label_yolo.py --input datasets/inbox
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

CLASSES = ["black_sigatoka", "healthy", "moko", "panama"]
COLORS = [
    (69, 53, 220),
    (69, 167, 40),
    (7, 193, 255),
    (220, 120, 40),
]

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


SKIP_DIR_NAMES = {"labels", "preview", "__pycache__"}


def _list_images(folder: Path, recursive: bool = True) -> list[Path]:
    if recursive:
        paths = sorted(folder.rglob("*"))
    else:
        paths = sorted(folder.iterdir())
    out = []
    for p in paths:
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if recursive and any(part in SKIP_DIR_NAMES for part in p.relative_to(folder).parts[:-1]):
            continue
        out.append(p)
    return out


def _load_labels(path: Path, w: int, h: int) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls_id = int(parts[0])
        cx, cy, bw, bh = map(float, parts[1:])
        x1 = int((cx - bw / 2) * w)
        y1 = int((cy - bh / 2) * h)
        x2 = int((cx + bw / 2) * w)
        y2 = int((cy + bh / 2) * h)
        out.append({"class_id": cls_id, "bbox": [x1, y1, x2, y2]})
    return out


def _save_labels(path: Path, boxes: list[dict], w: int, h: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for b in boxes:
        x1, y1, x2, y2 = b["bbox"]
        cx = ((x1 + x2) / 2.0) / w
        cy = ((y1 + y2) / 2.0) / h
        bw = abs(x2 - x1) / w
        bh = abs(y2 - y1) / h
        lines.append(f"{b['class_id']} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


class LabelSession:
    def __init__(self, image_dir: Path, label_dir: Path, recursive: bool = True):
        self.image_dir = image_dir
        self.label_dir = label_dir
        self.images = _list_images(image_dir, recursive=recursive)
        if not self.images:
            raise SystemExit(f"No images in {image_dir}")
        self.idx = 0
        self.class_id = 1
        self.boxes: list[dict] = []
        self._drag_start: tuple[int, int] | None = None
        self._drag_end: tuple[int, int] | None = None
        self._frame: np.ndarray | None = None
        self._path: Path | None = None

    def _label_path(self, image_path: Path) -> Path:
        return self.label_dir / f"{image_path.stem}.txt"

    def load(self) -> bool:
        self._path = self.images[self.idx]
        self._frame = cv2.imread(str(self._path))
        if self._frame is None:
            return False
        h, w = self._frame.shape[:2]
        self.boxes = _load_labels(self._label_path(self._path), w, h)
        return True

    def save(self) -> None:
        if self._frame is None or self._path is None:
            return
        h, w = self._frame.shape[:2]
        _save_labels(self._label_path(self._path), self.boxes, w, h)

    def render(self) -> np.ndarray:
        assert self._frame is not None
        vis = self._frame.copy()
        for b in self.boxes:
            x1, y1, x2, y2 = b["bbox"]
            cid = b["class_id"]
            color = COLORS[cid % len(COLORS)]
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                vis,
                CLASSES[cid],
                (x1, max(16, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )
        if self._drag_start and self._drag_end:
            cv2.rectangle(vis, self._drag_start, self._drag_end, COLORS[self.class_id], 1)
        bar = np.zeros((36, vis.shape[1], 3), dtype=np.uint8)
        bar[:] = (30, 40, 35)
        msg = (
            f"[{self.idx + 1}/{len(self.images)}] {self._path.name}  "
            f"class={CLASSES[self.class_id]} (0-3)  drag=box  n/p=next/prev  u=undo  s=save  q=quit"
        )
        cv2.putText(bar, msg, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 235, 220), 1, cv2.LINE_AA)
        return np.vstack([bar, vis])

    def on_mouse(self, event, x, y, _flags, _param):
        if y < 36:
            return
        y -= 36
        if event == cv2.EVENT_LBUTTONDOWN:
            self._drag_start = (x, y)
            self._drag_end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self._drag_start:
            self._drag_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self._drag_start:
            x1, y1 = self._drag_start
            x2, y2 = x, y
            if abs(x2 - x1) > 8 and abs(y2 - y1) > 8:
                self.boxes.append(
                    {
                        "class_id": self.class_id,
                        "bbox": [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                    }
                )
            self._drag_start = None
            self._drag_end = None

    def run(self) -> None:
        win = "AgriVision Labeler"
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
                    print("Saved", self._label_path(self._path))
                if key == ord("n"):
                    self.save()
                    self.idx = (self.idx + 1) % len(self.images)
                    break
                if key == ord("p"):
                    self.save()
                    self.idx = (self.idx - 1) % len(self.images)
                    break
                if key == ord("u") and self.boxes:
                    self.boxes.pop()
                if key in (ord("0"), ord("1"), ord("2"), ord("3")):
                    self.class_id = key - ord("0")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets" / "inbox")
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only label images directly in --input (not subfolders)",
    )
    args = parser.parse_args()
    image_dir = args.input.resolve()
    label_dir = (args.labels or image_dir / "labels").resolve()
    LabelSession(image_dir, label_dir, recursive=not args.no_recursive).run()


if __name__ == "__main__":
    main()
