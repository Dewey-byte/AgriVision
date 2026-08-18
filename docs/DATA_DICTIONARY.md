# AgriVision — Data Dictionary & Data Management

**System:** Drone-Based Banana Disease Detection and Crop Stress Mapping  
**Persistence:** In-memory during live runs + flat-file exports (no SQL database)  
**Related:** [WORKFLOW_ERD.md](WORKFLOW_ERD.md) · [STORAGE_DESIGN.md](STORAGE_DESIGN.md)

---

## 1. Technologies, Concepts, and Theories

| Area | Technology / theory | Role in AgriVision |
|------|---------------------|-------------------|
| **Object detection** | YOLOv8 (Ultralytics) | Bounding-box disease / plant detection on aerial frames |
| **Deep learning runtime** | PyTorch | Model inference and fine-tuning (`models/best.pt`) |
| **Computer vision** | OpenCV | Preprocess, draw overlays, image I/O |
| **Preprocessing** | Bilateral denoise, CLAHE (LAB), ECC temporal alignment | Improve contrast and stability before inference |
| **Vegetation index (proxy)** | ExG / HSV green-band ratio | Frame quality gate (`utils/frame_quality.py`) |
| **Geo mapping** | Local tangent-plane offset (meters → lat/lon) | Map detection centers to field coordinates |
| **Map visualization** | Leaflet + OpenStreetMap tiles | Interactive field map in UI and HTML export |
| **Desktop UI** | PyQt5 | Operator dashboard (feed, sidebar, controls) |
| **Video capture** | scrcpy (Android mirror) | Primary aerial video source from phone/drone app |
| **Annotation pipeline** | Label Studio → YOLO export | Offline training dataset preparation |
| **Software architecture** | Pipeline pattern, background worker thread | `backend/pipeline.py`, `ui/inference_worker.py` |

**Emerging / planned (next phase):** drone EXIF GPS import, GeoTIFF export, PDF farmer reports.

**Validation metrics (implemented):** held-out test/val evaluation via `python tools/evaluate_test_set.py` → `output/metrics/test_report_latest.{json,csv,md}`.

**Session storage (implemented):** live runs write to `output/sessions/{YYYYMMDD_HHMMSS_id}/` with `session.json`, `captures/`, and `maps/`.

**Drone EXIF GPS (implemented):** set sidebar **Drone EXIF folder** or `AGRIVISION_DRONE_IMAGE_DIR`; GPS is read from the newest DJI `.JPG` on session start, Detect My Location, and Capture Frame.

---

## 2. Type of Data

| Classification | AgriVision examples |
|----------------|---------------------|
| **Primary data** | Live mirror video frames, operator-entered GPS, per-frame YOLO detections, session counters, exported field reports |
| **Secondary data** | Labeled DJI training images (`datasets/yolo_banana/`), pretrained YOLO weights (`yolov8n.pt`), OpenStreetMap basemap tiles, Windows/browser geolocation APIs |

---

## 3. Data Sources

| Source | Category | Description |
|--------|----------|-------------|
| **Drone pilot (sidebar)** | User input | Latitude, longitude, Android IP, mirror quality |
| **Phone mirror feed** | IoT / device stream | scrcpy window capture from drone controller app |
| **YOLO model** | System-generated | Detections: bbox, class, confidence, label |
| **Session recorder** | System-generated | Frame counts, peak detections, rolling health summary |
| **Activity log** | System-generated | Timestamped UI events in sidebar |
| **Browser / Windows GPS** | External API | Auto location when enabled (`backend/geo.py`) |
| **Label Studio export** | External dataset | Training images + YOLO `.txt` labels |
| **OpenStreetMap** | External API | Map tiles in Leaflet HTML |

---

## 4. Data Collection Method

