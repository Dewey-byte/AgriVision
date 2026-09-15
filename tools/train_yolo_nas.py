"""Fine-tune and score YOLO-NAS on the AgriVision banana dataset.

Ultralytics ships a predictor and validator for YOLO-NAS but no trainer, so
fine-tuning has to go through Deci's ``super-gradients``. That package pins an
older numpy/protobuf/onnx stack, so it lives in its own environment built by
``tools/setup_venv_nas.ps1``.

This script trains on the exact same ``datasets/yolo_banana`` splits as
``train.py``, then writes two things the admin dashboard already knows how to
read:

  - ``output/metrics/benchmarks/<model-id>.json`` — the same evaluation schema
    ``tools/benchmark_models.py`` emits for the Ultralytics contenders.
  - ``runs/nas/<experiment>/results.csv`` — per-epoch curves using Ultralytics'
    column names, so the Model Comparison training charts work unchanged.

Usage (from the repository root):
    .\venv-nas\Scripts\python.exe tools\train_yolo_nas.py --epochs 100
    .\venv-nas\Scripts\python.exe tools\train_yolo_nas.py --eval-only
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datasets" / "yolo_banana"
BENCHMARKS_DIR = ROOT / "output" / "metrics" / "benchmarks"
RUNS_DIR = ROOT / "runs" / "nas"
WEIGHTS_DIR = ROOT / "weights"
MODEL_ID = "yolonas-s-bench"

# COCO checkpoints ship with an 80-class head; super-gradients swaps it for ours.
COCO_NUM_CLASSES = 80

# super-gradients still points at sghub.deci.ai, which stopped resolving after
# Deci was acquired. Fetch the checkpoint ourselves and hand it to models.get()
# as an explicit path, so training never depends on that dead host.
COCO_WEIGHT_MIRRORS = {
    "yolo_nas_s": (
        "https://d2gjn4b69gu75n.cloudfront.net/models/yolo_nas_s_coco.pth",
        "https://github.com/qpal147147/YOLO-NAS/releases/download/v1.0.0/yolo_nas_s_coco.pth",
    ),
    "yolo_nas_m": (
        "https://d2gjn4b69gu75n.cloudfront.net/models/yolo_nas_m_coco.pth",
        "https://github.com/qpal147147/YOLO-NAS/releases/download/v1.0.0/yolo_nas_m_coco.pth",
    ),
    "yolo_nas_l": (
        "https://d2gjn4b69gu75n.cloudfront.net/models/yolo_nas_l_coco.pth",
        "https://github.com/qpal147147/YOLO-NAS/releases/download/v1.0.0/yolo_nas_l_coco.pth",
    ),
}

CSV_COLUMNS = [
    "epoch",
    "metrics/precision(B)",
    "metrics/recall(B)",
    "metrics/mAP50(B)",
    "metrics/mAP50-95(B)",
    "train/box_loss",
    "train/cls_loss",
    "val/box_loss",
    "val/cls_loss",
]


def coco_checkpoint(model_name: str) -> Path:
    """Local COCO checkpoint for a YOLO-NAS variant, downloading it if needed.

    These pretrained weights carry Deci's own non-commercial licence, see
    https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md
    """
    destination = WEIGHTS_DIR / f"{model_name}_coco.pth"
    if destination.is_file():
        return destination

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in COCO_WEIGHT_MIRRORS[model_name]:
        print(f"Downloading {model_name} COCO weights from {url}")
        try:
            urllib.request.urlretrieve(url, destination)
            return destination
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            errors.append(f"{url}: {exc}")
            destination.unlink(missing_ok=True)

    raise SystemExit(
        f"Could not download {model_name} COCO weights. Tried:\n  "
        + "\n  ".join(errors)
        + f"\nDownload manually and save as {destination}."
    )


def load_model(model_name: str, num_classes: int, checkpoint: Path | None = None):
    """Build a YOLO-NAS with our class count, from COCO or a fine-tuned run."""
    from super_gradients.training import models

    if checkpoint is None:
        return models.get(
            model_name,
            num_classes=num_classes,
            checkpoint_path=str(coco_checkpoint(model_name)),
            checkpoint_num_classes=COCO_NUM_CLASSES,
        )
    return models.get(model_name, num_classes=num_classes, checkpoint_path=str(checkpoint))


def class_names() -> list[str]:
    raw = yaml.safe_load((DATASET / "data.yaml").read_text(encoding="utf-8")) or {}
    names = raw["names"]
    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=lambda x: int(x))]
    return list(names)


def metric_value(metrics: dict, key: str) -> float | None:
    """Exact lookup in super-gradients' metric dict.

    Substring matching is not safe here: ``mAP@0.50`` is a prefix of
    ``mAP@0.50:0.95``, so a loose match can silently return the wrong figure
    depending on dict ordering. The exact component names come from
    ``DetectionMetrics_050(...).component_names``.
    """
    if key not in metrics:
        return None
    try:
        return float(metrics[key])
    except (TypeError, ValueError):
        return None


def loss_value(metrics: dict, suffix: str) -> float | None:
    """Loss components are keyed by loss class, e.g. ``PPYoloELoss/loss_iou``."""
    for key, value in metrics.items():
        if str(key).endswith(suffix):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def f1_score(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def split_stats(split: str, names: list[str]) -> dict:
    """Image and box counts per class, matching backend.validation_metrics."""
    images_dir = DATASET / "images" / split
    labels_dir = DATASET / "labels" / split
    instances = {n: 0 for n in names}
    images_with = {n: 0 for n in names}
    image_count = 0
    instance_count = 0

    for img in sorted(images_dir.iterdir()):
        label = labels_dir / f"{img.stem}.txt"
        if not img.is_file() or not label.is_file():
            continue
        image_count += 1
        seen: set[int] = set()
        for line in label.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            cid = int(float(parts[0]))
            if not 0 <= cid < len(names):
                continue
            instance_count += 1
            instances[names[cid]] += 1
            seen.add(cid)
        for cid in seen:
            images_with[names[cid]] += 1

    return {
        "split": split,
        "images": image_count,
        "instances": instance_count,
        "instances_by_class": instances,
        "images_with_class": images_with,
        "class_names": names,
    }


def build_dataloaders(names: list[str], batch: int, workers: int):
    from super_gradients.training.dataloaders.dataloaders import (
        coco_detection_yolo_format_train,
        coco_detection_yolo_format_val,
    )

    common = {"data_dir": str(DATASET), "classes": names}
    loader_params = {"batch_size": batch, "num_workers": workers, "drop_last": False}

    train = coco_detection_yolo_format_train(
        dataset_params={**common, "images_dir": "images/train", "labels_dir": "labels/train"},
        dataloader_params={**loader_params, "shuffle": True},
    )
    val = coco_detection_yolo_format_val(
        dataset_params={**common, "images_dir": "images/val", "labels_dir": "labels/val"},
        dataloader_params=loader_params,
    )
    test = coco_detection_yolo_format_val(
        dataset_params={**common, "images_dir": "images/test", "labels_dir": "labels/test"},
        dataloader_params=loader_params,
    )
    return train, val, test


def build_metrics(names: list[str]):
    """mAP@0.5 and mAP@0.5:0.95 with per-class AP, mirroring Ultralytics output."""
    from super_gradients.training.metrics import DetectionMetrics_050, DetectionMetrics_050_095
    from super_gradients.training.models.detection_models.pp_yolo_e import (
        PPYoloEPostPredictionCallback,
    )

    post_prediction = PPYoloEPostPredictionCallback(
        score_threshold=0.01,
        nms_top_k=1000,
        max_predictions=300,
        nms_threshold=0.7,
    )
    shared = {
        "score_thres": 0.1,
        "top_k_predictions": 300,
        "num_cls": len(names),
        "normalize_targets": True,
        "post_prediction_callback": post_prediction,
        "include_classwise_ap": True,
        "class_names": names,
    }
    return [DetectionMetrics_050(**shared), DetectionMetrics_050_095(**shared)]


class EpochCsvLogger:
    """Append per-epoch validation metrics in Ultralytics' results.csv format."""

    def __init__(self, path: Path, append: bool = False):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if append and self.path.is_file():
            return
        with self.path.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(CSV_COLUMNS)

    def log(self, epoch: int, metrics: dict) -> None:
        def fmt(value: float | None) -> float:
            return round(value, 5) if value is not None else 0.0

        # Only validation losses are in scope at VALIDATION_EPOCH_END, so the
        # train/* columns mirror them rather than being left blank.
        box_loss = loss_value(metrics, "loss_iou")
        cls_loss = loss_value(metrics, "loss_cls")
        row = [
            epoch,
            fmt(metric_value(metrics, "Precision@0.50")),
            fmt(metric_value(metrics, "Recall@0.50")),
            fmt(metric_value(metrics, "mAP@0.50")),
            fmt(metric_value(metrics, "mAP@0.50:0.95")),
            fmt(box_loss),
            fmt(cls_loss),
            fmt(box_loss),
            fmt(cls_loss),
        ]
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(row)


