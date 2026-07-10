# AgriVision — Entity-Relationship Diagram (ERD)

**System:** Drone-Based Banana Disease Detection and Crop Stress Mapping  
**Model type:** Conceptual / logical ERD (no relational DB at runtime)  
**Persistence:** In-memory during live runs + file exports under `output/reports/`

---

## 1. Overview (high level)

This simplified view is suitable for **outline defense slides** and thesis chapter introductions.

```mermaid
erDiagram
    VIDEO_SOURCE ||--|| LIVE_SESSION : configures
    LIVE_SESSION ||--o{ VIDEO_FRAME : captures
    VIDEO_FRAME ||--|| PREPROCESSED_FRAME : preprocesses
    PREPROCESSED_FRAME ||--o{ DETECTION : yields
    PREPROCESSED_FRAME ||--|| STRESS_MAP : yields
    YOLO_MODEL ||--o{ DETECTION : powers
    DISEASE_CLASS ||--o{ DETECTION : classifies
    DETECTION ||--|| HEALTH_SUMMARY : aggregates
    PREPROCESSED_FRAME ||--o| FIELD_REPORT : exports
    FIELD_REPORT ||--|{ REPORT_ARTIFACT : contains
    TRAINING_DATASET ||--o{ TRAINING_RUN : trains
    TRAINING_RUN ||--|| YOLO_MODEL : produces
```

| # | Entity | One-line role |
|---|--------|----------------|
| 1 | **VIDEO_SOURCE** | Built-in mirror (iOS AirPlay / Android scrcpy) |
| 2 | **LIVE_SESSION** | Rolling stats for one Start→Stop run |
| 3 | **VIDEO_FRAME** | Raw BGR frame from capture |
| 4 | **PREPROCESSED_FRAME** | Denoised, CLAHE, aligned frame |
| 5 | **YOLO_MODEL** | `models/best.pt` weights |
| 6 | **DISEASE_CLASS** | Banana disease taxonomy |
| 7 | **DETECTION** | One bounding box from YOLO |
| 8 | **STRESS_MAP** | ExG vegetation stress grid |
| 9 | **HEALTH_SUMMARY** | Healthy / Stressed / Diseased counts |
| 10 | **FIELD_REPORT** | Export bundle on Capture Frame |
| 11 | **REPORT_ARTIFACT** | JPG, PNG, JSON, CSV files |
| 12 | **TRAINING_DATASET** | Offline labeled images |
| 13 | **TRAINING_RUN** | Ultralytics training job |

---

## 2. Detailed ERD — Live processing

```mermaid
erDiagram
    VIDEO_SOURCE {
        string source_id PK
        string platform "ios | android"
        string window_title
        string device_ip
        string quality
        datetime configured_at
    }

    LIVE_SESSION {
        string session_id PK
        string source_id FK
        datetime started_at
        int frames_processed
        int frames_analyzed
        int peak_detections
    }

    VIDEO_FRAME {
        string frame_id PK
        string session_id FK
        int width
        int height
        datetime captured_at
    }

    PREPROCESSED_FRAME {
        string frame_id PK
        string parent_frame_id FK
        datetime processed_at
        bool denoise_applied
        bool clahe_applied
        bool align_applied
    }

    YOLO_MODEL {
        string model_id PK
        string file_path
        string architecture "yolov8"
        datetime loaded_at
    }

    DISEASE_CLASS {
        int class_id PK
        string name
        string ui_category "healthy|stressed|diseased"
    }

    DETECTION {
        string detection_id PK
        string frame_id FK
        int class_id FK
        float confidence
        int bbox_x1
        int bbox_y1
        int bbox_x2
        int bbox_y2
        string label
    }

    STRESS_MAP {
        string map_id PK
        string frame_id FK
        string algorithm "ExG"
        float min_value
        float max_value
    }

    HEALTH_SUMMARY {
        string summary_id PK
        string frame_id FK
        int total_count
        int healthy_count
        int stressed_count
        int diseased_count
        float health_percentage
    }

    ACTIVITY_LOG {
        string log_id PK
        string session_id FK
    }

    LOG_ENTRY {
        string entry_id PK
        string log_id FK
        datetime timestamp
        string message
    }

    VIDEO_SOURCE ||--|| LIVE_SESSION : "1 active config"
    LIVE_SESSION ||--o{ VIDEO_FRAME : "1:N per tick"
    VIDEO_FRAME ||--|| PREPROCESSED_FRAME : "1:1"
    PREPROCESSED_FRAME ||--o{ DETECTION : "1:N"
    PREPROCESSED_FRAME ||--|| STRESS_MAP : "1:1"
    YOLO_MODEL ||--o{ DETECTION : "1:N"
    DISEASE_CLASS ||--o{ DETECTION : "1:N"
    PREPROCESSED_FRAME ||--|| HEALTH_SUMMARY : "1:1 rollup"
    LIVE_SESSION ||--|| ACTIVITY_LOG : "1:1"
    ACTIVITY_LOG ||--|{ LOG_ENTRY : "1:N"
```

---

## 3. Detailed ERD — Reports & export