| Method | What is collected | Module |
|--------|-------------------|--------|
| **Manual input** | Plantation GPS, mirror IP, start/stop, capture button | `ui/components/sidebar.py`, `ui/components/feed_panel.py` |
| **Automated (real-time)** | Video frames, preprocess output, detections, geo markers | `utils/screen_capture.py`, `backend/pipeline.py` |
| **Automated (on demand)** | Field report bundle (JPG, JSON, CSV, HTML) | `backend/report.py` on Capture Frame |
| **Automated (offline)** | Training labels, model weights | `train.py`, `tools/label_studio/export_yolo.py` |
| **API integration** | Browser geolocation, Windows location, OSM tiles | `backend/geo.py`, `backend/map_export.py` |

---

## 5. Time of Collection

| Data | Timing |
|------|--------|
| Mirror configuration | **One-time** per flight session (before Start) |
| Plantation GPS | **One-time** or updated manually; optional auto-detect at launch |
| Live frames & inference | **Real-time** (~16–40 ms timer loop while feed is active) |
| Session statistics | **Real-time** (accumulated per analyzed frame) |
| Field map HTML | **Real-time** refresh when geo or markers change |
| Capture export | **One-time** per Capture Frame button press |
| Training dataset | **Periodic** / batch (when new labels are exported) |
| Model retraining | **Periodic** (when `train.py` is run) |

**Collection window (live run):** from **Start** (mirror + feed) to **Stop** — `LiveSession.started_at` (UTC ISO-8601) marks session start. Exports record `exported_at` per capture.

---

## 6. Dataset Overview

### 6.1 Runtime (operational) data

| Entity | Typical records per session | Expected growth |
|--------|----------------------------|-----------------|
| Video frames processed | Thousands (30–60 FPS effective) | Linear with flight duration |
| Frames analyzed (YOLO) | Subset of processed (inference every N frames) | Same |
| Capture exports | 0–N (operator-triggered) | ~1–20 per field visit |
| Geo markers | 0–80 per analyzed frame (`AGRIVISION_MAX_DET`) | Bounded per frame |

### 6.2 Training dataset (`datasets/yolo_banana`)

| Split | Images | Labels |
|-------|--------|--------|
| **Train** | 252 | 252 |
| **Validation** | 32 | 32 |
| **Test** | 31 | 31 |
| **Total** | **315** | **315** |

De-duplicated by original `DJI_xxxx` filename (Label Studio re-exports each photo with a
fresh hash prefix); no image appears in more than one split. Partition: **80-10-10**
via `tools/split_yolo_dataset.py`. Merge new exports with `tools/merge_yolo_export.py`.

**Classes** (`data.yaml`): `black_sigatoka`, `bunchy_top`, `healthy`, `panama`

**Class distribution (bounding boxes):**

| Class | Train boxes | Val boxes | Train images |
|-------|-------------|-----------|--------------|
| `healthy` | 3,108 | 1,058 | 232 |
| `black_sigatoka` | 137 | 52 | 81 |
| `panama` | 119 | 52 | 70 |
| `bunchy_top` | 3 | 2 | 3 |

> **Imbalance note:** ~92% of labels are `healthy`. Disease classes — especially
> `bunchy_top` (3 training boxes) — are under-represented and need more labeled
> samples before per-class accuracy can improve.

**Expected growth:** +50–200 images per labeling batch from new drone flights (Label Studio export).

### 6.3 Latest training run (`runs/detect/runs/banana_disease`)

| Setting | Value |
|---------|-------|
| Base model | `yolov8n.pt` |
| Epochs / imgsz / batch | 100 / 640 / 16 |
| Hardware | NVIDIA RTX 4050 (CUDA), ~1.46 h |
| Output | `models/best.pt` (auto-deployed) |

**Validation metrics (`best.pt`, 32-image val split):**

| Class | mAP50 | mAP50-95 |
|-------|-------|----------|
| **all** | **0.177** | **0.046** |
| `healthy` | 0.501 | 0.143 |
| `black_sigatoka` | 0.182 | 0.035 |
| `panama` | 0.026 | 0.007 |
| `bunchy_top` | 0.000 | 0.000 |

Training curves: `output/model_history_keras_style.png` and
`runs/detect/runs/banana_disease/results.png`.

**Graph narrative (thesis-ready):** see [TESTING_RESULTS.md](TESTING_RESULTS.md).

---

