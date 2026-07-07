# AgriVision — Secondary Datasets Plan

The primary dataset is **315 de-duplicated aerial banana images** (80-10-10
split) with heavy class imbalance: ~92% of boxes are `healthy`, while
`bunchy_top` has only three training boxes. This caps validation mAP@0.5 at
~0.177 overall and near-zero for rare diseases (see `docs/TESTING_RESULTS.md`).

Secondary datasets supplement the primary data to raise rare-class recall
without changing the deployed detector until a retraining run validates better.

## 1. Goals

- Raise recall on `panama`, `bunchy_top`, and `black_sigatoka`.
- Add close-range leaf imagery to support the two-stage classifier
  (`models/banana-cls.pt`, used when `AGRIVISION_INFER_MODE=both`).
- Keep the aerial detector's domain (top-down canopy view) intact — secondary
  data is blended, not substituted.

## 2. Candidate secondary sources

| Source | Type | Classes added | Notes |
|---|---|---|---|
| PlantVillage (banana subset) | Close-range leaf | Black/Yellow Sigatoka, healthy | Large, clean labels; classifier pretraining |
| Kaggle "Banana Leaf Disease" sets | Close-range leaf | Sigatoka, Panama, Cordana | Verify licenses; de-duplicate |
| Roboflow Universe banana-disease projects | Mixed / aerial | Varies | Some already in YOLO format |
| Field-collected oblique phone photos | Close-range | Panama, Moko, Bunchy Top | Targeted collection for the three weakest classes |
| Synthetic augmentation | Derived | Rare classes | Copy-paste / augmentation to rebalance boxes |

## 3. Integration workflow

1. Convert each source to YOLO format and remap labels to the AgriVision
   class set (`black_sigatoka`, `bunchy_top`, `healthy`, `panama`).
2. De-duplicate against the primary set (perceptual hash) to avoid leakage
   between train/val/test.
3. Merge using the existing tooling (`tools/merge_*`, `tools/split_yolo_dataset.py`),
   keeping the held-out test set primary-only for honest evaluation.
4. Rebalance: cap `healthy` or oversample rare classes so no class exceeds
   ~50% of boxes.
5. Retrain YOLOv8n into a new run directory, e.g.
   `runs/detect/runs/banana_disease_augmented/`.

## 4. Wiring results into the dashboard

The **Model Comparison** page reads `web/api/data/models.json`. The third
model, `yolov8n-augmented`, is defined but has no metrics yet. After a
retraining run, add its results CSV so metrics and training curves populate
automatically:

```json
{
  "id": "yolov8n-augmented",
  "name": "YOLOv8n — Primary + Secondary Datasets",
  "task": "detection",
  "weights": "models/best_augmented.pt",
  "status": "deployed",
  "results_csv": "runs/detect/runs/banana_disease_augmented/results.csv"
}
```

The API's `agrivision_reader.model_comparison()` parses the CSV, extracts best
and final mAP/precision/recall, and builds the per-epoch curve — no code
changes required, only the config entry.

## 5. Evaluation protocol

- Always evaluate on the **primary-only held-out test set** so improvements
  reflect real aerial performance, not secondary-domain memorization.
- Report per-class mAP@0.5 side by side with the deployed model.
- Only promote the augmented model to `models/best.pt` if overall and
  per-class rare-disease mAP both improve.
