"""Geo-tagging helpers for plantation field maps."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


# Compostela Valley, Philippines — fallback when auto-detect is unavailable
DEFAULT_LAT = 7.3669
DEFAULT_LON = 125.91


@dataclass
class GeoTag:
    latitude: float
    longitude: float
    altitude_m: float | None = None
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "source": self.source,
        }


@dataclass
class DetectedLocation:
    tag: GeoTag
    label: str = ""
    accuracy_m: float | None = None


def should_auto_detect_location() -> bool:
    if os.environ.get("AGRIVISION_AUTO_GEO", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    if os.environ.get("AGRIVISION_LAT") or os.environ.get("AGRIVISION_LON"):
        return False
    return True


def _http_json(url: str, timeout: float) -> dict[str, Any] | None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AgriVision/1.0 (geo-locate)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _run_powershell(script: str, timeout: float) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=max(5, timeout + 3),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _parse_lat_lon_acc(line: str) -> DetectedLocation | None:
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
        acc = float(parts[2]) if len(parts) >= 3 and parts[2] else None
    except ValueError:
        return None
    return DetectedLocation(
        tag=GeoTag(latitude=lat, longitude=lon, source="windows_gps"),
        label="Windows GPS",
        accuracy_m=acc,
    )


def _detect_windows_winrt(timeout: float) -> DetectedLocation | None:
    if sys.platform != "win32":
        return None
    sec = max(3, int(timeout))
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Devices.Geolocation.Geolocator,Windows.Devices.Geolocation,ContentType=WindowsRuntime] | Out-Null
$loc = New-Object Windows.Devices.Geolocation.Geolocator
$loc.DesiredAccuracy = [Windows.Devices.Geolocation.PositionAccuracy]::High
$task = $loc.GetGeopositionAsync().AsTask()
if (-not $task.Wait([TimeSpan]::FromSeconds({sec}))) {{ exit 4 }}
$p = $task.Result
Write-Output ("{{0}},{{1}},{{2}}" -f $p.Coordinate.Point.Position.Latitude, $p.Coordinate.Point.Position.Longitude, $p.Coordinate.Accuracy)
"""
    proc = _run_powershell(script, timeout)
    if proc is None or proc.returncode != 0:
        return None
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None
    return _parse_lat_lon_acc(lines[-1])


def _detect_windows_location(timeout: float) -> DetectedLocation | None:
    if sys.platform != "win32":
        return None
    sec = max(3, int(timeout))
    script = f"""
Add-Type -AssemblyName System.Device
$w = New-Object System.Device.Location.GeoCoordinateWatcher
$null = $w.TryStart($false, [TimeSpan]::FromSeconds({sec}))
$deadline = (Get-Date).AddSeconds({sec})
while ($w.Status -ne 'Ready' -and (Get-Date) -lt $deadline) {{
    Start-Sleep -Milliseconds 250
}}
if ($w.Permission -eq 'Denied' -or $w.Status -ne 'Ready') {{ exit 2 }}
$c = $w.Position.Location
if ($c.IsUnknown) {{ exit 3 }}
Write-Output ("{{0}},{{1}},{{2}}" -f $c.Latitude, $c.Longitude, $c.HorizontalAccuracy)
"""
    proc = _run_powershell(script, timeout)
    if proc is None or proc.returncode != 0:
        return None
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None
    found = _parse_lat_lon_acc(lines[-1])
    if found is not None:
        found.tag.source = "windows_gps"
    return found


