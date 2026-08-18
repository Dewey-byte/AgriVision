"""Geo-tagging helpers for plantation field maps."""

from __future__ import annotations

import json
import math
import os
import re
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
    accuracy_m: float | None = None
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "accuracy_m": self.accuracy_m,
            "source": self.source,
        }


@dataclass
class FieldBounds:
    """Geographic rectangle for manual plantation / scan area tagging."""

    south: float
    west: float
    north: float
    east: float

    def to_dict(self) -> dict[str, float]:
        return {
            "south": self.south,
            "west": self.west,
            "north": self.north,
            "east": self.east,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FieldBounds | None:
        if not data:
            return None
        try:
            return cls(
                south=float(data["south"]),
                west=float(data["west"]),
                north=float(data["north"]),
                east=float(data["east"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def contains(self, lat: float, lon: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def center(self) -> tuple[float, float]:
        return (self.south + self.north) / 2.0, (self.west + self.east) / 2.0


def default_field_bounds(
    center: GeoTag,
    *,
    width_m: float = 80.0,
    height_m: float = 60.0,
) -> FieldBounds:
    """Default plantation box around the anchor when the user has not drawn one yet."""
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    lat_n, lon_e = offset_meters(center.latitude, center.longitude, half_w, half_h)
    lat_s, lon_w = offset_meters(center.latitude, center.longitude, -half_w, -half_h)
    return FieldBounds(south=lat_s, west=lon_w, north=lat_n, east=lon_e)


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


def _adb_device_serials(adb: str) -> list[str]:
    """Connected ADB serials; wireless (hotspot) devices first."""
    try:
        from utils.cast_manager import _adb_devices_text
    except ImportError:
        return []

    wireless: list[str] = []
    other: list[str] = []
    for line in _adb_devices_text(adb).splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = parts[0]
        if ":" in serial and not serial.startswith("emulator-"):
            wireless.append(serial)
        else:
            other.append(serial)
    return wireless + other


def _detect_android_gps(timeout: float) -> DetectedLocation | None:
    """Read GPS from a connected Android phone over ADB (USB or laptop hotspot)."""
    try:
        from utils.cast_manager import _adb_devices_text, _run_adb, find_adb
    except ImportError:
        return None

    adb = find_adb()
    if not adb:
        return None

    serials = _adb_device_serials(adb)
    if not serials:
        return None

    sec = max(3, int(timeout))
    per_device = max(3, sec // max(1, len(serials)))

    for serial in serials:
        found = _read_android_gps_from_device(adb, serial, per_device)
        if found is not None:
            return found
    return None


def _read_android_gps_from_device(adb: str, serial: str, timeout: float) -> DetectedLocation | None:
    try:
        from utils.cast_manager import _run_adb
    except ImportError:
        return None

    sec = max(3, int(timeout))

    def _shell(args: list[str]) -> str:
        try:
            proc = _run_adb(adb, ["-s", serial, "shell", *args], timeout=sec)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if proc.returncode != 0:
            return ""
        return _normalize_adb_text((proc.stdout or "") + (proc.stderr or ""))

    _shell(["cmd", "location", "is-location-enabled"])

    loc_text = _shell(["dumpsys", "location"])
    found = _parse_android_location_dump(loc_text)
    if found is not None:
        return found

    gms_text = _shell(["dumpsys", "activity", "service", "com.google.android.location"])
    found = _parse_gms_location_dump(gms_text)
    if found is not None:
        return found

    return None


def _normalize_adb_text(text: str) -> str:
    if not text:
        return text
    return text.replace("Â±", "±")


def _parse_gms_location_dump(text: str) -> DetectedLocation | None:
    """Parse Google Play Services location dump (works when OEM censors dumpsys location)."""
    text = _normalize_adb_text(text)
    if not text.strip():
        return None

    candidates: list[tuple[int, float, float, float, str]] = []
    # {gps|fused|network, lat,lon±acc m, ...} — ± may be mojibake on Windows ADB
    for m in re.finditer(
        r"\{(gps|fused|network),\s*(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)[^0-9-]*(\d+(?:\.\d+)?)m",
        text,
        flags=re.IGNORECASE,
    ):
        provider = m.group(1).lower()
        lat, lon, acc = float(m.group(2)), float(m.group(3)), float(m.group(4))
        rank = {"gps": 0, "fused": 1, "network": 2}.get(provider, 3)
        candidates.append((rank, lat, lon, acc, provider))

    fine = re.search(
        r"last location \(fine\):\s*\{(?:gps|fused|network),\s*"
        r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)[^0-9-]*(\d+(?:\.\d+)?)m",
        text,
        flags=re.IGNORECASE,
    )
    if fine:
        lat, lon, acc = float(fine.group(1)), float(fine.group(2)), float(fine.group(3))
        candidates.append((0, lat, lon, acc, "fine"))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[0], c[3]))
    _, lat, lon, acc, provider = candidates[0]
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    if lat == 0.0 and lon == 0.0:
        return None

    label = "Phone GPS (ADB)"
    if provider == "network":
        label = "Phone location (network, ADB)"
    elif provider == "fused":
        label = "Phone GPS (fused, ADB)"

    return DetectedLocation(
        tag=GeoTag(latitude=lat, longitude=lon, accuracy_m=acc, source="android_gps"),
        label=label,
        accuracy_m=acc,
    )


def _parse_android_location_dump(text: str) -> DetectedLocation | None:
    """Parse ``adb shell dumpsys location`` for the best recent GPS fix."""
    text = _normalize_adb_text(text)
    best: tuple[float, float, float] | None = None
    best_acc = float("inf")

    for m in re.finditer(
        r"Location\[gps\s+(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    ):
        lat, lon = float(m.group(1)), float(m.group(2))
        snippet = text[m.end() : m.end() + 120]
        acc_m = re.search(r"hAcc=(\d+(?:\.\d+)?)", snippet)
        acc = float(acc_m.group(1)) if acc_m else 8.0
        if acc < best_acc:
            best_acc = acc
            best = (lat, lon, acc)

    if best is None:
        for m in re.finditer(
            r"latitude=(-?\d+(?:\.\d+)?)[^\n]{0,80}?longitude=(-?\d+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        ):
            lat, lon = float(m.group(1)), float(m.group(2))
            snippet = text[m.start() : m.end() + 80]
            acc_m = re.search(r"accuracy=(\d+(?:\.\d+)?)", snippet, flags=re.IGNORECASE)
            acc = float(acc_m.group(1)) if acc_m else 12.0
            if acc < best_acc:
                best_acc = acc
                best = (lat, lon, acc)

    if best is None:
        return None

    lat, lon, acc = best
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    if lat == 0.0 and lon == 0.0:
        return None

    return DetectedLocation(
        tag=GeoTag(latitude=lat, longitude=lon, accuracy_m=acc, source="android_gps"),
        label="Phone GPS (ADB)",
        accuracy_m=acc,
    )


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


def _detect_drone_exif_folder() -> DetectedLocation | None:
    """Read GPS from the newest JPEG in AGRIVISION_DRONE_IMAGE_DIR."""
    try:
        from backend.exif_geo import import_drone_gps_detailed
    except ImportError:
        return None

    found = import_drone_gps_detailed()
    if found is None:
        return None
    return found.to_detected_location()


def detect_my_location(timeout: float | None = None) -> DetectedLocation | None:
    """Phone GPS (ADB), Windows GPS, drone EXIF folder, then approximate IP."""
    t = float(timeout or os.environ.get("AGRIVISION_GEO_TIMEOUT", "12"))

    phone = _detect_android_gps(min(t, 8.0))
    if phone is not None:
        return phone

    win = _detect_windows_winrt(t)
    if win is not None:
        return win

    win = _detect_windows_location(min(t, 8.0))
    if win is not None:
        return win

    drone = _detect_drone_exif_folder()
    if drone is not None:
        return drone

    if os.environ.get("AGRIVISION_ALLOW_IP_GEO", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return None

    return _detect_ip_location(min(t, 6.0))


def format_location_label(label: str, accuracy_m: float | None, source: str) -> str:
    return label or source


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def dms_to_decimal(text: str) -> float | None:
    """Parse a single coordinate in decimal or DMS form.

    Accepts values like ``7.6688``, ``7°40'07.7"N``, ``126 06 07.3 E``,
    ``-7 40 7.7``. Returns None if no number can be extracted.
    """
    s = str(text).strip()
    if not s:
        return None

    try:
        return float(s)
    except ValueError:
        pass

    hemi_match = re.search(r"[NSEWnsew]", s)
    hemi = hemi_match.group(0).upper() if hemi_match else ""

    nums = _NUM_RE.findall(s)
    if not nums:
        return None

    deg = float(nums[0])
    minutes = float(nums[1]) if len(nums) > 1 else 0.0
    seconds = float(nums[2]) if len(nums) > 2 else 0.0

    value = abs(deg) + minutes / 60.0 + seconds / 3600.0
    if hemi in ("S", "W") or deg < 0 or s.lstrip().startswith("-"):
        value = -value
    return value


def parse_latlon_pair(text: str) -> tuple[float, float] | None:
    """Parse a combined 'lat, lon' string (decimal or DMS) into a pair."""
    s = str(text).strip()
    if not s:
        return None

    # Split on a comma first (Google Maps decimal form: "7.6688, 126.1020").
    if "," in s:
        left, _, right = s.partition(",")
        lat = dms_to_decimal(left)
        lon = dms_to_decimal(right)
        if lat is not None and lon is not None:
            return lat, lon

    # Otherwise split on hemisphere letters: "7°40'07.7\"N 126°06'07.3\"E".
    parts = re.split(r"(?<=[NSns])\s+", s, maxsplit=1)
    if len(parts) == 2:
        lat = dms_to_decimal(parts[0])
        lon = dms_to_decimal(parts[1])
        if lat is not None and lon is not None:
            return lat, lon

    return None


def parse_coord(text: str, default: float) -> float:
    value = dms_to_decimal(text)
    return value if value is not None else default


def resolve_geo_tag(
    latitude: str | float | None = None,
    longitude: str | float | None = None,
    *,
    altitude_m: float | None = None,
    accuracy_m: float | None = None,
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

    env_alt = os.environ.get("AGRIVISION_ALTITUDE_M")
    if altitude_m is None and env_alt:
        try:
            altitude_m = float(env_alt)
        except ValueError:
            altitude_m = None

    return GeoTag(
        latitude=lat,
        longitude=lon,
        altitude_m=altitude_m,
        accuracy_m=accuracy_m,
        source=source,
    )


def offset_meters(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    """WGS84 local tangent-plane offset from a center point in meters."""
    cos_lat = max(0.2, math.cos(math.radians(lat)))
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * cos_lat)
    return lat + dlat, lon + dlon


def estimate_field_span_m(
    geo: GeoTag,
    frame_w: int,
    frame_h: int,
    *,
    default_span_m: float = 80.0,
) -> tuple[float, float]:
    """Estimate ground width and height (meters) covered by the frame."""
    env_span = os.environ.get("AGRIVISION_FIELD_SPAN_M")
    if env_span:
        width_m = float(env_span)
    else:
        alt = geo.altitude_m
        if alt is None or alt <= 0:
            width_m = default_span_m
        else:
            hfov_deg = float(os.environ.get("AGRIVISION_CAMERA_HFOV", "73"))
            width_m = 2.0 * alt * math.tan(math.radians(hfov_deg / 2.0))

    aspect = frame_w / max(1.0, float(frame_h))
    height_m = width_m / aspect
    return width_m, height_m


def pixel_to_geo(
    x: float,
    y: float,
    frame_w: int,
    frame_h: int,
    center: GeoTag,
    *,
    span_m: float = 80.0,
    span_w: float | None = None,
    span_h: float | None = None,
    field_bounds: FieldBounds | None = None,
) -> tuple[float, float]:
    """Map image pixel coordinates to geo using field bounds or a local meter span."""
    if frame_w < 1 or frame_h < 1:
        return center.latitude, center.longitude

    if field_bounds is not None:
        lat = field_bounds.north - (y / float(frame_h)) * (
            field_bounds.north - field_bounds.south
        )
        lon = field_bounds.west + (x / float(frame_w)) * (
            field_bounds.east - field_bounds.west
        )
        return lat, lon

    if span_w is None or span_h is None:
        span_w, span_h = estimate_field_span_m(center, frame_w, frame_h, default_span_m=span_m)

    east_m = (x / float(frame_w) - 0.5) * span_w
    north_m = (0.5 - y / float(frame_h)) * span_h
    return offset_meters(center.latitude, center.longitude, east_m, north_m)


def stress_map_to_heat_points(
    stress_map,
    center: GeoTag,
    frame_w: int,
    frame_h: int,
    *,
    span_m: float = 80.0,
    field_bounds: FieldBounds | None = None,
    grid_step: int = 12,
    max_points: int = 400,
) -> list[list[float]]:
    """Sample stress map into Leaflet.heat points: [lat, lon, intensity]."""
    import numpy as np

    if stress_map is None or getattr(stress_map, "size", 0) == 0:
        return []

    h, w = stress_map.shape[:2]
    step = max(4, grid_step)
    span_w = span_h = None
    if field_bounds is None:
        span_w, span_h = estimate_field_span_m(center, frame_w, frame_h, default_span_m=span_m)
    points: list[list[float]] = []

    for y in range(0, h, step):
        y2 = min(h, y + step)
        for x in range(0, w, step):
            x2 = min(w, x + step)
            raw = float(np.mean(stress_map[y:y2, x:x2]))
            if raw < 0.05:
                continue
            from utils.stress_palette import stress_to_heat_intensity

            intensity = stress_to_heat_intensity(raw)
            px = (x + (x2 - x) / 2.0) * frame_w / max(1, w)
            py = (y + (y2 - y) / 2.0) * frame_h / max(1, h)
            lat, lon = pixel_to_geo(
                px,
                py,
                frame_w,
                frame_h,
                center,
                span_w=span_w,
                span_h=span_h,
                field_bounds=field_bounds,
            )
            if field_bounds is not None and not field_bounds.contains(lat, lon):
                continue
            points.append(
                [round(lat, 7), round(lon, 7), round(min(1.0, max(0.0, intensity)), 3)]
            )

    if len(points) > max_points:
        idx = np.linspace(0, len(points) - 1, max_points, dtype=int)
        points = [points[i] for i in idx]

    return points


def detections_to_markers(
    detections: list[dict[str, Any]],
    center: GeoTag,
    frame_w: int,
    frame_h: int,
    *,
    span_m: float = 80.0,
    field_bounds: FieldBounds | None = None,
) -> list[dict[str, Any]]:
    """Geo-tag each detection bbox center for Leaflet markers."""
    from utils.drawing import detection_category

    span_w = span_h = None
    if field_bounds is None:
        span_w, span_h = estimate_field_span_m(center, frame_w, frame_h, default_span_m=span_m)
    markers: list[dict[str, Any]] = []
    for det in detections:
        bbox = det.get("bbox") or []
        if len(bbox) < 4:
            continue
        cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        cy = (float(bbox[1]) + float(bbox[3])) / 2.0
        lat, lon = pixel_to_geo(
            cx,
            cy,
            frame_w,
            frame_h,
            center,
            span_w=span_w,
            span_h=span_h,
            field_bounds=field_bounds,
        )
        if field_bounds is not None and not field_bounds.contains(lat, lon):
            continue
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
