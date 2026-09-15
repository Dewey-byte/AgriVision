# AgriVision — Architecture Benchmark (YOLOv8 vs YOLOv9 vs YOLO-NAS)

This document covers the accuracy comparison surfaced on the admin dashboard's
**Model Comparison** page. It answers one question: on AgriVision's own aerial
banana dataset, which detector architecture is the most accurate?

The comparison is deliberately separate from the *deployed pipeline* section of
that page. Deployment cares about latency and the weights the desktop app
actually loads; this benchmark only cares about accuracy on a held-out split.

---

## The rule that makes the numbers comparable

Every contender is trained on the **same** `datasets/yolo_banana` splits
(593 train / 33 val / 34 test), for the **same** 100 epochs at **imgsz 640**,
and is then scored on the **held-out test split** — 34 images the model never
saw during training or validation — with identical inference settings.

Do not compare a number produced under a different recipe. The legacy
`runs/detect/runs/banana_disease` run, for example, used weaker augmentation and
`cls=0.5`, so it is kept out of the benchmark and shown only under "Deployed
pipeline".

Where a contender must deviate, the deviation is recorded in `models.json` and
shown in the dashboard. YOLO-NAS S trains at batch 8 rather than 16 because it
is roughly 19M parameters against YOLOv8n's 3M and will not fit a 6 GB card at
batch 16.

---

## Why YOLO-NAS needs its own environment

Ultralytics ships a *predictor* and *validator* for YOLO-NAS but no *trainer* —
`NAS.task_map` maps only `predictor` and `validator`. Running COCO-pretrained
YOLO-NAS against banana classes it has never seen would score near zero and
prove nothing, so YOLO-NAS has to be genuinely fine-tuned.

Fine-tuning it requires Deci's `super-gradients`, which pins `numpy<=1.23` plus
an older protobuf/onnx stack. Installing that alongside the main venv would
break the Ultralytics detector `core/detection.py` depends on. So it gets an
isolated `venv-nas`, and `tools/train_yolo_nas.py` writes its results in the
same JSON schema the Ultralytics harness uses. The dashboard cannot tell the
difference.

---

## Layout

| Piece | Path |
|---|---|
| Contender declarations | `web/api/data/models.json` → `benchmark.contenders` |
| Ultralytics training | `train.py --model <weights> --name <run> --no-deploy` |
| YOLO-NAS environment | `tools/setup_venv_nas.ps1` → `venv-nas/` |
| YOLO-NAS training + scoring | `tools/train_yolo_nas.py` |
| Scoring (Ultralytics models) | `tools/benchmark_models.py` |
| Per-model results | `output/metrics/benchmarks/<model-id>.json` |
| API | `GET /api/analytics/models` → `benchmark` |
| Dashboard page | `web/frontend/src/pages/ModelComparison.jsx` |

`benchmark_models.py` never reads a model's own training logs to decide
accuracy. It re-runs validation on the test split so all contenders are measured
by the same code path.

---

## Reproducing the benchmark

Stop the desktop app first — training needs the whole GPU.

### 1. Train the Ultralytics contenders

`--no-deploy` matters: without it, `train.py` copies its result over
`models/best.pt` and silently swaps the model the desktop app serves.

```powershell
python train.py --model yolov8n.pt --name bench_yolov8n --epochs 100 --batch 16 --no-deploy
python train.py --model yolov9s.pt --name bench_yolov9s --epochs 100 --batch 16 --no-deploy
```

Ultralytics downloads base weights it does not find in the repo root.

### 2. Train YOLO-NAS in its isolated environment

One-time setup (needs Python 3.10 — `super-gradients` does not support 3.11+):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\setup_venv_nas.ps1
```

Then train and score in one step:

```powershell
.\venv-nas\Scripts\python.exe tools\train_yolo_nas.py --epochs 100 --batch 8
```

This writes `output/metrics/benchmarks/yolonas-s-bench.json` itself, plus a
`results.csv` in Ultralytics' column format so the convergence chart works.

### 3. Score everything on the held-out test split

```powershell
python tools/benchmark_models.py
```

It evaluates each `runner: ultralytics` contender, skips the `super-gradients`
one (already scored in step 2), writes one JSON per model into
`output/metrics/benchmarks/`, and prints a leaderboard.

Useful flags:

| Flag | Effect |
|---|---|
| `--only <id>` | Score a single contender (repeatable) |
| `--split val` | Score the validation split instead of test |

### 4. Read the results in the dashboard

The API reads `output/metrics/benchmarks/` on every request, so no restart is
needed:

```powershell
uvicorn web.api.main:app --port 8077
```

Open the dashboard and go to **Model Comparison**. The page shows the ranked
leaderboard with the winner highlighted, overall and per-class mAP charts, and
all contenders' convergence curves on one axis.

---

## Adding a fourth contender

1. Train it, keeping the shared recipe from the top of this document.
2. Append an entry to `benchmark.contenders` in `web/api/data/models.json`:

```json
{
  "id": "yolo11n-bench",
  "name": "YOLO11n",
  "family": "YOLO11",
  "runner": "ultralytics",
  "weights": "runs/detect/bench_yolo11n/weights/best.pt",
  "results_csv": "runs/detect/bench_yolo11n/results.csv",
  "notes": "One sentence on what this architecture brings."
}
```

3. Run `python tools/benchmark_models.py --only yolo11n-bench`.

The dashboard picks it up on the next page load — leaderboard, charts, colours
and ranking all derive from the config plus the results folder. Contenders
declared but not yet scored appear greyed out with a "pending" pill, so the
line-up is visible before every run has finished.

For an architecture Ultralytics cannot train, give it a different `runner`
value. `benchmark_models.py` skips unknown runners instead of failing, and
whatever process trains it just has to drop a JSON file in the same schema into
`output/metrics/benchmarks/`.

---

## Interpreting the leaderboard honestly

- **mAP@0.5 is the headline**, but check `mAP@0.5:0.95` too — a model can win at
  the loose IoU threshold and localise poorly.
- **Read the Params column.** A larger model beating a smaller one is expected,
  not a discovery. YOLOv9s against YOLOv8n is not a like-for-like fight.
- **Watch the rare classes.** With 34 test images, `bunchy_top` and `panama`
  have very few ground-truth boxes, so their per-class mAP swings hard on single
  detections. The per-class table shows instance counts for exactly this reason.
- **A test split this small has wide error bars.** Treat small gaps between
  contenders as noise, and prefer the model that also wins per-class.

---

## Related docs

- [`MODEL_TRAINING.md`](MODEL_TRAINING.md) — training the deployed detector
- [`SECONDARY_DATASETS.md`](SECONDARY_DATASETS.md) — improving accuracy with more data
- [`TESTING_RESULTS.md`](TESTING_RESULTS.md) — validation results for the deployed model
