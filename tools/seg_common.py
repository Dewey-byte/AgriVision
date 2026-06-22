"""Shared helpers for semantic segmentation masks (AgriVision)."""

from __future__ import annotations

import random
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}
SKIP_DIR_NAMES = {"labels", "masks", "preview", "preview_seg", "__pycache__"}

CLASS_NAMES = ["black_sigatoka", "healthy", "moko", "panama"]
# Mask pixel values: 0=background, 1..N = class index + 1
CLASS_TO_MASK = {name: idx + 1 for idx, name in enumerate(CLASS_NAMES)}
MASK_TO_CLASS = {v: k for k, v in CLASS_TO_MASK.items()}

# BGR overlay colors for visualization
MASK_COLORS_BGR = {
    0: (0, 0, 0),
    1: (53, 53, 220),   # black_sigatoka
    2: (40, 167, 69),   # healthy
    3: (255, 193, 7),   # moko
    4: (40, 120, 220),  # panama
}


def list_images(folder: Path, recursive: bool = True) -> list[Path]:
    out: list[Path] = []
    if recursive:
        paths = sorted(folder.rglob("*"))
    else:
        paths = sorted(folder.iterdir())
    for p in paths:
        if not p.is_file() or p.suffix not in IMAGE_SUFFIXES:
            continue
        if recursive and any(part in SKIP_DIR_NAMES for part in p.relative_to(folder).parts[:-1]):
            continue
        out.append(p)
    return out


def mask_path(mask_dir: Path, image_path: Path) -> Path:
    return mask_dir / f"{image_path.stem}.png"


def load_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    if path.is_file():
        m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if m is not None and m.shape[:2] == (h, w):
            return m
    return np.zeros((h, w), dtype=np.uint8)


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), mask)


def vegetation_mask(frame_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    lo = np.array([25, 40, 40], dtype=np.uint8)
    hi = np.array([95, 255, 255], dtype=np.uint8)
    return cv2.inRange(hsv, lo, hi)


def overlay_mask(frame_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    vis = frame_bgr.copy()
    if mask is None or not np.any(mask):
        return vis
    color_layer = np.zeros_like(vis)
    for mid, color in MASK_COLORS_BGR.items():
        if mid == 0:
            continue
        color_layer[mask == mid] = color
    blended = cv2.addWeighted(color_layer, alpha, vis, 1.0 - alpha, 0)
    vis[mask > 0] = blended[mask > 0]
    return vis


def mask_class_counts(mask: np.ndarray) -> dict[str, int]:
    counts: dict[str, int] = {name: 0 for name in CLASS_NAMES}
    counts["background"] = int(np.count_nonzero(mask == 0))
    for mid, name in MASK_TO_CLASS.items():
        counts[name] = int(np.count_nonzero(mask == mid))
    return counts


def export_seg_dataset(
    images: list[Path],
    mask_dir: Path,
    export_root: Path,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> None:
    rng = random.Random(seed)
    shuffled = images[:]
    rng.shuffle(shuffled)
    val_n = max(1, int(round(len(shuffled) * val_ratio)))
    val_set = set(shuffled[:val_n])

    for img in images:
        split = "val" if img in val_set else "train"
        dst_img = export_root / "images" / split / img.name
        dst_msk = export_root / "masks" / split / f"{img.stem}.png"
        dst_img.parent.mkdir(parents=True, exist_ok=True)
        dst_msk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, dst_img)
        src_msk = mask_path(mask_dir, img)
        if src_msk.is_file():
            shutil.copy2(src_msk, dst_msk)
        else:
            frame = cv2.imread(str(img))
            if frame is not None:
                save_mask(dst_msk, np.zeros(frame.shape[:2], dtype=np.uint8))

    data_yaml = export_root / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {export_root.as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                *[f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )


def mask_to_yolo_seg_lines(mask: np.ndarray, min_area: int = 64) -> list[str]:
    """Convert a semantic mask to YOLO-seg polygon lines (one polygon per contour)."""
    h, w = mask.shape[:2]
    lines: list[str] = []
    for mid, name in MASK_TO_CLASS.items():
        class_id = CLASS_NAMES.index(name)
        binary = (mask == mid).astype(np.uint8) * 255
        if not np.any(binary):
            continue
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            eps = 0.002 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            if len(approx) < 3:
                continue
            pts = approx.reshape(-1, 2).astype(np.float64)
            pts[:, 0] /= w
            pts[:, 1] /= h
            coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
            lines.append(f"{class_id} {coords}")
    return lines


def export_yolo_seg_from_masks(
    images: list[Path],
    mask_dir: Path,
    export_root: Path,
    val_ratio: float = 0.2,
    seed: int = 42,
    min_area: int = 64,
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
        frame = cv2.imread(str(img))
        if frame is None:
            dst_lbl.write_text("", encoding="utf-8")
            continue
        msk = load_mask(mask_path(mask_dir, img), frame.shape[:2])
        lines = mask_to_yolo_seg_lines(msk, min_area=min_area)
        dst_lbl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    data_yaml = export_root / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {export_root.as_posix()}",
                "train: images/train",
                "val: images/val",
                "names:",
                *[f"  {idx}: {name}" for idx, name in enumerate(CLASS_NAMES)],
                "",
            ]
        ),
        encoding="utf-8",
    )