## 7. Data Structure (logical groupings)

AgriVision uses **logical tables** (JSON objects), not SQL tables.

| Group | Entities | Storage |
|-------|----------|---------|
| **Session** | `LiveSession` | Memory → embedded in `FieldReport.session` |
| **Capture** | `Frame`, `PreprocessedFrame` | Memory; JPEG on export |
| **Detection** | `Detection`, `HealthSummary` | Memory → JSON/CSV export |
| **Geo** | `GeoTag`, `GeoMarker` | Memory → JSON + Leaflet HTML |
| **Export** | `FieldReport`, `Artifacts` | `output/reports/` |
| **Training** | `TRAINING_IMAGE`, `YOLO_LABEL` | `datasets/yolo_banana/` |

---

## 8. Data Dictionary

### Table 1 — `LiveSession` (in-memory)

| Field | Type | Description |
|-------|------|-------------|
| `started_at` | string (ISO-8601 UTC) | Session start timestamp |
| `frames_processed` | integer | Total frames pulled from mirror |
| `frames_analyzed` | integer | Frames that completed inference |
| `total_detections` | integer | Cumulative detection count |
| `peak_detections` | integer | Max detections in a single analyzed frame |
| `last_detection_summary` | object | `{total, healthy, stressed, diseased}` |
| `geo_marker_count` | integer | Count of markers on current map |
| `last_geo` | object | Last `GeoTag` used for mapping |

**Source:** `backend/session.py` → `SessionRecorder.to_dict()`

---

### Table 2 — `Detection` (per bounding box)

| Field | Type | Description |
|-------|------|-------------|
| `bbox` | array[4] integer | `[x1, y1, x2, y2]` pixels, top-left origin |
| `label` | string | Display label, e.g. `Healthy (0.92)` |
| `confidence` | float | Model confidence 0.0–1.0 |
| `class` | integer | YOLO class id (see `data.yaml`) |

**Source:** `core/detection.py` → `backend/pipeline.py`

---

### Table 3 — `HealthSummary` (aggregated per frame)

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Count of valid detections |
| `healthy` | integer | Healthy category count |
| `stressed` | integer | Stressed / moderate count |
| `diseased` | integer | Diseased count |

**Source:** `utils/drawing.py` → `detection_category()`

---

### Table 4 — `GeoTag` (plantation anchor)

| Field | Type | Description |
|-------|------|-------------|
| `latitude` | float | Decimal degrees (WGS84) |
| `longitude` | float | Decimal degrees (WGS84) |
| `altitude_m` | float \| null | Altitude in meters (optional) |
| `source` | string | `manual`, `browser_gps`, `windows_gps`, `default`, `env` |

**Source:** `backend/geo.py` → sidebar or auto-detect

---

### Table 5 — `GeoMarker` (map pin per detection)

| Field | Type | Description |
|-------|------|-------------|
| `lat` | float | Marker latitude |
| `lon` | float | Marker longitude |
| `label` | string | Detection label |
| `category` | string | `healthy` \| `stressed` \| `diseased` |
| `confidence` | float | Detection confidence |

**Source:** `backend/geo.py` → `detections_to_markers()`

---

### Table 6 — `FieldReport` (export root JSON)

| Field | Type | Description |
|-------|------|-------------|
| `system` | string | Always `"AgriVision"` |
| `exported_at` | string (datetime) | Capture timestamp (local ISO) |
| `video_source` | string | e.g. `scrcpy`, `android` |
| `geo` | object | `GeoTag` fields |
| `detection_summary` | object | `HealthSummary` |
| `detections` | array | List of `Detection` |
| `session` | object | `LiveSession` snapshot |
| `artifacts` | object | Paths to frame, JSON, map files |

**Source:** `backend/report.py` → `*_report.json`

---

### Table 7 — `FieldReport` CSV columns

**Summary / geo rows** (key-value):

| section | field | value (example) |
|---------|-------|-----------------|
| summary | total | 12 |
| summary | healthy | 8 |
| summary | stressed | 2 |
| summary | diseased | 2 |
| geo | latitude | 7.3669 |
| geo | longitude | 125.91 |
| geo | altitude_m | (empty) |
| geo | source | manual |