def _detect_ip_location(timeout: float) -> DetectedLocation | None:
    data = _http_json(
        "http://ip-api.com/json/?fields=status,message,lat,lon,city,regionName,country",
        timeout,
    )
    if data and data.get("status") == "success":
        label = ", ".join(
            p for p in (data.get("city"), data.get("regionName"), data.get("country")) if p
        )
        return DetectedLocation(
            tag=GeoTag(
                latitude=float(data["lat"]),
                longitude=float(data["lon"]),
                source="ip_geolocation",
            ),
            label=(label or "IP geolocation") + " (approximate, city-level)",
            accuracy_m=5000.0,
        )

    data = _http_json("https://get.geojs.io/v1/ip/geo.json", timeout)
    if data and data.get("latitude") not in (None, "") and data.get("longitude") not in (None, ""):
        label = ", ".join(
            p for p in (data.get("city"), data.get("region"), data.get("country")) if p
        )
        return DetectedLocation(
            tag=GeoTag(
                latitude=float(data["latitude"]),
                longitude=float(data["longitude"]),
                source="ip_geolocation",
            ),
            label=(label or "IP geolocation") + " (approximate, city-level)",
            accuracy_m=5000.0,
        )
    return None


def detect_my_location(timeout: float | None = None) -> DetectedLocation | None:
    """Background fallback: Windows high-accuracy GPS, then approximate IP."""
    t = float(timeout or os.environ.get("AGRIVISION_GEO_TIMEOUT", "12"))

    win = _detect_windows_winrt(t)
    if win is not None:
        return win

    win = _detect_windows_location(min(t, 8.0))
    if win is not None:
        return win

    if os.environ.get("AGRIVISION_ALLOW_IP_GEO", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return None

    return _detect_ip_location(min(t, 6.0))


def format_location_label(label: str, accuracy_m: float | None, source: str) -> str:
    if accuracy_m is not None and accuracy_m > 0:
        if accuracy_m >= 1000:
            return f"{label} ±{accuracy_m / 1000:.1f} km"
        return f"{label} ±{accuracy_m:.0f} m"
    return label or source


def parse_coord(text: str, default: float) -> float:
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def resolve_geo_tag(
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    *,
    altitude_m: float | None = None,
    source: str = "manual",
) -> GeoTag:
    env_lat = os.environ.get("AGRIVISION_LAT")
    env_lon = os.environ.get("AGRIVISION_LON")

    lat_raw = latitude if latitude not in (None, "") else env_lat
    lon_raw = longitude if longitude not in (None, "") else env_lon

    lat = parse_coord(lat_raw, DEFAULT_LAT) if lat_raw not in (None, "") else DEFAULT_LAT
    lon = parse_coord(lon_raw, DEFAULT_LON) if lon_raw not in (None, "") else DEFAULT_LON
    lat = max(-90.0, min(90.0, lat))
    lon = max(-180.0, min(180.0, lon))

    return GeoTag(latitude=lat, longitude=lon, altitude_m=altitude_m, source=source)


def offset_meters(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    """Approximate lat/lon offset from a center point in meters."""
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def pixel_to_geo(
    x: float,
    y: float,
    frame_w: int,
    frame_h: int,
    center: GeoTag,
    *,
    span_m: float = 80.0,
) -> tuple[float, float]:
    """Map image pixel coordinates to geo using a local meter span across the frame."""
    if frame_w < 1 or frame_h < 1:
        return center.latitude, center.longitude
    east_m = (x / float(frame_w) - 0.5) * span_m
    north_m = (0.5 - y / float(frame_h)) * span_m
    return offset_meters(center.latitude, center.longitude, east_m, north_m)


def detections_to_markers(
    detections: list[dict[str, Any]],
    center: GeoTag,
    frame_w: int,
    frame_h: int,
    *,
    span_m: float = 80.0,
) -> list[dict[str, Any]]:
    """Geo-tag each detection bbox center for Leaflet markers."""
    from utils.drawing import detection_category

    markers: list[dict[str, Any]] = []
    for det in detections:
        bbox = det.get("bbox") or []
        if len(bbox) < 4:
            continue
        cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        cy = (float(bbox[1]) + float(bbox[3])) / 2.0
        lat, lon = pixel_to_geo(cx, cy, frame_w, frame_h, center, span_m=span_m)
        cat = detection_category(det.get("label", ""))
        markers.append(
            {
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "label": det.get("label", "detection"),
                "category": cat,
                "confidence": det.get("confidence"),
            }
        )
    return markers