def make_epoch_callback(logger: EpochCsvLogger):
    from super_gradients.training.utils.callbacks import Phase, PhaseCallback

    class _Callback(PhaseCallback):
        def __init__(self):
            super().__init__(phase=Phase.VALIDATION_EPOCH_END)

        def __call__(self, context):
            logger.log(int(context.epoch) + 1, dict(context.metrics_dict or {}))

    return _Callback()


def deployed_checkpoint(args) -> Path:
    """Where a finished run's best checkpoint is published.

    Smoke runs keep their checkpoint inside the run directory so a throwaway
    one-epoch model can never end up as the benchmarked one.
    """
    if args.smoke:
        return RUNS_DIR / args.name / "smoke_best.pth"
    return ROOT / "models" / "yolo_nas_s_banana.pth"


def train(args, names: list[str]) -> Path:
    from super_gradients.training import Trainer
    from super_gradients.training.losses import PPYoloELoss

    train_loader, val_loader, _ = build_dataloaders(names, args.batch, args.workers)
    trainer = Trainer(experiment_name=args.name, ckpt_root_dir=str(RUNS_DIR))
    model = load_model(args.model, len(names))

    csv_logger = EpochCsvLogger(RUNS_DIR / args.name / "results.csv", append=args.resume)

    train_params = {
        "silent_mode": False,
        # Off deliberately, for two reasons. It pickles model snapshots to
        # averaging_snapshots.pkl every epoch, which intermittently fails on
        # Windows with "file cannot be opened" and killed a 42-epoch run. It
        # also selects a different kind of checkpoint than Ultralytics' best.pt
        # (an average of top snapshots vs the single best epoch), which would
        # hand YOLO-NAS an advantage the other contenders do not get.
        "average_best_models": False,
        "resume": args.resume,
        "warmup_mode": "linear_epoch_step",
        "warmup_initial_lr": 1e-6,
        "lr_warmup_epochs": 3,
        "initial_lr": 5e-4,
        "lr_mode": "cosine",
        "cosine_final_lr_ratio": 0.1,
        "optimizer": "AdamW",
        "optimizer_params": {"weight_decay": 0.0001},
        "zero_weight_decay_on_bias_and_bn": True,
        "ema": True,
        "ema_params": {"decay": 0.9, "decay_type": "threshold"},
        "max_epochs": args.epochs,
        "mixed_precision": True,
        "loss": PPYoloELoss(use_static_assigner=False, num_classes=len(names), reg_max=16),
        "valid_metrics_list": build_metrics(names),
        "metric_to_watch": "mAP@0.50",
        "phase_callbacks": [make_epoch_callback(csv_logger)],
    }

    trainer.train(
        model=model,
        training_params=train_params,
        train_loader=train_loader,
        valid_loader=val_loader,
    )

    checkpoint = trainer.checkpoints_dir_path
    best = Path(checkpoint) / "ckpt_best.pth"
    if not best.is_file():
        raise RuntimeError(f"Training finished but no checkpoint at {best}")

    destination = deployed_checkpoint(args)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, destination)
    print(f"Copied best checkpoint to {destination}")
    return destination


