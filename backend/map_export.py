"""Leaflet geo-tagged marker export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.geo import GeoTag

_CATEGORY_COLOR = {
    "healthy": "#40916c",
    "stressed": "#d4a373",
    "diseased": "#bc4749",
}


def build_map_html(
    *,
    center_lat: float,
    center_lon: float,
    markers: list[dict[str, Any]] | None = None,
    title: str = "AgriVision — Field Map",
) -> str:
    """Build a standalone Leaflet HTML page with geo-tagged detection markers."""
    marks = markers or []
    center = [center_lat, center_lon]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body, #map {{ margin: 0; height: 100%; width: 100%; }}
    .leaflet-container {{ font: 12px/1.4 system-ui, sans-serif; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const center = {json.dumps(center)};
    const markers = {json.dumps(marks)};
    const colors = {json.dumps(_CATEGORY_COLOR)};

    const map = L.map('map', {{ zoomControl: true }}).setView(center, 17);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);

    L.circleMarker(center, {{
      radius: 7,
      color: '#1b4332',
      fillColor: '#52b788',
      fillOpacity: 0.95,
      weight: 2
    }}).addTo(map).bindPopup('<b>Drone / field anchor</b><br>Lat: ' + center[0] + '<br>Lon: ' + center[1]);

    markers.forEach(m => {{
      const c = colors[m.category] || '#40916c';
      L.circleMarker([m.lat, m.lon], {{
        radius: 6,
        color: c,
        fillColor: c,
        fillOpacity: 0.85,
        weight: 2
      }}).addTo(map).bindPopup('<b>' + m.label + '</b><br>' + (m.category || '') +
        (m.confidence != null ? '<br>conf: ' + Number(m.confidence).toFixed(2) : ''));
    }});

    if (markers.length) {{
      const group = L.featureGroup();
      markers.forEach(m => group.addLayer(L.circleMarker([m.lat, m.lon])));
      try {{ map.fitBounds(group.getBounds().pad(0.15)); }} catch (e) {{}}
    }}
  </script>
</body>
</html>
"""


def write_map_html(html: str, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out.resolve()


def export_leaflet_map(
    center: GeoTag,
    markers: list[dict[str, Any]],
    out_path: str | Path,
) -> Path:
    html = build_map_html(
        center_lat=center.latitude,
        center_lon=center.longitude,
        markers=markers,
    )
    return write_map_html(html, out_path)
