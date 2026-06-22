# AgriVision — Conceptual Framework

**System title:** A Drone-Based System for Detecting Banana Diseases and Mapping Crop Stress Using YOLOv8 and NDVI Image Analysis

**System type:** Desktop application (Python, PyQt5) with real-time computer vision. There is no web server, relational database, or user authentication layer.

### draw.io (diagrams.net)

Open in [draw.io](https://app.diagrams.net/) or the Draw.io desktop app. See also [`docs/diagrams/README.md`](diagrams/README.md).

**Separate files (recommended for thesis figures):**

| File | Section |
|------|---------|
| [`docs/diagrams/AgriVision-DFD.drawio`](diagrams/AgriVision-DFD.drawio) | **g.** DFD Level 0 + Level 1 (2 tabs) |
| [`docs/diagrams/AgriVision-Use-Case-Diagram.drawio`](diagrams/AgriVision-Use-Case-Diagram.drawio) | **h.** Use Case Diagram |
| [`docs/diagrams/AgriVision-ERD.drawio`](diagrams/AgriVision-ERD.drawio) | **i.** ERD (Conceptual) |

**All-in-one file (includes CFD + all above):**

[`docs/diagrams/AgriVision-Conceptual-Framework.drawio`](diagrams/AgriVision-Conceptual-Framework.drawio)

**Export for thesis/PDF:** File → Export as → PNG (300 DPI) or PDF.

---

## Overview

AgriVision ingests live drone video (via the built-in wireless phone mirror), preprocesses frames, runs YOLOv8 disease detection and ExG-based vegetation stress mapping, and presents results to a farm operator through a graphical interface.

| Layer | Description |
|-------|-------------|
| **External entities** | Farm operator, drone pilot, phone (iOS / Android), YOLO weights on disk |
| **Core processes** | Capture → Preprocess → Detect → Stress map → Visualize → Report |
| **Data persistence** | In-memory caches during runtime; optional JPEG export and offline training files |

---

## g. Context Flow Diagram (CFD) and Data Flow Diagram (DFD)

### g.1 Context Flow Diagram (CFD) — Level 0

The CFD shows AgriVision as a single process at the center of its environment.

```mermaid
flowchart TB
    subgraph External Entities
        OP[Farm Operator / Analyst]
        PILOT[Drone Pilot]
        PHONE[Drone Feed on Phone<br/>iPhone / Android]
        DISK[(Local Filesystem)]
    end

    SYS((0<br/>AgriVision<br/>Disease Detection &<br/>Stress Mapping System))

    OP -->|Configuration commands,<br/>start/stop processing| SYS
    SYS -->|Live feed, bounding boxes,<br/>detection summary, NDVI heatmap,<br/>activity log| OP

    PILOT -->|Mirrors phone screen| PHONE
    PHONE -->|Wireless screen mirror<br/>iOS AirPlay / Android scrcpy| SYS

    DISK -->|YOLO model weights<br/>models/best.pt| SYS
    SYS -->|Captured frame image<br/>captured_frame.jpg| DISK
    SYS -->|Training outputs<br/>runs/detect/| DISK
```

**CFD narrative**

| # | Entity | Interaction |
|---|--------|-------------|
| 1 | Farm Operator | Selects the mirror source (iOS / Android), starts/stops the feed, views detections and stress maps, captures frames |
| 2 | Drone Pilot | Mirrors the phone screen (showing the live drone feed) to AgriVision |
| 3 | Phone (iOS / Android) | Supplies the live screen via the built-in wireless mirror — AirPlay for iOS, scrcpy for Android — captured directly inside AgriVision |
| 4 | Local Filesystem | Stores model weights, captured snapshots, and offline training artifacts |

---

### g.2 Data Flow Diagram (DFD) — Level 0

```mermaid
flowchart LR
    OP[Farm Operator]

    P0((0<br/>AgriVision))

    MIRROR[Phone Screen Mirror<br/>AirPlay / scrcpy]
    MODEL[Model Weights<br/>D1]
    OUT_UI[Detection Results,<br/>Stress Map, Statistics]
    OUT_FILE[Captured Image<br/>D2]

    MIRROR -->|Live video frames| P0
    MODEL -->|best.pt| P0
    OP -->|Source config, start/stop| P0
    P0 -->|Annotated feed, counts, heatmap| OUT_UI
    OUT_UI --> OP
    P0 -->|JPEG snapshot| OUT_FILE
```

**Level 0 data stores**

| ID | Name | Description |
|----|------|-------------|
| D1 | Model Weights | YOLOv8 `.pt` file (`models/best.pt`) |
| D2 | Captured Frame | `captured_frame.jpg` written on demand |

---

### g.3 Data Flow Diagram (DFD) — Level 1

Decomposition of Process **0** into sub-processes aligned with the application modules.

```mermaid
flowchart TD
    OP[Farm Operator]
    SRC[Phone Screen Mirror<br/>AirPlay / scrcpy]

    P1((1.0<br/>Capture<br/>Video Frame))
    P2((2.0<br/>Preprocess<br/>Frame))
    P3((3.0<br/>Run ML<br/>Inference))
    P4((4.0<br/>Compute<br/>Stress Map))
    P5((5.0<br/>Visualize &<br/>Aggregate))
    P6((6.0<br/>Export<br/>Frame))

    D_CACHE[(D3: Cached<br/>Detections)]
    D_STRESS[(D4: Cached<br/>Stress Map)]
    D_MODEL[(D1: YOLO<br/>Weights)]
    D_CAPTURE[(D2: Captured<br/>Image)]

    OP -->|Start/stop, source settings| P1
    SRC -->|Raw BGR frame| P1
    P1 -->|Raw frame| P2
    P2 -->|Preprocessed frame| P3
    P2 -->|Preprocessed frame| P4
    D_MODEL --> P3
    P3 -->|Detection list| D_CACHE
    P4 -->|Stress array| D_STRESS
    D_CACHE --> P5
    D_STRESS --> P5
    P2 -->|Preprocessed frame| P5
    P5 -->|UI frames, stats, log| OP
    OP -->|Capture command| P6
    P2 -->|Frame to save| P6
    P6 -->|JPEG file| D_CAPTURE
```

**Level 1 process specifications**

| Process | Name | Module | Input | Output |
|---------|------|--------|-------|--------|
| 1.0 | Capture Video Frame | `utils/screen_capture.py`, `utils/cast_manager.py` | Mirror window (iOS/Android) | Raw BGR `numpy` frame |
| 2.0 | Preprocess Frame | `core/preprocess.py` | Raw frame | Denoised, CLAHE-enhanced, aligned, resized frame |
| 3.0 | Run ML Inference | `core/detection.py`, `ui/inference_worker.py` | Preprocessed frame + weights | Bounding boxes, confidence, class labels |
| 4.0 | Compute Stress Map | `core/ndvi.py`, `core/processor.py` | Preprocessed frame | ExG-derived normalized stress map |
| 5.0 | Visualize & Aggregate | `utils/drawing.py`, `ui/main_window.py`, `ui/components/sidebar.py` | Frame, detections, stress map | Overlaid feed, Healthy/Stressed/Diseased counts, NDVI heatmap, activity log |
| 6.0 | Export Frame | `ui/main_window.py` | Preprocessed frame | `captured_frame.jpg` |

**Data dictionary (key flows)**

| Data flow | Composition |
|-----------|-------------|
| Raw BGR frame | `H × W × 3` uint8 array from OpenCV |
| Preprocessed frame | Same shape after denoise, CLAHE, temporal alignment, resize |
| Detection list | `[{bbox, confidence, class, label}, ...]` |
| Stress map | `H × W` float array (ExG index) |
| Detection statistics | `{total, healthy, stressed, diseased}` aggregated from YOLO labels |

---

## h. Use Case Diagram

```mermaid
flowchart TB
    subgraph Actors
        OP((Farm Operator<br/>/ Analyst))
        PILOT((Drone Pilot))
    end

    subgraph AgriVision System Boundary
        UC1[UC01: Select Mirror Source iOS/Android]
        UC2[UC02: Start Live Processing]
        UC3[UC03: Stop Live Processing]
        UC4[UC04: View Live Feed with Detections]
        UC5[UC05: View Detection Summary]
        UC6[UC06: View NDVI Stress Heatmap]
        UC7[UC07: Capture Frame to Disk]
        UC8[UC08: Monitor Activity Log]
        UC9[UC09: Train YOLO Model Offline]
    end

    subgraph Built-in Mirror Setup
        UC10[UC10: Mirror Android via scrcpy]
        UC11[UC11: Start Built-in Mirror Receiver]
        UC12[UC12: Mirror iPhone via AirPlay]
    end

    OP --- UC1
    OP --- UC2
    OP --- UC3
    OP --- UC4
    OP --- UC5
    OP --- UC6
    OP --- UC7
    OP --- UC8
    OP --- UC9
    OP --- UC11
    OP --- UC12

    PILOT --- UC10

    UC2 -.include.-> UC4
    UC2 -.include.-> UC5
    UC2 -.include.-> UC6
    UC4 -.include.-> UC5
    UC10 -.-> UC11
    UC11 -.-> UC2
    UC12 -.-> UC2
    UC1 -.extend.-> UC2
```

### Use case descriptions

| ID | Use case | Actor | Description | Preconditions | Postconditions |
|----|----------|-------|-------------|---------------|----------------|
| UC01 | Select Mirror Source | Farm Operator | Choose iOS (AirPlay) or Android (scrcpy); set device IP / window title and quality | AgriVision launched | Source mode stored in UI |
| UC02 | Start Live Processing | Farm Operator | Enable capture timer and background inference worker | Video source available | Live feed updating with overlays |
| UC03 | Stop Live Processing | Farm Operator | Stop timer and release capture handles | Processing active | Feed frozen; resources released |
| UC04 | View Live Feed with Detections | Farm Operator | See video with bounding boxes (Healthy / Stressed / Diseased colors) | UC02 active | Real-time visual feedback |
| UC05 | View Detection Summary | Farm Operator | Sidebar shows total detections and health breakdown bar | Detections returned | Counts refreshed each frame cycle |
| UC06 | View NDVI Stress Heatmap | Farm Operator | Sidebar shows JET colormap of ExG stress index | Stress map computed | Heatmap preview updated |
| UC07 | Capture Frame to Disk | Farm Operator | Save current preprocessed frame as JPEG | Frame available | `captured_frame.jpg` written |
| UC08 | Monitor Activity Log | Farm Operator | Read timestamped log in sidebar | Any operation | Log entry appended |
| UC09 | Train YOLO Model Offline | Farm Operator | Run `train.py` to prepare dataset and fine-tune YOLOv8 | Labeled images in `datasets/` | New weights under `runs/detect/` |
| UC10 | Mirror Android via scrcpy | Drone Pilot | Connect the Android phone over USB or Wi-Fi (Wireless debugging); AgriVision launches scrcpy | Phone debugging enabled | Low-latency Android mirror window available |
| UC11 | Start Built-in Mirror Receiver | Farm Operator | Click "Start Mirror" — AgriVision auto-launches and manages the receiver (scrcpy / AirPlay) | scrcpy / AirPlay receiver installed | Mirror receiver running, feed targeted |
| UC12 | Mirror iPhone via AirPlay | Farm Operator | Use iOS Control Center → Screen Mirroring to the built-in AirPlay receiver | AirPlay receiver running | Capturable iPhone window available |

**Authentication:** Not applicable. The system runs locally with a single operator and no login module.

---

## i. Entity-Relationship Diagram (ERD)

> **Updated clean ERD:** See **[docs/ERD.md](ERD.md)** for the presentable thesis version and **[diagrams/AgriVision-ERD.drawio](diagrams/AgriVision-ERD.drawio)** for export to PNG/PDF.

AgriVision does **not** use a relational database at runtime. The ERD below is a **conceptual (logical) model** of domain entities, in-memory structures, and file-based artifacts. It is suitable for documentation and for a future persistence layer if one is added.

```mermaid
erDiagram
    VIDEO_SOURCE ||--o{ VIDEO_FRAME : produces
    VIDEO_FRAME ||--|| PREPROCESSED_FRAME : "undergoes preprocessing"
    PREPROCESSED_FRAME ||--o{ DETECTION : "yields"
    PREPROCESSED_FRAME ||--|| STRESS_MAP : "yields"
    YOLO_MODEL ||--o{ DETECTION : generates
    DISEASE_CLASS ||--o{ DETECTION : classifies
    DETECTION }o--|| UI_HEALTH_CATEGORY : "aggregated into"
    UI_HEALTH_CATEGORY ||--o{ DETECTION_STATISTICS : summarizes
    PREPROCESSED_FRAME ||--o| CAPTURED_FRAME : "exported as"
    TRAINING_DATASET ||--|{ TRAINING_IMAGE : contains
    TRAINING_IMAGE ||--|| YOLO_LABEL : annotated_by
    DISEASE_CLASS ||--o{ YOLO_LABEL : references
    TRAINING_DATASET ||--o{ TRAINING_RUN : trains
    TRAINING_RUN ||--|| YOLO_MODEL : produces
    ACTIVITY_LOG ||--|{ LOG_ENTRY : contains

    VIDEO_SOURCE {
        string source_id PK
        string platform "ios|android"
        string window_title
        string device_ip
        string quality
        datetime started_at
    }

    VIDEO_FRAME {
        string frame_id PK
        string source_id FK
        int height
        int width
        datetime captured_at
    }

    PREPROCESSED_FRAME {
        string frame_id PK
        string parent_frame_id FK
        datetime processed_at
    }

    YOLO_MODEL {
        string model_id PK
        string file_path
        string version
        datetime loaded_at
    }

    DISEASE_CLASS {
        int class_id PK
        string name
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

    UI_HEALTH_CATEGORY {
        string category PK
        string value "healthy|stressed|diseased"
    }

    DETECTION_STATISTICS {
        string stats_id PK
        string frame_id FK
        int total_count
        int healthy_count
        int stressed_count
        int diseased_count
        float health_percentage
    }

    STRESS_MAP {
        string map_id PK
        string frame_id FK
        string algorithm "ExG"
        float min_value
        float max_value
    }

    CAPTURED_FRAME {
        string capture_id PK
        string frame_id FK
        string file_path
        datetime saved_at
    }

    TRAINING_DATASET {
        string dataset_id PK
        string name
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

    ACTIVITY_LOG {
        string log_id PK
    }

    LOG_ENTRY {
        string entry_id PK
        string log_id FK
        datetime timestamp
        string message
    }
```

### Entity reference

| Entity | Role in system | Persistence |
|--------|------------------|-------------|
| **VIDEO_SOURCE** | Built-in mirror configuration (iOS AirPlay / Android scrcpy) | UI state (transient) |
| **VIDEO_FRAME** | Single captured frame from source | Memory (per tick) |
| **PREPROCESSED_FRAME** | Frame after denoise, CLAHE, alignment | Memory |
| **YOLO_MODEL** | Trained weights for inference | `models/best.pt` |
| **DISEASE_CLASS** | ML taxonomy: black_sigatoka, healthy, moko, panama | `datasets/yolo_banana/data.yaml` |
| **DETECTION** | One YOLO bounding box result | `_cached_dets` in memory |
| **UI_HEALTH_CATEGORY** | Three-tier rollup: Healthy, Stressed, Diseased | `utils/drawing.py` mapping rules |
| **DETECTION_STATISTICS** | Sidebar counts and health bar | UI labels (transient) |
| **STRESS_MAP** | ExG-derived vegetation stress grid | `_last_stress` in memory |
| **CAPTURED_FRAME** | Operator-saved snapshot | `captured_frame.jpg` |
| **TRAINING_DATASET / TRAINING_IMAGE / YOLO_LABEL** | Offline supervised learning data | `datasets/` folder tree |
| **TRAINING_RUN** | Ultralytics training output | `runs/detect/` |
| **ACTIVITY_LOG / LOG_ENTRY** | Timestamped operational messages | `Sidebar.log_box` (transient) |

### Disease class reference (from `data.yaml`)

| class_id | name | Typical UI category |
|----------|------|---------------------|
| 0 | black_sigatoka | Stressed |
| 1 | healthy | Healthy |
| 2 | moko | Diseased |
| 3 | panama | Diseased |

Label-to-category mapping also considers substring rules in `utils/drawing.py` (e.g., sigatoka → Stressed, panama → Diseased).

---

## Relationship to IPO / System Architecture

| Conceptual artifact | Maps to |
|--------------------|---------|
| CFD external entities | Operators, phone (iOS/Android mirror), filesystem |
| DFD Process 3.0 | YOLOv8 inference (`core/detection.py`) |
| DFD Process 4.0 | ExG / NDVI proxy (`core/ndvi.py`) |
| Use cases UC02–UC06 | Main window timer loop (`ui/main_window.py`) |
| ERD DETECTION + DISEASE_CLASS | YOLO output + `data.yaml` classes |

---

## Files referenced

| Component | Path |
|-----------|------|
| Application entry | `main.py` |
| Main orchestration | `ui/main_window.py` |
| Inference worker | `ui/inference_worker.py` |
| Detection | `core/detection.py` |
| Stress / ExG | `core/ndvi.py` |
| Preprocessing | `core/preprocess.py` |
| Drawing / categories | `utils/drawing.py` |
| Built-in mirror manager | `utils/cast_manager.py` |
| Screen capture | `utils/screen_capture.py` |
| Class definitions | `datasets/yolo_banana/data.yaml` |
| Training | `train.py` |

---

*Document version: 1.0 — aligned with AgriVision codebase structure.*
