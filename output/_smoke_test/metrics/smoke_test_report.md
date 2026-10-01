# AgriVision — TEST Set Validation Report

**Generated:** 2026-08-03T00:00:00+00:00  
**Weights:** `models/best.pt`  
**Dataset:** `datasets/yolo_banana`  
**Split:** test (34 images, 468 instances)

## Overall metrics

| Precision | Recall | F1-Score | mAP@0.5 | mAP@0.5:0.95 |
|---:|---:|---:|---:|---:|
| 0.500 | 0.250 | 0.330 | 0.200 | 0.060 |

## Per-class metrics (test set)

| Class | Images | Instances | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `black_sigatoka` | 8 | 9 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `bunchy_top` | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `healthy` | 34 | 410 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `panama` | 18 | 49 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## Dataset composition (held-out split)

| Class | Images containing class | Bounding boxes |
|---|---:|---:|
| `black_sigatoka` | 8 | 9 |
| `bunchy_top` | 0 | 0 |
| `healthy` | 34 | 410 |
| `panama` | 18 | 49 |

*Regenerate with `python tools/evaluate_test_set.py` or `python tools/evaluate_test_set.py --split val`.*
