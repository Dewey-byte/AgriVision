"""Score every benchmark contender on the same held-out split.

Contenders are declared under the ``benchmark`` key of
``web/api/data/models.json``. Each one is evaluated on an identical dataset
split with identical inference settings, then written to
``output/metrics/benchmarks/<id>.json``. The admin dashboard's Model Comparison
page reads that folder, so a run of this script is what makes new numbers show
up in the browser.

YOLO-NAS cannot be evaluated here: Ultralytics ships a predictor and validator
for it but no trainer, so its fine-tuned weights live in a separate
``super-gradients`` environment. ``tools/train_yolo_nas.py`` writes a JSON file
in the same schema into the same folder, and this script leaves those files
alone unless ``--force`` is passed.

Usage:
    python tools/benchmark_models.py
    python tools/benchmark_models.py --only yolov9s-bench
    python tools/benchmark_models.py --split val
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.validation_metrics import run_validation  # noqa: E402

MODELS_CONFIG = ROOT / "web" / "api" / "data" / "models.json"
BENCHMARKS_DIR = ROOT / "output" / "metrics" / "benchmarks"

# Runners this script knows how to execute in the main venv.
NATIVE_RUNNERS = {"ultralytics"}


def load_benchmark_config() -> dict:
    cfg = json.loads(MODELS_CONFIG.read_text(encoding="utf-8"))
    bench = cfg.get("benchmark") or {}
    if not bench.get("contenders"):
        raise SystemExit(f"No benchmark.contenders defined in {MODELS_CONFIG}")
    return bench


def model_complexity(weights: Path) -> dict[str, float]:
    """Parameter count and GFLOPs, so size differences stay visible."""
    from ultralytics import YOLO

    try:
        model = YOLO(str(weights))
        n_params, _, _, flops = model.info(detailed=False, verbose=False)
        return {
            "params_millions": round(n_params / 1e6, 3),
            "gflops": round(float(flops), 2),
        }
    except Exception as exc:  # noqa: BLE001 - complexity is nice-to-have only
        print(f"    (could not read model complexity: {exc})")
        return {}


def training_summary(results_csv: Path) -> dict:
    """Epoch count and best validation mAP from an Ultralytics results.csv."""
    if not results_csv.is_file():
        return {}

    import csv

    epochs = 0
    best_map50 = 0.0
    with results_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            epochs = max(epochs, int(float(row.get("epoch", 0) or 0)))
            best_map50 = max(best_map50, float(row.get("metrics/mAP50(B)", 0) or 0))
    return {"epochs_trained": epochs, "best_val_map50": round(best_map50, 4)}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def evaluate_contender(contender: dict, bench: dict, split: str) -> dict:
    weights = ROOT / contender["weights"]
    if not weights.is_file():
        raise FileNotFoundError(f"weights not found: {weights}")

    report = run_validation(
        weights=weights,
        dataset_dir=ROOT / bench.get("dataset", "datasets/yolo_banana"),
        split=split,
        imgsz=int(bench.get("imgsz", 640)),
        batch=int(bench.get("batch", 8)),
        workers=0,
        plots=True,
        project=BENCHMARKS_DIR / "runs",
        name=contender["id"],
    )

    record = {
        "model_id": contender["id"],
        "name": contender["name"],
        "family": contender["family"],
        "runner": contender.get("runner", "ultralytics"),
        "weights": rel(weights),
        "split": split,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "overall": report["overall"],
        "per_class": report["per_class"],
        "speed_ms_per_image": report["speed_ms_per_image"],
        "dataset_stats": report["dataset_stats"],
        **model_complexity(weights),
    }

    if contender.get("results_csv"):
        record["training"] = {
            "results_csv": contender["results_csv"],
            **training_summary(ROOT / contender["results_csv"]),
        }
    return record


def print_leaderboard(records: list[dict]) -> None:
    if not records:
        return
    ranked = sorted(records, key=lambda r: r["overall"]["mAP50"], reverse=True)
    print(f"\nLeaderboard — {ranked[0]['split']} split, ranked by mAP@0.5\n")
    print(f"  {'Model':<16}{'mAP@0.5':>10}{'mAP@.5:.95':>12}{'P':>9}{'R':>9}{'F1':>9}{'Params':>10}")
    for rec in ranked:
        o = rec["overall"]
        params = rec.get("params_millions")
        print(
            f"  {rec['name']:<16}{o['mAP50']:>10.4f}{o['mAP50_95']:>12.4f}"
            f"{o['precision']:>9.3f}{o['recall']:>9.3f}{o['f1']:>9.3f}"
            f"{(f'{params:.2f}M' if params else '—'):>10}"
        )
    print(f"\n  Best mAP@0.5: {ranked[0]['name']} ({ranked[0]['overall']['mAP50'] * 100:.2f}%)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("train", "val", "test"), default=None)
    parser.add_argument("--only", action="append", help="Evaluate just this contender id (repeatable)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-evaluate contenders whose runner is not runnable here (normally skipped)",
    )
    args = parser.parse_args()

    bench = load_benchmark_config()
    split = args.split or bench.get("split", "test")
    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)

    contenders = bench["contenders"]
    if args.only:
        wanted = set(args.only)
        contenders = [c for c in contenders if c["id"] in wanted]
        missing = wanted - {c["id"] for c in contenders}
        if missing:
            raise SystemExit(f"Unknown contender id(s): {', '.join(sorted(missing))}")

    records: list[dict] = []
    for contender in contenders:
        runner = contender.get("runner", "ultralytics")
        out_path = BENCHMARKS_DIR / f"{contender['id']}.json"

        if runner not in NATIVE_RUNNERS and not args.force:
            print(f"[skip] {contender['name']} — runner '{runner}' runs in its own environment")
            if out_path.is_file():
                records.append(json.loads(out_path.read_text(encoding="utf-8")))
            continue

        print(f"\n[eval] {contender['name']} ({contender['weights']}) on {split} split")
        try:
            record = evaluate_contender(contender, bench, split)
        except FileNotFoundError as exc:
            print(f"[skip] {contender['name']} — {exc}")
            if out_path.is_file():
                records.append(json.loads(out_path.read_text(encoding="utf-8")))
            continue

        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"    wrote {rel(out_path)}")
        records.append(record)

    print_leaderboard(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
