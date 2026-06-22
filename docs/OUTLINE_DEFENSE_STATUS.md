# AgriVision — Outline Defense Status

Use this document during your **outline defense** to explain system completion.

## Overall completion

| Layer | Progress | Notes |
|-------|----------|-------|
| **Frontend (UI)** | **100%** | PyQt5 dashboard, live feed, sidebar stats, Leaflet field map, activity log, built-in wireless mirror controls |
| **Backend** | **50%** | Core services implemented; geo/PDF deferred to next phase |

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
  [Report]      backend/report.py → output/reports/*.json, *.csv, *.html
       ↑
  [Orchestrator] backend/pipeline.py + ui/inference_worker.py
```

**Frontend** consumes backend results only — it does not implement CV logic.

---

## What you can demo live

1. Start feed → live YOLO boxes + **Leaflet field map** in sidebar (geo-tagged detection markers)  
2. Set **Latitude / Longitude** for plantation anchor (or use defaults)  
3. **Capture Frame** → saves report + `*_map.html` under `output/reports/`  
4. Show `python -m backend` for objective percentages  

---

## Backend — implemented (50%)

- Built-in wireless mirror capture (Android scrcpy)  
- Preprocessing pipeline (resize, denoise, CLAHE, alignment)  
- YOLOv8 inference + training script (`train.py`)  
- Detection summary stats (healthy / stressed / diseased)  
- Session tracking (`backend/session.py`)  
- Field report export: JSON, CSV, **Leaflet HTML map**  
- Geo-tagged detection markers (`backend/map_export.py`)  

## Backend — planned (remaining 50%)

- Drone EXIF GPS auto-import  
- GeoTIFF export  
- PDF farmer reports  
- Batch flight processing & validation metrics  

---

## Suggested defense script (1 minute)

> “Our **frontend is complete at 100%** — the operator sees live drone video, disease detections, health summary stats, and controls in a PyQt5 dashboard.  
> The **backend is at 50%** for this outline milestone: we have the full processing chain from capture through YOLO detection, plus report export to JSON, CSV, and an interactive Leaflet map. The remaining backend work is automated GPS import, GeoTIFF maps, and PDF reports, which we scoped for the next development phase.”