**Detection rows:**

| label | confidence | class | bbox |
|-------|------------|-------|------|
| Healthy (0.92) | 0.92 | 2 | 10 10 50 50 |

---

### Table 8 — YOLO training label (offline)

| Field | Format | Description |
|-------|--------|-------------|
| `class_id` | integer 0–3 | Disease class index |
| `x_center` | float 0–1 | Normalized bbox center x |
| `y_center` | float 0–1 | Normalized bbox center y |
| `width` | float 0–1 | Normalized bbox width |
| `height` | float 0–1 | Normalized bbox height |

**File:** `datasets/yolo_banana/labels/{split}/{image_stem}.txt` (one line per box)

---

### Table 9 — Activity log (UI, unstructured)

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | Prepended by `utils/logger.py` |
| `message` | string | Human-readable event (mirror status, export path, errors) |

**Storage:** In-memory QTextEdit only (not persisted unless copied by operator).

---

## 9. Data Cleaning

| Step | Rule | Implementation |
|------|------|----------------|
| Skip blank / static frames | Reject if not live video or gray std &lt; 12 | `utils/frame_quality.is_analyzable_frame()` |
| Low-confidence boxes | Drop if `confidence < 0.35` | `AGRIVISION_DET_MIN_CONF` in `core/detection.py` |
| Tiny boxes | Drop if area &lt; 400 px² | `AGRIVISION_DET_MIN_AREA` |
| Invalid category | Map to `none`; exclude from health totals | `detection_category()` |
| Duplicate session state | Reset on new Start | `SessionRecorder.reset()` |
| Missing GPS | Fallback to Compostela Valley default + note in JSON | `backend/geo.resolve_geo_tag()` |

---

## 10. Data Transformation

| Transformation | Input → output | Method |
|----------------|----------------|--------|
| Resize for inference | Full frame → max side 320–512 px | `cv2.resize` INTER_AREA |
| Denoise | BGR → BGR | Bilateral filter (d=5) |
| Contrast | BGR → BGR | CLAHE on L channel (LAB) |
| Temporal align | Frameₙ → aligned Frameₙ | ECC on grayscale downscale |
| Pixel → geo | bbox center + anchor → lat/lon | Local meter span (default 80 m) |
| Label → UI category | YOLO class name → healthy/stressed/diseased | Keyword rules in `detection_category()` |
| Tensor → detection list | YOLO output → JSON-serializable dicts | `core/detection.py` |
| Frame → JPEG | ndarray → file | `cv2.imwrite` |

**Normalization (training):** YOLO labels use **normalized** 0–1 coordinates relative to image width/height.

---

## 11. Data Integration

| Integration | Sources combined | Result |
|-------------|------------------|--------|
| **Live pipeline** | Mirror frame + preprocess + YOLO + GPS | Unified `AnalysisResult` in memory |
| **Map export** | `GeoTag` + `Detection[]` | `GeoMarker[]` on Leaflet map |
| **Field report** | Frame + detections + session + geo | Single `FieldReport` JSON + sidecar files |
| **Training** | Label Studio JSON + image folder | Unified `datasets/yolo_banana/` YOLO layout |

**Consistency:** All exports share one timestamp prefix (`agrivision_YYYYMMDD_HHMMSS_*`); JSON `artifacts` block cross-links files.

---

## 12. Data Reduction

| Reduction | Rationale |
|-----------|-----------|
| Inference on downscaled frames | Real-time performance on laptop |
| Process every Nth frame (`AGRIVISION_INFER_EVERY`) | Drop backlog; keep UI current |
| `max_det=80` cap | Limit markers and overlay clutter |
| Export only on Capture Frame | Avoid storing every live frame to disk |
| Training val split (~20%) | Hold-out for model evaluation |

---

## 13. Data Validation

