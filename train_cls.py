"""Fine-tune YOLOv8-cls on the secondary healthy/panama/sigatoka dataset.

Leaves the aerial detector (datasets/yolo_banana, models/best.pt) untouched.
Copies best weights to models/banana-cls.pt (close-range leaf classifier).
Do not use it to overwrite aerial YOLO labels unless AGRIVISION_CLS_REFINE=1.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

try:
    import torch
except ImportError:
    torch = None

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "datasets" / "cls_healthy_panama_sigatoka"
MODELS_DIR = ROOT / "models"
CLASS_NAMES = ("healthy", "panama", "black_sigatoka")


def resolve_cls_dataset(dataset: Path | None) -> Path:
    data = Path(dataset) if dataset else DEFAULT_DATA
    if not data.is_dir():
        raise FileNotFoundError(
            f"Missing classification dataset: {data}\n"
            "Build it first:\n"
            "  python tools/prepare_cls_secondary.py"
        )
    for split in ("train", "val"):
        split_dir = data / split
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Incomplete cls dataset (missing {split_dir})")
        for name in CLASS_NAMES:
            if not (split_dir / name).is_dir():
                raise FileNotFoundError(f"Missing class folder: {split_dir / name}")
    print(f"Using classification dataset at {data}")
    return data


def default_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def train_cls(
    data: Path,
    epochs: int,
    imgsz: int,
    batch: int,
    device: str,
    project: str,
    name: str,
    workers: int,
    model_name: str,
) -> Path:
    weights = ROOT / model_name
    if not weights.is_file():
        # Ultralytics will download if absent when given the bare name.
        model = YOLO(model_name)
    else:
        model = YOLO(str(weights))

    results = model.train(
        data=str(data),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        exist_ok=True,
        workers=workers,
        verbose=True,
        patience=30,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training finished but weights were not found: {best_weights}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / "banana-cls.pt"
    shutil.copy2(best_weights, dest)
    print(f"Copied classifier weights to {dest}")
    return best_weights


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=224)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--device", default=default_device())
    p.add_argument("--project", default="runs/classify")
    p.add_argument("--name", default="healthy_panama_sigatoka")
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--model", default="yolov8n-cls.pt")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data = resolve_cls_dataset(args.data)
    train_cls(
        data=data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        workers=args.workers,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