def evaluate(args, names: list[str], weights: Path) -> dict:
    from super_gradients.training import Trainer

    _, _, test_loader = build_dataloaders(names, args.batch, args.workers)
    trainer = Trainer(experiment_name=f"{args.name}_eval", ckpt_root_dir=str(RUNS_DIR))
    model = load_model(args.model, len(names), checkpoint=weights)

    results = trainer.test(
        model=model,
        test_loader=test_loader,
        test_metrics_list=build_metrics(names),
    )
    metrics = dict(results) if not isinstance(results, dict) else results
    raw_dump = RUNS_DIR / args.name / "test_metrics_raw.json"
    raw_dump.parent.mkdir(parents=True, exist_ok=True)
    raw_dump.write_text(
        json.dumps({str(k): str(v) for k, v in metrics.items()}, indent=2), encoding="utf-8"
    )
    print(f"\nRaw super-gradients test metrics written to {raw_dump}")

    required = ("Precision@0.50", "Recall@0.50", "mAP@0.50", "mAP@0.50:0.95")
    missing = [key for key in required if key not in metrics]
    if missing:
        raise SystemExit(
            f"super-gradients did not report {missing}; got {sorted(metrics)}. "
            "A zeroed benchmark entry would be worse than none, so nothing was written."
        )

    precision = metric_value(metrics, "Precision@0.50") or 0.0
    recall = metric_value(metrics, "Recall@0.50") or 0.0
    stats = split_stats("test", names)

    # super-gradients reports per-class AP but no per-class precision/recall, so
    # those stay null instead of being faked as zero.
    per_class = [
        {
            "class_id": class_id,
            "name": name,
            "precision": None,
            "recall": None,
            "f1": None,
            "mAP50": round(metric_value(metrics, f"AP@0.50_{name}") or 0.0, 4),
            "mAP50_95": round(metric_value(metrics, f"AP@0.50:0.95_{name}") or 0.0, 4),
            "instances_in_split": stats["instances_by_class"].get(name, 0),
            "images_with_class": stats["images_with_class"].get(name, 0),
        }
        for class_id, name in enumerate(names)
    ]

    model_id = f"{MODEL_ID}-smoke" if args.smoke else MODEL_ID
    results_csv = RUNS_DIR / args.name / "results.csv"
    record = {
        "model_id": model_id,
        "name": "YOLO-NAS S",
        "family": "YOLO-NAS",
        "runner": "super-gradients",
        "weights": str(weights.relative_to(ROOT)) if weights.is_relative_to(ROOT) else str(weights),
        "split": "test",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1_score(precision, recall), 4),
            "mAP50": round(metric_value(metrics, "mAP@0.50") or 0.0, 4),
            "mAP50_95": round(metric_value(metrics, "mAP@0.50:0.95") or 0.0, 4),
        },
        "per_class": per_class,
        "speed_ms_per_image": {},
        "dataset_stats": stats,
        "params_millions": round(sum(p.numel() for p in model.parameters()) / 1e6, 3),
        "training": {
            "results_csv": str(results_csv.relative_to(ROOT)) if results_csv.is_file() else None,
            "epochs_trained": args.epochs,
            "batch": args.batch,
        },
    }

    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BENCHMARKS_DIR / f"{model_id}.json"
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path.relative_to(ROOT)}")

    overall = record["overall"]
    print(
        f"YOLO-NAS S on test split: mAP@0.5={overall['mAP50']:.4f}  "
        f"mAP@0.5:0.95={overall['mAP50_95']:.4f}  "
        f"P={overall['precision']:.3f}  R={overall['recall']:.3f}"
    )
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="yolo_nas_s", choices=("yolo_nas_s", "yolo_nas_m", "yolo_nas_l"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=8, help="Lower than train.py: YOLO-NAS S is ~19M params")
    # Unlike Ultralytics (which needs workers=0 on Windows), super-gradients is
    # fine with worker processes, and its mosaic/affine transforms are heavy
    # enough that workers=0 leaves the GPU idle ~90% of the time. Going to 4
    # cut epoch time from ~3.5 min to ~1.1 min.
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", default="bench_yolo_nas_s")
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Skip training and score the checkpoint at models/yolo_nas_s_banana.pth",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Throwaway run: keep the checkpoint in the run dir and export under a -smoke id",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue the latest run of this experiment instead of starting over",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    names = class_names()
    print(f"Classes: {names}")

    if args.eval_only:
        weights = deployed_checkpoint(args)
        if not weights.is_file():
            raise SystemExit(f"No checkpoint at {weights}; train first (drop --eval-only)")
    else:
        weights = train(args, names)

    evaluate(args, names, weights)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