```mermaid
erDiagram
    PREPROCESSED_FRAME {
        string frame_id PK
    }

    FIELD_REPORT {
        string report_id PK
        string frame_id FK
        string session_id FK
        string video_source
        datetime exported_at
        json geo "lat, lon, alt (planned)"
        json detection_summary
        json vegetation_summary
    }

    REPORT_ARTIFACT {
        string artifact_id PK
        string report_id FK
        string artifact_type "frame|stress|json|csv"
        string file_path
        datetime saved_at
    }

    PREPROCESSED_FRAME ||--o| FIELD_REPORT : "on Capture Frame"
    FIELD_REPORT ||--|{ REPORT_ARTIFACT : "1:4 typical"
```

**Export paths (implemented):**

| artifact_type | Example path |
|---------------|--------------|
| frame | `output/reports/agrivision_YYYYMMDD_HHMMSS_frame.jpg` |
| stress | `output/reports/agrivision_YYYYMMDD_HHMMSS_stress.png` |
| json | `output/reports/agrivision_YYYYMMDD_HHMMSS_report.json` |
| csv | `output/reports/agrivision_YYYYMMDD_HHMMSS_report.csv` |

---

## 4. Detailed ERD — Offline training

```mermaid
erDiagram
    DISEASE_CLASS {
        int class_id PK
        string name
    }

    TRAINING_DATASET {
        string dataset_id PK
        string name "yolo_banana"
        string root_path
    }

    TRAINING_IMAGE {
        string image_id PK
        string dataset_id FK
        string file_path
        string split "train|val"
    }

    YOLO_LABEL {
        string label_id PK
        string image_id FK
        int class_id FK
        float x_center
        float y_center
        float width
        float height
    }

    TRAINING_RUN {
        string run_id PK
        string dataset_id FK
        int epochs
        string output_path
        datetime completed_at
    }

    YOLO_MODEL {
        string model_id PK
        string file_path
    }

    TRAINING_DATASET ||--|{ TRAINING_IMAGE : "1:N"
    TRAINING_IMAGE ||--|| YOLO_LABEL : "1:1 per box"
    DISEASE_CLASS ||--o{ YOLO_LABEL : "1:N"
    TRAINING_DATASET ||--o{ TRAINING_RUN : "1:N"
    TRAINING_RUN ||--|| YOLO_MODEL : "produces best.pt"
```

### Disease classes (`datasets/yolo_banana/data.yaml`)

| class_id | name | UI category |
|----------|------|-------------|
| 0 | black_sigatoka | Stressed |
| 1 | healthy | Healthy |
| 2 | moko | Diseased |
| 3 | panama | Diseased |

---

## 5. Color legend (draw.io / thesis figures)

| Color | Domain | Entities |
|-------|--------|----------|
| Blue | Input & capture | VIDEO_SOURCE, LIVE_SESSION, VIDEO_FRAME, PREPROCESSED_FRAME |
| Green | Analysis | DETECTION, STRESS_MAP, HEALTH_SUMMARY |
| Yellow | Reference data | DISEASE_CLASS, YOLO_MODEL |
| Red / coral | UI & logging | ACTIVITY_LOG, LOG_ENTRY |
| Orange | Export | FIELD_REPORT, REPORT_ARTIFACT |
| Purple | Offline training | TRAINING_DATASET, TRAINING_IMAGE, YOLO_LABEL, TRAINING_RUN |

---

## 6. Code mapping

| Entity | Implementation |
|--------|----------------|
| VIDEO_SOURCE | `ui/components/sidebar.py` |
| LIVE_SESSION | `backend/session.py` → `SessionRecorder` |
| VIDEO_FRAME | `utils/screen_capture.py`, `utils/cast_manager.py` |
| PREPROCESSED_FRAME | `core/preprocess.py` → `FramePreprocessor` |
| YOLO_MODEL | `core/detection.py` → `models/best.pt` |
| DETECTION | `core/detection.py`, `ui/inference_worker.py` |
| STRESS_MAP | `core/ndvi.py`, `core/processor.py` |
| HEALTH_SUMMARY | `utils/drawing.py`, `ui/components/sidebar.py` |
| FIELD_REPORT | `backend/report.py` → `export_field_report()` |
| ACTIVITY_LOG | `ui/components/sidebar.py` → `log_box` |
| TRAINING_* | `train.py`, `datasets/` |

---

## 7. Export for thesis

**Draw.io (recommended for Word/PDF):**  
Open [`diagrams/AgriVision-ERD.drawio`](diagrams/AgriVision-ERD.drawio) → **File → Export as → PNG (300 DPI)**.

**Mermaid (Markdown / GitHub):**  
Use the diagrams in this file directly, or paste into [mermaid.live](https://mermaid.live).

---

## 8. Notes for panel Q&A

1. **No SQL database** — the ERD documents *logical* entities; runtime data lives in memory and flat files.
2. **LIVE_SESSION** maps to `SessionRecorder` and is included in JSON reports.
3. **STRESS_MAP** uses ExG (RGB proxy); true multispectral NDVI is a planned extension (`geo` block in reports is reserved).
4. **HEALTH_SUMMARY** replaces the older split between `UI_HEALTH_CATEGORY` and `DETECTION_STATISTICS` for a cleaner model.
