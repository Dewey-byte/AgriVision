## Three-model Keras-style results (AdamW)

| Model | Epochs | Accuracy | Recall | Precision | F1-Score |
|---|---:|---:|---:|---:|---:|
| YOLOv9s | 20 | 13.71% | 15.65 | 68.46 | 25.48 |
| YOLOv9s | 40 | 9.65% | 13.20 | 64.75 | 21.93 |
| YOLOv9s | 60 | 10.91% | 14.90 | 17.61 | 16.14 |
| YOLOv9s | 80 | 10.06% | 14.00 | 43.72 | 21.21 |
| YOLOv9s | 100 | 11.43% | 14.55 | 70.49 | 24.12 |
| **YOLOv9s Average** | | **11.15%** | **14.46** | **53.00** | **21.77** |

*Accuracy = validation mAP@0.5. Train accuracy is a Keras-style proxy `1 - train_loss / train_loss[0]`. YOLO-NAS has no DFL term, so its loss magnitude is not directly comparable to Ultralytics YOLO.*
