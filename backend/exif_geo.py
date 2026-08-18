"""Read GPS coordinates from drone / DJI JPEG EXIF metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.geo import DetectedLocation, GeoTag

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".tif", ".tiff", ".dng", ".heic"}


def _dms_to_decimal(values: tuple[float, ...] | list[float], ref: str) -> float:
    if not values:
        return 0.0
    deg = float(values[0])
    minutes = float(values[1]) if len(values) > 1 else 0.0
    seconds = float(values[2]) if len(values) > 2 else 0.0
    decimal = deg + minutes / 60.0 + seconds / 3600.0
    if ref.upper() in ("S", "W"):
        decimal = -decimal
    return decimal


def _ratio_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, tuple) and len(value) == 2:
        num, den = value
        if den:
            return float(num) / float(den)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_exif_gps(image_path: str | Path) -> GeoTag | None:
    """Extract GPS from a drone image EXIF block. Returns None when absent."""
    path = Path(image_path)
    if not path.is_file():
        return None

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            gps_ifd = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else {}
    except OSError:
        return None

    if not gps_ifd:
        return None

    lat_values = gps_ifd.get(2)
    lat_ref = gps_ifd.get(1, "N")
    lon_values = gps_ifd.get(4)
    lon_ref = gps_ifd.get(3, "E")
    if not lat_values or not lon_values:
        return None

    latitude = _dms_to_decimal(lat_values, str(lat_ref))
    longitude = _dms_to_decimal(lon_values, str(lon_ref))
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    if latitude == 0.0 and longitude == 0.0:
        return None

    altitude_m = _ratio_to_float(gps_ifd.get(6))
    return GeoTag(
        latitude=round(latitude, 7),
        longitude=round(longitude, 7),
        altitude_m=altitude_m,
        accuracy_m=5.0,
        source="drone_exif",
    )


def iter_image_files(folder: Path) -> Iterable[Path]:
    if not folder.is_dir():
        return
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            yield path


def find_newest_image(folder: Path) -> Path | None:
    newest: Path | None = None
    newest_mtime = -1.0
    for path in iter_image_files(folder):
        mtime = path.stat().st_mtime
        if mtime > newest_mtime:
            newest_mtime = mtime
            newest = path
    return newest


def drone_image_dir() -> Path | None:
    raw = os.environ.get("AGRIVISION_DRONE_IMAGE_DIR", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def import_latest_drone_gps(folder: Path | None = None) -> GeoTag | None:
    """Use the newest image in *folder* (or env ``AGRIVISION_DRONE_IMAGE_DIR``)."""
    root = folder or drone_image_dir()
    if root is None:
        return None
    image = find_newest_image(root)
    if image is None:
        return None
    return read_exif_gps(image)


def import_drone_gps_from_image(image_path: str | Path) -> GeoTag | None:
    return read_exif_gps(image_path)


@dataclass
class ExifImportResult:
    tag: GeoTag
    image_path: Path
    image_name: str

    def to_detected_location(self) -> DetectedLocation:
        return DetectedLocation(
            tag=self.tag,
            label=f"Drone EXIF ({self.image_name})",
            accuracy_m=self.tag.accuracy_m,
        )


def import_drone_gps_detailed(folder: Path | None = None) -> ExifImportResult | None:
    root = folder or drone_image_dir()
    if root is None:
        return None
    image = find_newest_image(root)
    if image is None:
        return None
    tag = read_exif_gps(image)
    if tag is None:
        return None
    return ExifImportResult(tag=tag, image_path=image, image_name=image.name)


def scan_folder_gps_summary(folder: Path) -> dict[str, Any]:
    """Summarize GPS coverage for a folder of drone images (batch manifest helper)."""
    images = list(iter_image_files(folder))
    tagged: list[dict[str, Any]] = []
    for path in images:
        tag = read_exif_gps(path)
        if tag is None:
            continue
        tagged.append(
            {
                "file": path.name,
                "latitude": tag.latitude,
                "longitude": tag.longitude,
                "altitude_m": tag.altitude_m,
            }
        )

    lats = [row["latitude"] for row in tagged]
    lons = [row["longitude"] for row in tagged]
    bounds = None
    if lats and lons:
        bounds = {
            "south": min(lats),
            "north": max(lats),
            "west": min(lons),
            "east": max(lons),
        }

    return {
        "folder": str(folder),
        "image_count": len(images),
        "gps_image_count": len(tagged),
        "bounds": bounds,
        "samples": tagged[:5],
    }
