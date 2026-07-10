"""Build epoch checkpoint table + Keras-style training graphs.

Reads Ultralytics results.csv and writes:
  - output/tables/table7_yolov8n_results.md
  - output/model_history_keras_style_20ep.png
  - output/model_history_keras_style_40ep.png
  - output/model_history_keras_style_60ep.png
  - output/model_history_keras_style_80ep.png
  - output/model_history_keras_style_all_epochs.png  (stacked 20/40/60/80)

Usage:
    python tools/generate_epoch_reports.py
    python tools/generate_epoch_reports.py --epochs 20 40 60 80 --csv runs/detect/runs/banana_disease/results.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "runs" / "detect" / "runs" / "banana_disease" / "results.csv"
DEFAULT_OUT = ROOT / "output"
MODEL_LABEL = "YOLOv8n"
OPTIMIZER = "AdamW"


def load_history(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    return df


def history_series(df: pd.DataFrame) -> dict[str, np.ndarray]:
    epochs = df["epoch"].to_numpy()
    train_loss = (
        df["train/box_loss"] + df["train/cls_loss"] + df["train/dfl_loss"]
    ).to_numpy()
    val_loss = (df["val/box_loss"] + df["val/cls_loss"] + df["val/dfl_loss"]).to_numpy()
    val_acc = df["metrics/mAP50(B)"].to_numpy()
    t0 = float(train_loss[0]) if len(train_loss) else 1.0
    train_acc = np.clip(1.0 - train_loss / max(t0, 1e-9), 0.0, 1.0)
    return {
        "epoch": epochs,
        "train_acc": train_acc,
        "val_acc": val_acc,
        "train_loss": train_loss,
        "val_loss": val_loss,
        "precision": df["metrics/precision(B)"].to_numpy(),
        "recall": df["metrics/recall(B)"].to_numpy(),
    }


def f1_score(precision: float, recall: float) -> float:
    if precision + recall <= 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def metrics_at_epoch(series: dict[str, np.ndarray], epoch: int) -> dict[str, float]:
    idx = int(epoch) - 1
    p = float(series["precision"][idx])
    r = float(series["recall"][idx])
    acc = float(series["val_acc"][idx])
    f1 = f1_score(p, r)
    return {"accuracy": acc, "recall": r, "precision": p, "f1": f1}


def plot_keras_style(
    series: dict[str, np.ndarray],
    max_epoch: int,
    caption: str,
    save_path: Path,
) -> None:
    mask = series["epoch"] <= max_epoch
    epochs = series["epoch"][mask]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(epochs, series["train_acc"][mask], label="train", color="C0")
    axes[0].plot(epochs, series["val_acc"][mask], label="valid", color="C1")
    axes[0].set_title("model accuracy")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("accuracy")
    axes[0].legend(loc="upper left")
    axes[0].set_xlim(0, max_epoch)

    axes[1].plot(epochs, series["train_loss"][mask], label="train", color="C0")
    axes[1].plot(epochs, series["val_loss"][mask], label="valid", color="C1")
    axes[1].set_title("model loss")
    axes[1].set_xlabel("epoch")
    axes[1].set_ylabel("loss")
    axes[1].legend(loc="upper right")
    axes[1].set_xlim(0, max_epoch)

    fig.text(0.5, -0.02, caption, ha="center", va="top", fontsize=11)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_stacked_epochs(
    series: dict[str, np.ndarray],
    checkpoints: list[int],
    save_path: Path,
) -> None:
    labels = "abcdefghijklmnop"
    n = len(checkpoints)
    fig, axes = plt.subplots(n, 2, figsize=(12, 4 * n))
    if n == 1:
        axes = np.array([axes])

    for row, ep in enumerate(checkpoints):
        mask = series["epoch"] <= ep
        epochs = series["epoch"][mask]
        ax_acc, ax_loss = axes[row]

        ax_acc.plot(epochs, series["train_acc"][mask], label="train", color="C0")
        ax_acc.plot(epochs, series["val_acc"][mask], label="valid", color="C1")
        ax_acc.set_title("model accuracy")
        ax_acc.set_xlabel("epoch")
        ax_acc.set_ylabel("accuracy")
        ax_acc.legend(loc="upper left")
        ax_acc.set_xlim(0, ep)

        ax_loss.plot(epochs, series["train_loss"][mask], label="train", color="C0")
        ax_loss.plot(epochs, series["val_loss"][mask], label="valid", color="C1")
        ax_loss.set_title("model loss")
        ax_loss.set_xlabel("epoch")
        ax_loss.set_ylabel("loss")
        ax_loss.legend(loc="upper right")
        ax_loss.set_xlim(0, ep)

        tag = labels[row] if row < len(labels) else str(row + 1)
        ax_loss.text(
            0.5,
            -0.28,
            f"({tag}) {MODEL_LABEL} {OPTIMIZER} Optimizer {ep} epochs",
            transform=ax_loss.transAxes,
            ha="center",
            fontsize=11,
        )

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def build_table7_markdown(checkpoints: list[int], rows: list[dict[str, float]]) -> str:
    lines = [
        f"## Table 7. {MODEL_LABEL} Results using {OPTIMIZER} Optimizer",
        "",
        f"| {MODEL_LABEL} | Epochs | Accuracy | Recall | Precision | F1-Score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for ep, m in zip(checkpoints, rows):
        lines.append(
            f"| | {ep} | {m['accuracy']*100:.2f}% | {m['recall']*100:.2f} | "
            f"{m['precision']*100:.2f} | {m['f1']*100:.2f} |"
        )

    avg_acc = np.mean([m["accuracy"] for m in rows]) * 100
    avg_rec = np.mean([m["recall"] for m in rows]) * 100
    avg_pre = np.mean([m["precision"] for m in rows]) * 100
    avg_f1 = np.mean([m["f1"] for m in rows]) * 100
    total_avg = (avg_acc + avg_rec + avg_pre + avg_f1) / 4.0

    lines.extend(
        [
            f"| **Average** | | **{avg_acc:.2f}%** | **{avg_rec:.2f}** | "
            f"**{avg_pre:.2f}** | **{avg_f1:.2f}** |",
            f"| **Total Average** | | | | | **{total_avg:.2f}%** |",
            "",
            "*Accuracy = validation mAP@0.5. Metrics taken from `results.csv` at each epoch checkpoint.*",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--epochs", type=int, nargs="+", default=[20, 40, 60, 80])
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    out_dir = args.out.resolve()
    table_dir = out_dir / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    df = load_history(csv_path)
    series = history_series(df)
    max_available = int(series["epoch"][-1])

    checkpoints = [ep for ep in args.epochs if ep <= max_available]
    if not checkpoints:
        raise SystemExit(f"No checkpoints <= {max_available} epochs in {csv_path}")

    rows: list[dict[str, float]] = []
    for ep in checkpoints:
        rows.append(metrics_at_epoch(series, ep))
        caption = f"{MODEL_LABEL} {OPTIMIZER} Optimizer {ep} epochs"
        plot_path = out_dir / f"model_history_keras_style_{ep}ep.png"
        plot_keras_style(series, ep, caption, plot_path)
        print(f"Wrote {plot_path}")

    stacked_path = out_dir / "model_history_keras_style_all_epochs.png"
    plot_stacked_epochs(series, checkpoints, stacked_path)
    print(f"Wrote {stacked_path}")

    md = build_table7_markdown(checkpoints, rows)
    table_path = table_dir / "table7_yolov8n_results.md"
    table_path.write_text(md, encoding="utf-8")
    print(f"Wrote {table_path}")

    print("\nCheckpoint metrics:")
    for ep, m in zip(checkpoints, rows):
        print(
            f"  epoch {ep:3d}: mAP50={m['accuracy']*100:.2f}%  "
            f"P={m['precision']*100:.2f}  R={m['recall']*100:.2f}  F1={m['f1']*100:.2f}"
        )


if __name__ == "__main__":
    main()
