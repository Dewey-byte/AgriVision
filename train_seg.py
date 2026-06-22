"""Fine-tune YOLOv8-seg on AgriVision semantic mask datasets."""

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
DEFAULT_DATA = ROOT / "datasets" / "yolo_seg_banana" / "data.yaml"
BASE_WEIGHTS = ROOT / "yolov8n-seg.pt"
MODELS_DIR = ROOT / "models"


def default_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def train_seg(
    data_yaml: Path,
    epochs: int,
    imgsz: int,
    batch: int,
    device: str,
    project: str,
    name: str,
    resume: str | None = None,
    workers: int = 0,
) -> Path:
    weights = resume or str(BASE_WEIGHTS)
    if not Path(weights).is_file():
        raise FileNotFoundError(f"Missing weights: {weights}")
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Missing dataset yaml: {data_yaml}")

    model = YOLO(weights)
    results = model.train(
        task="segment",
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        exist_ok=True,
        pretrained=resume is None,
        resume=bool(resume),
        workers=workers,
        verbose=True,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training finished but weights were not found: {best_weights}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, MODELS_DIR / "banana-seg.pt")
    print(f"Copied trained weights to {MODELS_DIR / 'banana-seg.pt'}")
    return best_weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=512)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default=default_device())
    parser.add_argument("--project", default="runs")
    parser.add_argument("--name", default="banana_seg")
    parser.add_argument("--resume", default=None)
    parser.add_argument("--workers", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_seg(
        data_yaml=args.data.resolve(),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        resume=args.resume,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
