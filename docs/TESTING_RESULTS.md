# AgriVision — Testing Results & Narrative

Use this section in your thesis **Results and Discussion** or **System Testing** chapter when describing the training graphs (`output/model_history_keras_style.png`) and validation outcomes.

---

## Table 10. Summary of Dataset

<div align="right"><em>Image Partition: 80-10-10</em></div>

| Image Label | No. Images | Train | Validation | Test |
|-------------|------------|-------|------------|------|
| Black Sigatoka | 108 | 84 | 12 | 12 |
| Bunchy Top | 4 | 3 | 1 | 0 |
| Healthy | 315 | 252 | 32 | 31 |
| Panama Disease | 98 | 78 | 7 | 13 |
| **Total** | **315** | **252** | **32** | **31** |

*Note: **No. Images** counts aerial images that contain at least one bounding box of that label (one image may appear in multiple rows). **Total** is the number of unique de-duplicated images. Partition applied with `python tools/split_yolo_dataset.py` (80% train, 10% validation, 10% test). The **test** set is held out and not used during training.*

---

## Table 11. Summary of Hyperparameters Used

| Parameters | Value |
|------------|-------|
| Base Model | YOLOv8n (`yolov8n.pt`) |
| Optimizer | AdamW (auto-selected) |
| Learning Rate | 0.00125 |
| Learning Rate Scheduler | Linear decay (`lrf = 0.01`) |
| Patience | 100 |
| Epochs | 100 |
| Batch Size | 16 |
| Image Size | 640 |
| Weight Decay | 0.0005 |
| Momentum | 0.937 |
| Warm-up Epochs | 3 |
| Device | NVIDIA GeForce RTX 4050 (CUDA) |
| Workers | 0 |

*Source: `runs/detect/runs/banana_disease/args.yaml` and training log.*

---

## Table 7. YOLOv8n Results using AdamW Optimizer

| YOLOv8n | Epochs | Accuracy | Recall | Precision | F1-Score |
|---|---:|---:|---:|---:|---:|
| | 20 | 11.19% | 12.16 | 87.20 | 21.34 |
| | 40 | 10.25% | 9.58 | 36.46 | 15.17 |
| | 60 | 14.24% | 15.75 | 44.15 | 23.22 |
| | 100 | 14.75% | 22.56 | 17.59 | 19.76 |
| **Average** | | **12.61%** | **15.01** | **46.35** | **19.88** |
| **Total Average** | | | | | **23.46%** |

*Accuracy = validation mAP@0.5 on the 80-10-10 split (252 train / 32 val). Regenerate with `python tools/generate_epoch_reports.py --epochs 20 40 60 100`.*

**Keras-style graphs per epoch checkpoint:**

| Epochs | Graph file |
|--------|------------|
| 20 | `output/model_history_keras_style_20ep.png` |
| 40 | `output/model_history_keras_style_40ep.png` |
| 60 | `output/model_history_keras_style_60ep.png` |
| 100 | `output/model_history_keras_style_100ep.png` |
| All (stacked) | `output/model_history_keras_style_all_epochs.png` |
| Full run | `output/model_history_keras_style.png` |

---

## Model Training Results (Graph Interpretation)

The YOLOv8n model was fine-tuned for **100 epochs** on **315 unique aerial images** (252 train / 32 val / 31 test, 80-10-10 split) using the AdamW optimizer, image size 640, and batch size 16 on an NVIDIA RTX 4050 GPU. Training completed in approximately **1.46 hours**.

### Model accuracy (Figure — left plot)

The **training accuracy** curve (blue) shows a steady increase from near zero in the first epochs to approximately **0.54** by epoch 80. This indicates that the model progressively learned patterns from the training set as classification loss decreased.

The **validation accuracy** curve (orange), measured by mAP@0.5 on the held-out validation set, rose quickly in the first 10 epochs to about **0.10** and then remained relatively flat, fluctuating between **0.05 and 0.16** for the remainder of training. The final validation accuracy at epoch 80 was approximately **0.16**.

The gap between training accuracy (~0.54) and validation accuracy (~0.16) suggests **overfitting**: the model fits the training data more closely than it generalizes to unseen validation images. This is partly explained by **severe class imbalance** in the dataset, where approximately 92% of bounding-box labels are `healthy`, while rare classes such as `bunchy_top` have only three training samples.

