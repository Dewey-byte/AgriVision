## Three-model Keras-style results (AdamW)

| Model | Epochs | Accuracy | Recall | Precision | F1-Score |
|---|---:|---:|---:|---:|---:|
| YOLOv8n | 20 | 11.19% | 12.16 | 87.20 | 21.34 |
| YOLOv8n | 40 | 10.25% | 9.58 | 36.46 | 15.17 |
| YOLOv8n | 60 | 14.24% | 15.75 | 44.15 | 23.22 |
| YOLOv8n | 80 | 14.60% | 19.61 | 19.89 | 19.75 |
| YOLOv8n | 100 | 14.75% | 22.56 | 17.59 | 19.76 |
| **YOLOv8n Average** | | **13.00%** | **15.93** | **41.06** | **19.85** |
| YOLOv9t | 20 | 10.64% | 14.90 | 40.82 | 21.84 |
| YOLOv9t | 40 | 12.89% | 14.27 | 71.50 | 23.79 |
| YOLOv9t | 60 | 13.70% | 18.94 | 41.96 | 26.10 |
| YOLOv9t | 80 | 8.37% | 11.66 | 12.04 | 11.85 |
| YOLOv9t | 100 | 12.31% | 16.47 | 43.28 | 23.86 |
| **YOLOv9t Average** | | **11.58%** | **15.25** | **41.92** | **21.48** |
| YOLO-NAS S | 20 | 6.91% | 29.42 | 2.14 | 3.99 |
| YOLO-NAS S | 40 | 8.50% | 25.56 | 1.73 | 3.23 |
| YOLO-NAS S | 60 | 7.18% | 25.78 | 1.70 | 3.19 |
| YOLO-NAS S | 80 | 5.83% | 25.16 | 4.01 | 6.91 |
| YOLO-NAS S | 100 | 8.15% | 25.64 | 3.03 | 5.42 |
| **YOLO-NAS S Average** | | **7.31%** | **26.31** | **2.52** | **4.55** |

*Accuracy = validation mAP@0.5. Train accuracy is a Keras-style proxy `1 - train_loss / train_loss[0]`. YOLO-NAS has no DFL term, so its loss magnitude is not directly comparable to Ultralytics YOLO.*
