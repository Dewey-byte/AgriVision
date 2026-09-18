"""Keras-style accuracy/loss graphs for the three architecture families.

Reads each model's results.csv and writes per-model and comparison figures at
epoch checkpoints 20 / 40 / 60 / 80 / 100:

  output/model_history_keras_style_{slug}_{ep}ep.png
  output/model_history_keras_style_{slug}_all_epochs.png
  output/model_history_keras_style_three_models_{ep}ep.png
  output/model_history_keras_style_three_models_overlay.png
  output/tables/three_models_keras_style.md

Usage:
    python tools/generate_keras_style_three_models.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "output"
DEFAULT_EPOCHS = [20, 40, 60, 80, 100]

MODELS = [
    {
        "slug": "yolov8n",
        "label": "YOLOv8n",
        "optimizer": "AdamW",
        "csv": ROOT / "runs" / "detect" / "runs" / "banana_disease" / "results.csv",
        "color": "C0",
    },
    {
        "slug": "yolov9s",
        "label": "YOLOv9s",
        "optimizer": "AdamW",
        "csv": ROOT / "runs" / "detect" / "bench_yolov9s" / "results.csv",
        "color": "C4",
    },
    {
        "slug": "yolov9t",
        "label": "YOLOv9t",
        "optimizer": "AdamW",
        "csv": ROOT / "runs" / "detect" / "bench_yolov9t" / "results.csv",
        "color": "C2",
    },
    {
        "slug": "yolo_nas_s",
        "label": "YOLO-NAS S",
        "optimizer": "AdamW",
        "csv": ROOT / "runs" / "nas" / "bench_yolo_nas_s" / "results.csv",
        "color": "C3",
    },
]


def load_history(csv_path: Path) -> dict[str, np.ndarray]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV: {csv_path}")
        fieldnames = [name.strip() for name in reader.fieldnames]
        columns: dict[str, list[float]] = {name: [] for name in fieldnames}
        for row in reader:
            for name in fieldnames:
                raw = (row.get(name) or "").strip()
                columns[name].append(float(raw) if raw else 0.0)
    return {name: np.array(values, dtype=float) for name, values in columns.items()}


def _sum_loss(cols: dict[str, np.ndarray], prefix: str) -> np.ndarray:
    total = cols[f"{prefix}/box_loss"] + cols[f"{prefix}/cls_loss"]
    dfl = f"{prefix}/dfl_loss"
    if dfl in cols:
        total = total + cols[dfl]
    return total


def history_series(cols: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    epochs = cols["epoch"]
    train_loss = _sum_loss(cols, "train")
    val_loss = _sum_loss(cols, "val")
    val_acc = cols["metrics/mAP50(B)"]
    t0 = float(train_loss[0]) if len(train_loss) else 1.0
    train_acc = np.clip(1.0 - train_loss / max(t0, 1e-9), 0.0, 1.0)
    return {
        "epoch": epochs,
        "train_acc": train_acc,
        "val_acc": val_acc,
        "train_loss": train_loss,
        "val_loss": val_loss,
        "precision": cols["metrics/precision(B)"],
        "recall": cols["metrics/recall(B)"],
    }


def f1_score(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def metrics_at_epoch(series: dict[str, np.ndarray], epoch: int) -> dict[str, float]:
    idx = int(np.where(series["epoch"] <= epoch)[0][-1])
    p = float(series["precision"][idx])
    r = float(series["recall"][idx])
    acc = float(series["val_acc"][idx])
    used = int(series["epoch"][idx])
    return {
        "accuracy": acc,
        "recall": r,
        "precision": p,
        "f1": f1_score(p, r),
        "used_epoch": used,
    }


def _plot_pair(ax_acc, ax_loss, series: dict[str, np.ndarray], max_epoch: int) -> int:
    mask = series["epoch"] <= max_epoch
    if not np.any(mask):
        raise ValueError(f"No epochs <= {max_epoch}")
    epochs = series["epoch"][mask]
    ax_acc.plot(epochs, series["train_acc"][mask], label="train", color="C0")
    ax_acc.plot(epochs, series["val_acc"][mask], label="valid", color="C1")
    ax_acc.set_title("model accuracy")
    ax_acc.set_xlabel("epoch")
    ax_acc.set_ylabel("accuracy")
    ax_acc.legend(loc="upper left")
    ax_acc.set_xlim(0, max_epoch)

    ax_loss.plot(epochs, series["train_loss"][mask], label="train", color="C0")
    ax_loss.plot(epochs, series["val_loss"][mask], label="valid", color="C1")
    ax_loss.set_title("model loss")
    ax_loss.set_xlabel("epoch")
    ax_loss.set_ylabel("loss")
    ax_loss.legend(loc="upper right")
    ax_loss.set_xlim(0, max_epoch)
    return int(epochs[-1])


def caption_for(model: dict, requested: int, used: int) -> str:
    base = f"{model['label']} {model['optimizer']} Optimizer {used} epochs"
    if used < requested:
        return f"{base} (early stop; requested {requested})"
    return base


def plot_keras_style(
    series: dict[str, np.ndarray],
    model: dict,
    max_epoch: int,
    save_path: Path,
) -> int:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    used = _plot_pair(axes[0], axes[1], series, max_epoch)
    fig.text(0.5, -0.02, caption_for(model, max_epoch, used), ha="center", va="top", fontsize=11)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return used


def plot_stacked_epochs(
    series: dict[str, np.ndarray],
    model: dict,
    checkpoints: list[int],
    save_path: Path,
) -> None:
    labels = "abcdefghijklmnop"
    n = len(checkpoints)
    fig, axes = plt.subplots(n, 2, figsize=(12, 4 * n))
    if n == 1:
        axes = np.array([axes])

    for row, ep in enumerate(checkpoints):
        ax_acc, ax_loss = axes[row]
        used = _plot_pair(ax_acc, ax_loss, series, ep)
        tag = labels[row] if row < len(labels) else str(row + 1)
        ax_loss.text(
            0.5,
            -0.28,
            f"({tag}) {caption_for(model, ep, used)}",
            transform=ax_loss.transAxes,
            ha="center",
            fontsize=11,
        )

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_three_models_at_epoch(
    loaded: list[tuple[dict, dict[str, np.ndarray]]],
    max_epoch: int,
    save_path: Path,
) -> None:
    n = len(loaded)
    fig, axes = plt.subplots(n, 2, figsize=(12, 4 * n))
    if n == 1:
        axes = np.array([axes])
    labels = "abc"

    for row, (model, series) in enumerate(loaded):
        ax_acc, ax_loss = axes[row]
        used = _plot_pair(ax_acc, ax_loss, series, max_epoch)
        tag = labels[row] if row < len(labels) else str(row + 1)
        ax_loss.text(
            0.5,
            -0.28,
            f"({tag}) {caption_for(model, max_epoch, used)}",
            transform=ax_loss.transAxes,
            ha="center",
            fontsize=11,
        )

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_overlay(
    loaded: list[tuple[dict, dict[str, np.ndarray]]],
    max_epoch: int,
    save_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    for model, series in loaded:
        mask = series["epoch"] <= max_epoch
        epochs = series["epoch"][mask]
        color = model["color"]
        axes[0].plot(epochs, series["train_acc"][mask], color=color, linestyle="-", label=f"{model['label']} train")
        axes[0].plot(epochs, series["val_acc"][mask], color=color, linestyle="--", label=f"{model['label']} valid")
        axes[1].plot(epochs, series["train_loss"][mask], color=color, linestyle="-", label=f"{model['label']} train")
        axes[1].plot(epochs, series["val_loss"][mask], color=color, linestyle="--", label=f"{model['label']} valid")

    axes[0].set_title("model accuracy")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("accuracy")
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].set_xlim(0, max_epoch)

    axes[1].set_title("model loss")
    axes[1].set_xlabel("epoch")
    axes[1].set_ylabel("loss")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_xlim(0, max_epoch)

    fig.text(
        0.5,
        -0.02,
        f"YOLOv8n vs YOLOv9t vs YOLO-NAS S  AdamW  {max_epoch} epochs",
        ha="center",
        va="top",
        fontsize=11,
    )
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def build_table(loaded: list[tuple[dict, dict[str, np.ndarray]]], checkpoints: list[int]) -> str:
    lines = [
        "## Three-model Keras-style results (AdamW)",
        "",
        "| Model | Epochs | Accuracy | Recall | Precision | F1-Score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, series in loaded:
        max_available = int(series["epoch"][-1])
        usable = [ep for ep in checkpoints if ep <= max_available]
        rows = [metrics_at_epoch(series, ep) for ep in usable]
        for ep, m in zip(usable, rows):
            lines.append(
                f"| {model['label']} | {m['used_epoch']} | {m['accuracy']*100:.2f}% | "
                f"{m['recall']*100:.2f} | {m['precision']*100:.2f} | {m['f1']*100:.2f} |"
            )
        if rows:
            avg_acc = np.mean([m["accuracy"] for m in rows]) * 100
            avg_rec = np.mean([m["recall"] for m in rows]) * 100
            avg_pre = np.mean([m["precision"] for m in rows]) * 100
            avg_f1 = np.mean([m["f1"] for m in rows]) * 100
            lines.append(
                f"| **{model['label']} Average** | | **{avg_acc:.2f}%** | "
                f"**{avg_rec:.2f}** | **{avg_pre:.2f}** | **{avg_f1:.2f}** |"
            )

    lines.extend(
        [
            "",
            "*Accuracy = validation mAP@0.5. Train accuracy is a Keras-style proxy "
            "`1 - train_loss / train_loss[0]`. YOLO-NAS has no DFL term, so its "
            "loss magnitude is not directly comparable to Ultralytics YOLO.*",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--epochs", type=int, nargs="+", default=DEFAULT_EPOCHS)
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Generate only these model slugs (e.g. yolov9s)",
    )
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="Skip the stacked three-model and overlay figures",
    )
    args = parser.parse_args()

    out_dir = args.out.resolve()
    table_dir = out_dir / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    models = MODELS
    if args.only:
        wanted = set(args.only)
        models = [m for m in MODELS if m["slug"] in wanted]
        missing = wanted - {m["slug"] for m in models}
        if missing:
            raise SystemExit(f"Unknown slug(s): {', '.join(sorted(missing))}")

    loaded: list[tuple[dict, dict[str, np.ndarray]]] = []
    for model in models:
        csv_path = model["csv"]
        if not csv_path.is_file():
            raise SystemExit(f"Missing {csv_path}")
        series = history_series(load_history(csv_path))
        loaded.append((model, series))
        print(f"Loaded {model['label']}: {int(series['epoch'][-1])} epochs from {csv_path}")

    for model, series in loaded:
        max_available = int(series["epoch"][-1])
        checkpoints = [ep for ep in args.epochs if ep <= max_available]
        if not checkpoints:
            raise SystemExit(f"No checkpoints <= {max_available} for {model['label']}")

        for ep in checkpoints:
            path = out_dir / f"model_history_keras_style_{model['slug']}_{ep}ep.png"
            plot_keras_style(series, model, ep, path)
            print(f"Wrote {path}")

        stacked = out_dir / f"model_history_keras_style_{model['slug']}_all_epochs.png"
        plot_stacked_epochs(series, model, checkpoints, stacked)
        print(f"Wrote {stacked}")

    if not args.no_compare and len(loaded) > 1:
        for ep in args.epochs:
            comparable = [(m, s) for m, s in loaded if int(s["epoch"][0]) <= ep]
            if not comparable:
                continue
            path = out_dir / f"model_history_keras_style_three_models_{ep}ep.png"
            plot_three_models_at_epoch(comparable, ep, path)
            print(f"Wrote {path}")

        overlay = out_dir / "model_history_keras_style_three_models_overlay.png"
        plot_overlay(loaded, max(args.epochs), overlay)
        print(f"Wrote {overlay}")

    table_name = (
        "three_models_keras_style.md"
        if not args.only
        else f"{'_'.join(args.only)}_keras_style.md"
    )
    table_path = table_dir / table_name
    table_path.write_text(build_table(loaded, args.epochs), encoding="utf-8")
    print(f"Wrote {table_path}")


if __name__ == "__main__":
    main()
