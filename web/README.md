# AgriVision Web Admin Dashboard

A web-based administrative dashboard for AgriVision analytics, layered on top of
the existing PyQt5 desktop app. The desktop app remains the **live detection
interface**; this dashboard is the **central hub for historical data, analytics,
and administrative oversight**.

It reads the same `output/` folder the desktop app writes to — no database, no
duplication. The desktop app is the writer; the web API is a read-only layer.

```
Desktop app (PyQt5) ──writes──▶ output/reports/*.{json,csv,jpg,map.html}
                                        │
                                        ▼ reads
                             web/api (FastAPI)  ──serves──▶  web/frontend (React)
```

## Features

- **Dashboard** — KPIs, detections-per-report trend, health distribution, recent sessions.
- **Records** — searchable/filterable management of every field report and flight session.
- **Analytics** — class distribution, vegetation-stress trends, health-label breakdown.
- **Model Comparison** — 3-model line-up (deployed aerial detector, two-stage classifier, secondary-dataset retraining track) with live training curves from `results.csv`.
- **Disease Map** — confirmed disease/stress tags clustered into affected zones with an estimated radius, over satellite imagery.
- **Reports** — day-organized report bundles with annotated frame, embedded Leaflet map, detection table, and JSON/CSV download.
- **Auth** — single administrative user, HMAC bearer tokens.

## Requirements

- Python 3.10+ (for the API)
- Node.js 18+ (only to build the frontend)

## Quick start

### 1. Start the API

```bash
pip install -r web/requirements.txt
# from the repository root:
uvicorn web.api.main:app --port 8077
```

The API reads `output/reports/` relative to the repo root. Override with
`AGRIVISION_OUTPUT_DIR` or `AGRIVISION_REPORTS_DIR` if needed.

### 2. Frontend

**Development** (hot reload, proxies `/api` to port 8077):

```bash
cd web/frontend
npm install
npm run dev          # http://localhost:5173
```

**Production** (single-port deployment — API serves the built SPA):

```bash
cd web/frontend
npm run build        # outputs web/frontend/dist
# then just run the API; open http://localhost:8077
```

### 3. Sign in

Default credentials (override via env before starting the API):

- Username: `admin`
- Password: `agrivision`

| Env var | Purpose | Default |
|---|---|---|
| `AGRIVISION_ADMIN_USER` | Admin username | `admin` |
| `AGRIVISION_ADMIN_PASSWORD` | Admin password | `agrivision` |
| `AGRIVISION_SECRET_KEY` | Token signing key | auto-generated `.secret_key` |
| `AGRIVISION_TOKEN_TTL` | Token lifetime (seconds) | `43200` (12 h) |
| `AGRIVISION_OUTPUT_DIR` | Path to `output/` | `<repo>/output` |
| `AGRIVISION_REPORTS_DIR` | Path to reports | `<output>/reports` |

> Change the default password before any non-local deployment.

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Exchange credentials for a bearer token |
| GET | `/api/auth/me` | Current admin identity |
| GET | `/api/health` | Service status + report count (unauthenticated) |
| GET | `/api/reports` | List report summaries (`q`, `category`, `limit`, `offset`) |
| GET | `/api/reports/{id}` | Full report record |
| GET | `/api/reports/{id}/artifact/{kind}` | `frame` / `map` / `json` / `csv` file |
| GET | `/api/sessions` | Flight sessions grouped by session start |
| GET | `/api/sessions/{id}` | One session with its reports |
| GET | `/api/analytics/overview` | Aggregated KPIs and time series |
| GET | `/api/analytics/models` | Model comparison + training curves |
| GET | `/api/maps/disease` | Geo points + disease-radius clusters (`cluster_radius_m`) |
| GET | `/api/maps/exports` | Exported Leaflet maps + live map |

All endpoints except `/api/health` and `/api/auth/login` require the
`Authorization: Bearer <token>` header. Interactive docs at `/docs`.

## How data flows in

Each desktop export writes a bundle to `output/reports/`:

```
agrivision_YYYYMMDD_HHMMSS_report.json   # canonical record (parsed by the API)
agrivision_YYYYMMDD_HHMMSS_report.csv    # flat detection table
agrivision_YYYYMMDD_HHMMSS_frame.jpg     # annotated frame
agrivision_YYYYMMDD_HHMMSS_map.html      # standalone Leaflet map
```

The API's `services/agrivision_reader.py` parses these into normalized records,
groups them into flight sessions by `session.started_at`, and computes
analytics and disease clusters. Reports are cached by file mtime, so the
dashboard reflects new exports on refresh without restarting the API.

### Video IDs

The desktop app now assigns a unique **video ID** to each session before
take-off (`AGV-YYYYMMDD-HHMMSS-XXXXXX`, editable in the sidebar). It is embedded
in every report and surfaced throughout the dashboard. Older reports without a
video ID are shown with a `legacy-<timestamp>` identifier. See
[`docs/DRONE_REQUIREMENTS.md`](../docs/DRONE_REQUIREMENTS.md) for the pre-flight
protocol.

## Related docs

- [`docs/DRONE_REQUIREMENTS.md`](../docs/DRONE_REQUIREMENTS.md) — drone specs and pre-flight video-ID procedure
- [`docs/SECONDARY_DATASETS.md`](../docs/SECONDARY_DATASETS.md) — supplementing model accuracy and wiring metrics into Model Comparison
- [`docs/TESTING_RESULTS.md`](../docs/TESTING_RESULTS.md) — model training/validation results