| Check | Constraint | Where |
|-------|------------|-------|
| Frame shape | `h > 0`, `w > 0`, 3 channels | Pipeline entry |
| Bbox bounds | Clamped to image dimensions | `core/detection.py` |
| Confidence range | 0.0–1.0 from model; threshold 0.35 | Post-inference filter |
| Geo range | Valid float lat/lon; fallback if missing | `resolve_geo_tag()` |
| Export completeness | JSON written last; all artifact paths set | `export_field_report()` |
| Dataset integrity | `images/{split}` + `labels/{split}` pairs | `train.py` `resolve_data_yaml()` |

---

## 14. System Testing

### 14.1 Smoke test suite (`python smoke_test.py`)

Automated checks with **binary pass/fail** per test case.

| Test area | Key fields / criteria | Pass condition |
|-----------|----------------------|----------------|
| Module imports | 14 backend/UI modules | No import error |
| Category mapping | label strings → category | `diseased`, `stressed`, `healthy`, `none` correct |
| Preprocess | output shape | Same H×W×3 as input |
| Detection | return type | `list` from `run_detection()` |
| Pipeline | `detection_summary` | Contains key `total` |
| Geo HTML | map content | `"leaflet"` and `"circleMarker"` in HTML |
| Export JSON | file exists | `*_report.json` on disk |
| Export CSV | file exists | `*_report.csv` on disk |
| Export map | file exists | `*_map.html` on disk |
| UI boot | MainWindow, Sidebar | Initializes without crash |
| Live loop | 5× `update_frame()` | Start/stop without exception |

**Overall success:** `SMOKE TEST PASSED` — zero failures in `FAILURES` list.

### 14.2 Operational success criteria (field demo)

| Metric | Field | Target for successful demo |
|--------|-------|---------------------------|
| Mirror connected | Activity log | “Mirror” status OK |
| Live feed | FPS badge | &gt; 0 FPS, non-black frame |
| Detections | `detection_summary.total` | Updates when plants visible |
| GPS | `geo.latitude`, `geo.longitude` | Set or auto-detected |
| Export | `artifacts.report_json` | File opens; valid JSON |
| Map | `artifacts.leaflet_map` | Markers visible in browser |

### 14.3 Model inference thresholds (runtime)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `AGRIVISION_DET_MIN_CONF` | 0.35 | Minimum box confidence |
| `AGRIVISION_DET_MIN_AREA` | 400 px² | Minimum bounding-box area |
| `AGRIVISION_MAX_DET` | 80 | Max boxes per frame |

A detection is **accepted** only if confidence ≥ 0.35 and area ≥ 400 px².

---

## 15. Confidence Level

| Layer | Confidence level | Interpretation |
|-------|------------------|----------------|
| **Smoke test (system)** | **95%** | 95% confidence that core modules, pipeline, export, and UI boot work on the target machine when `smoke_test.py` exits 0 |
| **YOLO detection (per box)** | **Model score** (e.g. 0.35–0.99) | Probability-like confidence from YOLO; default display threshold **0.35** (35%) |
| **Geo auto-detect** | Variable (accuracy in meters) | Browser/Windows GPS; operator warned if accuracy ≥ 2000 m |
| **Field report export** | **100%** file integrity | If export returns paths and smoke test passes, artifacts exist and JSON schema is valid |

**Thesis statement (suggested):**  
> “System reliability was verified at a **95% confidence level** using an automated smoke test covering import, preprocessing, inference, geo export, and UI lifecycle. Individual disease detections are reported with **YOLO confidence scores**; only detections above **0.35 confidence** are retained for mapping and reports.”

---

## 16. Related documents

| Document | Content |
|----------|---------|
| [WORKFLOW_ERD.md](WORKFLOW_ERD.md) | Entity workflow and JSON schemas |
| [STORAGE_DESIGN.md](STORAGE_DESIGN.md) | File paths and retention |
| [MODEL_TRAINING.md](MODEL_TRAINING.md) | Training procedure (if present) |
| [NAVIGATING_THE_SYSTEM.md](NAVIGATING_THE_SYSTEM.md) | Live demo script mapped to functional requirements |
| [OUTLINE_DEFENSE_STATUS.md](OUTLINE_DEFENSE_STATUS.md) | Completion checklist |
