# AgriVision — Architecture Benchmark (YOLOv8 vs YOLOv9)

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

---

## Layout

| Piece | Path |
|---|---|
| Contender declarations | `web/api/data/models.json` → `benchmark.contenders` |
| Training | `train.py --model <weights> --name <run> --no-deploy` |
| Scoring | `tools/benchmark_models.py` |
| Per-model results | `output/metrics/benchmarks/<model-id>.json` |
| API | `GET /api/analytics/models` → `benchmark` |
| Dashboard page | `web/frontend/src/pages/ModelComparison.jsx` |

`benchmark_models.py` never reads a model's own training logs to decide
accuracy. It re-runs validation on the test split so all contenders are measured
by the same code path.

---

## Reproducing the benchmark

Stop the desktop app first — training needs the whole GPU.

### 1. Train the contenders

`--no-deploy` matters: without it, `train.py` copies its result over
`models/best.pt` and silently swaps the model the desktop app serves.

```powershell
python train.py --model yolov8n.pt --name bench_yolov8n --epochs 100 --batch 16 --no-deploy
python train.py --model yolov9t.pt --name bench_yolov9t --epochs 100 --batch 16 --no-deploy
python train.py --model yolov9s.pt --name bench_yolov9s --epochs 100 --batch 16 --no-deploy
```

Ultralytics downloads base weights it does not find in the repo root.

### 2. Score everything on the held-out test split

```powershell
python tools/benchmark_models.py
```

It evaluates each contender, writes one JSON per model into
`output/metrics/benchmarks/`, and prints a leaderboard.

Useful flags:

| Flag | Effect |
|---|---|
| `--only <id>` | Score a single contender (repeatable) |
| `--split val` | Score the validation split instead of test |

### 3. Read the results in the dashboard

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

---

## Results

Scored on the 34-image held-out test split (468 boxes). Regenerate with
`python tools/benchmark_models.py`.

| # | Model | mAP@0.5 | mAP@0.5:0.95 | Precision | Recall | F1 | Params | Inference |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | **YOLOv9t** | **21.04%** | **6.56%** | 40.3% | 21.9% | 28.4% | 2.01 M | 7.9 ms |
| 2 | YOLOv9s | 19.29% | 5.92% | 66.4% | 21.8% | 32.8% | 7.29 M | 6.5 ms |
| 3 | YOLOv8n | 17.30% | 4.98% | 61.7% | 19.0% | 29.1% | 3.01 M | 2.9 ms |

Per-class mAP@0.5:

| Class | Test boxes | YOLOv9t | YOLOv9s | YOLOv8n |
|---|---:|---:|---:|---:|
| `healthy` | 410 | 38.7% | 37.6% | **40.1%** |
| `panama` | 49 | **16.1%** | 12.9% | 11.3% |
| `black_sigatoka` | 9 | **8.3%** | 7.4% | 0.5% |
| `bunchy_top` | 0 | not measurable | not measurable | not measurable |

**YOLOv9t is the most accurate**, winning on both mAP thresholds and on the two
rare disease classes, at roughly YOLOv8n's size (2.0M vs 3.0M parameters).

**YOLOv8n remains the fastest deployment choice**: it is within 4 points of
mAP@0.5, is the best model on `healthy` (the overwhelming majority of boxes),
and is more than twice as fast.

**YOLOv9s is the high-precision option.** It is the largest of the three (7.3M
parameters) and posts the highest precision and F1, at a cost in recall versus
YOLOv9t.

### Does the ranking hold on another split?

Yes. Re-scored on the 33-image validation split, the order is unchanged and the
gap is similar:

| Model | mAP@0.5 (test) | mAP@0.5 (val) |
|---|---:|---:|
| YOLOv9s | 19.29% | 14.86% |
| YOLOv8n | 17.30% | 13.46% |

Reproduce with `python tools/benchmark_models.py --split val`. That writes
`<id>.val.json` and leaves the published `<id>.json` test results — the ones the
dashboard shows — alone.

Note that `best.pt` was selected by validation fitness, so val is not an
independent measurement for either model. It is a consistency check, not a
second opinion.

### Caveats to state if you present these numbers

1. **`bunchy_top` is unmeasurable here.** The test split contains zero
   `bunchy_top` boxes, so its 0% is an absence of ground truth, not a model
   failure. The dashboard labels it "not measurable" rather than charting a zero.
2. **YOLOv9s is 2.4× the size of YOLOv8n** (7.29M vs 3.01M parameters). A larger
   model winning is the expected outcome, not a finding about YOLOv9's
   architecture. For a size-matched fight, benchmark `yolov9t.pt` (~2M) against
   YOLOv8n.
3. **YOLOv9's biggest per-class win rests on 9 boxes.** `black_sigatoka` at 8.3%
   vs 0.5% comes from a handful of detections in the test split; do not lean on
   that number as evidence.

Both Ultralytics runs stopped early on `patience=50` (YOLOv9s at epoch 63, best
at 13; YOLOv8n at epoch 67, best at 17), so neither was cut short while still
improving.

> Absolute mAP is low across the board because the dataset is small (593 training
> images) and dominated by `healthy`. The benchmark answers "which architecture
> is best *here*", not "is this model production-accurate". See
> [`SECONDARY_DATASETS.md`](SECONDARY_DATASETS.md) for raising the ceiling.

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
