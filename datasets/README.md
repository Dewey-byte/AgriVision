# Datasets

Old training data and exports were removed. Add your new Label Studio labels here.

## Expected layout (after export)

```
datasets/yolo_banana/
  data.yaml
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
```

After merging exports, apply an **80-10-10** partition:

```powershell
python tools/split_yolo_dataset.py --dataset datasets/yolo_banana
```

## Export from Label Studio

1. In Label Studio: **Export → JSON** (not YOLO, if you use Local Files on Windows).
2. Run:

```powershell
python tools/label_studio/export_yolo.py `
  --json path\to\export.json `
  --local-files-root "C:\path\to\your\images" `
  --output datasets/yolo_banana
```

Or pull directly from a running Label Studio project (see `tools/label_studio/export_yolo.py`).

## Train

**Jupyter notebook (recommended for interactive training):**

```powershell
jupyter notebook notebooks/train_banana_yolo.ipynb
```

See [docs/MODEL_TRAINING.md](../docs/MODEL_TRAINING.md) for the full workflow.

**Command line:**

```powershell
python train.py --epochs 50
```

Weights are copied to `models/best.pt` when training finishes.
