# AgriVision — TEST Set Validation Report

**Generated:** 2026-08-03T12:46:28.832257+00:00  
**Weights:** `models\best.pt`  
**Dataset:** `datasets\yolo_banana`  
**Split:** test (31 images, 456 instances)

## Overall metrics

| Precision | Recall | F1-Score | mAP@0.5 | mAP@0.5:0.95 |
|---:|---:|---:|---:|---:|
| 0.519 | 0.253 | 0.340 | 0.204 | 0.064 |

## Per-class metrics (test set)

| Class | Images | Instances | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `black_sigatoka` | 12 | 23 | 0.218 | 0.130 | 0.163 | 0.061 | 0.023 |
| `bunchy_top` | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.064 |
| `healthy` | 31 | 410 | 0.340 | 0.629 | 0.441 | 0.431 | 0.133 |
| `panama` | 13 | 23 | 1.000 | 0.000 | 0.000 | 0.119 | 0.034 |

## Dataset composition (held-out split)

| Class | Images containing class | Bounding boxes |
|---|---:|---:|
| `black_sigatoka` | 12 | 23 |
| `bunchy_top` | 0 | 0 |
| `healthy` | 31 | 410 |
| `panama` | 13 | 23 |

*Regenerate with `python tools/evaluate_test_set.py` or `python tools/evaluate_test_set.py --split val`.*
