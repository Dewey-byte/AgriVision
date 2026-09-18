"""Fine-tune a YOLO detector on AgriVision banana disease data (Label Studio export).

Defaults to YOLOv8n. Pass ``--model yolov9s.pt`` (or any Ultralytics-supported
checkpoint) to train a different architecture under identical hyperparameters,
which is how the Model Comparison benchmark keeps runs apples-to-apples.
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


def resolve_base_weights(model_name: str) -> str:
    """Prefer a checkpoint vendored in the repo, else let Ultralytics fetch it."""
    local = ROOT / model_name
    if local.is_file():
        return str(local)
    if Path(model_name).is_file():
        return model_name
    print(f"{model_name} not vendored in repo root; Ultralytics will download it")
    return model_name


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
    deploy: bool = True,
    patience: int = 50,
) -> Path:
    weights = resume or resolve_base_weights(model_name)

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
        patience=patience,
    )

    best_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training finished but weights were not found: {best_weights}")

    if deploy:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_weights, MODELS_DIR / "best.pt")
        print(f"Copied trained weights to {MODELS_DIR / 'best.pt'}")
    else:
        print(f"Left models/best.pt untouched; trained weights at {best_weights}")
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
    parser.add_argument("--project", default=str(ROOT / "runs" / "detect"))
    parser.add_argument("--name", default="banana_disease")
    parser.add_argument("--resume", default=None, help="Path to last.pt to resume training")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Base weights, e.g. yolov8n.pt, yolov8s.pt, yolov9t.pt, yolov9s.pt",
    )
    parser.add_argument(
        "--no-deploy",
        dest="deploy",
        action="store_false",
        default=True,
        help="Do not copy the result over models/best.pt (use for benchmark runs)",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="YOLO dataset folder or data.yaml (default: datasets/yolo_banana)",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
        help="Early-stop patience in epochs (0 disables early stopping)",
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
        deploy=args.deploy,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()