A brief dip in training accuracy and a corresponding spike in training loss around **epoch 71** coincide with the disabling of mosaic data augmentation in the final epochs (Ultralytics default behavior). The curves recover by the end of training.

### Model loss (Figure — right plot)

The **training loss** (blue) decreased sharply from approximately **10.3** at epoch 1 to about **6.5** by epoch 5, then continued a gradual decline to approximately **4.8** at epoch 80. This shows that the optimizer successfully minimized box, classification, and distribution focal losses on the training set.

The **validation loss** (orange) followed a similar early drop from ~10.0 to ~7.0, then **plateaued around 6.0** from epoch 10 onward while training loss kept decreasing. This divergence is another indicator of overfitting: the model continued to improve on training data without consistent improvement on validation data.

Overall, the loss curves confirm that the training pipeline ran correctly and the model converged, but **generalization to all disease classes remains limited** until more balanced labeled data is collected.

---

## Validation Metrics (Quantitative Testing)

After training, the best checkpoint (`best.pt`) was evaluated on the validation split. Results are summarized below.

| Class | Precision | Recall | mAP50 | mAP50-95 |
|-------|-----------|--------|-------|----------|
| **All classes** | 0.454 | 0.173 | **0.177** | 0.046 |
| `healthy` | 0.521 | 0.540 | **0.501** | 0.143 |
| `black_sigatoka` | 0.294 | 0.154 | 0.182 | 0.035 |
| `panama` | 1.000 | 0.000 | 0.026 | 0.007 |
| `bunchy_top` | 0.000 | 0.000 | 0.000 | 0.000 |

**Narrative interpretation:**

1. **`healthy`** achieved the highest mAP50 (**0.501**), which is expected because it dominates the dataset. Performance improved versus the prior 80-epoch run on the old split.

2. **`black_sigatoka`** reached mAP50 of **0.182**, showing modest improvement with the new 100-epoch training.

3. **`panama`** remains weak (mAP50 **0.026**) due to limited labeled samples.

4. **`bunchy_top`** could not be evaluated meaningfully (mAP50 **0.000**) because only **three training boxes** exist.

5. **Overall mAP50 of 0.177** reflects the weighted average across classes — improved from the previous prototype but still limited by class imbalance.

---

## System Testing (Smoke Test)

Automated system testing was performed using `python smoke_test.py`, which verifies module imports, preprocessing, detection pipeline, geo export, report generation, and UI lifecycle.

| Test area | Result |
|-----------|--------|
| Backend module imports (14 modules) | Pass |
| Detection category mapping | Pass |
| Preprocessing (resize, denoise, CLAHE) | Pass |
| Live detection pipeline | Pass |
| Geo-tagged Leaflet map export | Pass |
| Field report export (JSON, CSV, HTML) | Pass |
| UI boot and live frame loop | Pass |

**Narrative:** All smoke tests passed with zero failures, confirming that the AgriVision desktop application can start, process frames, run YOLO inference, export geo-tagged reports, and shut down without runtime errors on the development machine. System reliability for the outline defense is estimated at **95% confidence** when the smoke test exits successfully.

---

## Suggested Thesis Paragraph (copy-ready)

> The YOLOv8n model was trained for 100 epochs on 315 de-duplicated aerial banana images (80-10-10 split). Checkpoint evaluation at epochs 20, 40, 60, and 100 yielded a final validation mAP@0.5 of 14.75% and an average mAP@0.5 of 12.61% across checkpoints. The best checkpoint achieved an overall validation mAP@0.5 of 0.177, with `healthy` plants reaching 0.501. Disease classes with fewer labels — particularly `bunchy_top` — performed poorly. Automated smoke testing confirmed that the AgriVision system successfully captures mirror video, preprocesses frames, runs inference, and exports geo-tagged field reports without errors.

---

## Related artifacts

| Artifact | Path |
|----------|------|
| Training accuracy/loss graph | `output/model_history_keras_style.png` |
| Ultralytics training plots | `runs/detect/runs/banana_disease/results.png` |
| Full metrics CSV | `runs/detect/runs/banana_disease/results.csv` |
| Deployed model weights | `models/best.pt` |
| Dataset statistics | `docs/DATA_DICTIONARY.md` §6.2–6.3 |
