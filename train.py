"""Fine-tune YOLOv8 on AgriVision banana disease data (Label Studio export)."""

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
YOLO_ROOT = ROOT / "datasets" / "yolo_banana"
MODELS_DIR = ROOT / "models"
BASE_WEIGHTS = ROOT / "yolov8n.pt"


def resolve_data_yaml(dataset: Path | None = None) -> Path:
    """Use a YOLO dataset folder (data.yaml + images/labels splits)."""
    yolo_root = Path(dataset) if dataset else YOLO_ROOT
    if yolo_root.suffix.lower() in {".yaml", ".yml"}:
        data_yaml = yolo_root
        yolo_root = yolo_root.parent
    else:
        data_yaml = yolo_root / "data.yaml"
    if not data_yaml.is_file():
        raise FileNotFoundError(
            f"Missing dataset: {data_yaml}\n"
            "Export Label Studio annotations first, e.g.:\n"
            "  python tools/label_studio/export_yolo.py "
            "--json path/to/export.json "
            "--local-files-root C:/path/to/images "
            "--output datasets/yolo_banana"
        )

    for split in ("train", "val"):
        images = yolo_root / "images" / split
        labels = yolo_root / "labels" / split
        if not images.is_dir() or not labels.is_dir():
            raise FileNotFoundError(
                f"Incomplete dataset under {yolo_root} (missing images/{split} or labels/{split})"
            )

    print(f"Using YOLO dataset at {yolo_root}")
    return data_yaml


def train_model(
    data_yaml: Path,
    epochs: int,
    imgsz: int,
    batch: int,
    device: str,
    project: str,
    name: str,
    resume: str | None = None,
    workers: int = 0,
    model_name: str = "yolov8n.pt",
) -> Path:
    weights = resume or str(ROOT / model_name)
    if not Path(weights).is_file():
        raise FileNotFoundError(f"Missing weights: {weights}")

    model = YOLO(weights)
    results = model.train(
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
        # Small / imbalanced aerial datasets: stronger aug + class emphasis
        mosaic=1.0,
        mixup=0.1,
        copy_paste=0.1,
        degrees=5.0,
        translate=0.15,
        scale=0.6,
        fliplr=0.5,
        cls=1.0,
        box=7.5,
        patience=50,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training finished but weights were not found: {best_weights}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, MODELS_DIR / "best.pt")
    print(f"Copied trained weights to {MODELS_DIR / 'best.pt'}")
    return best_weights


def default_device() -> str:
    if torch is not None and torch.cuda.is_available():
        return "0"
    return "cpu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default=default_device())
    parser.add_argument("--project", default="runs")
    parser.add_argument("--name", default="banana_disease")
    parser.add_argument("--resume", default=None, help="Path to last.pt to resume training")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--model", default="yolov8n.pt", help="Base weights (yolov8n.pt or yolov8s.pt)")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="YOLO dataset folder or data.yaml (default: datasets/yolo_banana)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_yaml = resolve_data_yaml(args.data)
    train_model(
        data_yaml=data_yaml,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        resume=args.resume,
        workers=args.workers,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
