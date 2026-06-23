# AgriVision — Outline Defense Status

Use this document during your **outline defense** to explain system completion.

## Overall completion

| Layer | Progress | Notes |
|-------|----------|-------|
| **Frontend (UI)** | **100%** | PyQt5 dashboard, live feed, sidebar stats, Leaflet field map, activity log, built-in wireless mirror controls |
| **Backend** | **50%** | Core services implemented; session-scoped storage, GeoTIFF, PDF deferred to next phase |

Run in terminal for a printable summary:

```powershell
python -m backend
```

---

## Four objectives — backend vs frontend

| # | Objective | Frontend | Backend |
|---|-----------|----------|---------|
| 1 | Capture aerial images | 100% | 50% |
| 2 | Preprocess & enhance | 100% | 50% |
| 3 | YOLOv8 disease detection | 100% | 50% |
| 4 | Geo maps & reports | 100% | 50% |

**Backend average: 50%** — each objective has a working foundation with a defined “next phase.”

---

## Backend architecture (for panel Q&A)

```
Phone screen mirror (Android scrcpy)
       ↓
  [Capture]     utils/cast_manager.py, utils/screen_capture.py
       ↓
  [Preprocess]  core/preprocess.py (denoise, CLAHE, align)
       ↓
  [Detect]      core/detection.py (YOLOv8 + models/best.pt)
       ↓
  [Report]      backend/report.py → output/reports/*_frame.jpg, *_report.json/csv, *_map.html
       ↑
  [Orchestrator] backend/pipeline.py + ui/inference_worker.py
       ↓
  [Storage]     flat files under output/ (no SQL DB) — see STORAGE_DESIGN.md
```

**Frontend** consumes backend results only — it does not implement CV logic.

---

## Persistence (no database)

Runtime data is **in-memory** during a live run (`backend/session.py`) and **on disk** when the operator captures or exports.

| Path | Role | Status |
|------|------|--------|
| `output/reports/agrivision_*` | Capture Frame bundle (JPG + JSON + CSV + HTML map) | **Implemented** |
| `output/maps/live_map.html` | Rolling Leaflet map during live session | **Implemented** |
| `captured_frame.jpg` | Quick preview (overwritten each capture) | **Implemented** |
| `models/best.pt` | Deployed YOLO weights | **Implemented** |
| `output/sessions/` | One folder per Start→Stop run | Planned |
| `output/batch/` | Offline DJI / flight-folder processing | Planned |

Full layout, naming rules, env vars, and rollout phases: **[STORAGE_DESIGN.md](STORAGE_DESIGN.md)**

---

## What you can demo live

1. Start feed → live YOLO boxes + **Leaflet field map** in sidebar (geo-tagged detection markers)  
2. Set **Latitude / Longitude** for plantation anchor (or use defaults)  
3. **Capture Frame** → writes `agrivision_{timestamp}_frame.jpg`, `_report.json`, `_report.csv`, `_map.html` under `output/reports/`  
4. Open `output/maps/live_map.html` to show the continuously updated field map  
5. Show `python -m backend` for objective percentages  

---

## Backend — implemented (50%)

- Built-in wireless mirror capture (Android scrcpy)  
- Preprocessing pipeline (resize, denoise, CLAHE, alignment)  
- YOLOv8 inference + training script (`train.py`)  
- Detection summary stats (healthy / stressed / diseased)  
- Session tracking in memory (`backend/session.py`)  
- Field report export: JSON, CSV, **Leaflet HTML map** + frame JPEG  
- Geo-tagged detection markers (`backend/map_export.py`)  
- **Local filesystem storage design** documented (`docs/STORAGE_DESIGN.md`)  

## Backend — planned (remaining 50%)

- Session-scoped folders under `output/sessions/`  
- Drone EXIF GPS auto-import  
- GeoTIFF export  
- PDF farmer reports  
- Batch flight processing & validation metrics  

---

## Suggested defense script (1 minute)

> “Our **frontend is complete at 100%** — the operator sees live drone video, disease detections, health summary stats, and controls in a PyQt5 dashboard.  
> The **backend is at 50%** for this outline milestone: we have the full processing chain from capture through YOLO detection, plus flat-file export to JPEG, JSON, CSV, and an interactive Leaflet map under `output/`. We use no SQL database — session stats live in memory and field reports are written as traceable file bundles. The remaining backend work is session-scoped archival, automated GPS from drone EXIF, GeoTIFF maps, and PDF farmer reports, which we scoped for the next development phase. The on-disk layout is specified in our storage design document.”

---

## Related documents

| Document | Use in defense |
|----------|----------------|
| [STORAGE_DESIGN.md](STORAGE_DESIGN.md) | Where processed images and outputs are stored |
| [WORKFLOW_ERD.md](WORKFLOW_ERD.md) + [diagrams/AgriVision-Workflow-ERD.drawio](diagrams/AgriVision-Workflow-ERD.drawio) | Simple workflow ERD (JSON schema) |
| [ERD.md](ERD.md) | Logical entities (session, detection, report) |
| [CONCEPTUAL_FRAMEWORK.md](CONCEPTUAL_FRAMEWORK.md) | DFD, use cases, system context |
