# AgriVision OS — Documentation & Presentation Site

A self-contained, multi-page web application that presents the **AgriVision** capstone
(paper + running system) as a branded "operating system." Everything is static and works
**offline** — no build step, no server required.

> AgriVision — *A Drone-Based System for Detecting Banana Diseases and Mapping Disease
> Distribution Using YOLOv8, Heatmaps, and Geotagging.* Legacy College of Compostela,
> Institute of Information Technology · March 2026.

---

## Open it

Just open **`index.html`** in a browser (double-click, or drag into Chrome/Edge).

Optional (nicer for `fetch`-free cleanliness or LAN sharing):

```powershell
cd docs/site
python -m http.server 8080
# then visit http://localhost:8080
```

Add `?theme=light` or `?theme=dark` to any page URL to force a theme.

---

## Pages (the "apps")

| File | App | What it is |
|------|-----|------------|
| `index.html` | **Overview** | Hero, key facts, disease cards, pipeline, app launcher, snapshot charts, team. |
| `documentation.html` | **Documentation** | The full paper — every chapter, subchapter, table, figure, and the 29 IEEE references — with a sticky table of contents and reference chips. |
| `results.html` | **Results Explorer** | Interactive training curves (real `results.csv`), per-class mAP with a metric toggle, dataset balance, checkpoint metrics, hyperparameters, and smoke tests. |
| `architecture.html` | **System & Architecture** | Native IPO diagram, the 6-stage pipeline with module map, the paper's DFD/CFD/use-case/ERD figures, data model entities, requirements traceability, and storage design. |
| `dashboard.html` | **Field Console** | An interactive recreation of the PyQt5 operator dashboard — a real captured frame with detection overlays, health summary, vegetation-stress meter, geo-tag, field map, activity log, and a working "Capture Frame → report" flow. |
| `pitch.html` | **Pitch Deck** | A 12-slide presentation. **Download PDF** screenshots each slide (html2canvas) into a landscape PDF (jsPDF) entirely in-browser; also supports fullscreen **Present** and browser **Print**. |

Navigation is the left **dock**; the top bar has a live clock, status LEDs, and a light/dark toggle.

---

## Structure

```
docs/site/
├── index.html  documentation.html  results.html
├── architecture.html  dashboard.html  pitch.html
├── data/                     # ← the structured source of truth (JSON)
│   ├── paper.json            # full paper: chapters → sections → ordered blocks
│   ├── tables.json           # all 13 tables + definition of terms
│   ├── figures.json          # figure manifest (caption, file, description)
│   ├── references.json       # 29 IEEE references + DOIs
│   ├── system.json           # architecture, pipeline, modules, requirements, ERD, storage
│   └── metrics.json          # real training curves, per-class + checkpoint metrics, dataset, smoke tests
└── assets/
    ├── css/os.css            # brand design system (tokens, shell, components, charts, print)
    ├── js/os.js              # shell (boot/topbar/dock/theme), SVG chart engine, doc renderer
    ├── js/data.js            # auto-generated bundle of all data/*.json (window.AGV)
    ├── figures/              # 25 figures extracted from the .docx + real system assets
    └── vendor/               # html2canvas + jsPDF (for offline PDF export)
```

### The data

`data/*.json` is the **structured, machine-readable version of the paper and system** —
complete and detailed so the site (or anything else) can render it. The pages read from
`window.AGV`, which is built from those files into `assets/js/data.js`.

If you edit any `data/*.json`, regenerate the bundle:

```powershell
cd docs/site
python -c "import json,os; b={k:json.load(open(f'data/{k}.json',encoding='utf-8')) for k in ['paper','tables','figures','references','system','metrics']}; open('assets/js/data.js','w',encoding='utf-8').write('window.AGV = '+json.dumps(b,ensure_ascii=False)+';')"
```

---

## Design

- **Brand:** leaf-green `#16A34A` primary over a deep-forest shell, with banana-gold
  `#F5C518` and tech-teal `#14B8A6` accents. Fully themed for light and dark.
- **Charts** are hand-rolled inline SVG (no chart library) with a CVD-validated categorical
  palette; hover tooltips included. Semantic colors: healthy `#1FA85A`, stressed `#E0A100`,
  diseased `#D64545`, viral/BBTV `#7C5CD6`.
- **Offline-first:** all data, fonts (system UI stack), scripts, and images are local. The
  only thing that would need the internet is nothing — the site is fully self-contained.

---

*Generated for the AgriVision capstone. Source paper: `docs/general/AGRIVISION PAPER.docx`.*
