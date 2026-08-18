"""Import GPS from drone JPEG EXIF (DJI aerial images).

Usage:
    python tools/import_exif_gps.py path/to/DJI_0142.JPG
    python tools/import_exif_gps.py --folder datasets/yolo_banana/images/test --latest
    python tools/import_exif_gps.py --folder datasets/inbox --scan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.exif_geo import (  # noqa: E402
    import_drone_gps_detailed,
    read_exif_gps,
    scan_folder_gps_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path, help="Single DJI / drone JPEG")
    parser.add_argument("--folder", type=Path, help="Folder of drone images")
    parser.add_argument("--latest", action="store_true", help="Use newest image in --folder")
    parser.add_argument("--scan", action="store_true", help="Summarize GPS coverage in --folder")
    args = parser.parse_args()

    if args.scan:
        if not args.folder:
            parser.error("--scan requires --folder")
        summary = scan_folder_gps_summary(args.folder.resolve())
        print(json.dumps(summary, indent=2))
        return 0

    if args.latest or (args.folder and not args.image):
        if not args.folder:
            parser.error("--latest requires --folder")
        found = import_drone_gps_detailed(args.folder.resolve())
        if found is None:
            print("No GPS EXIF found in folder", file=sys.stderr)
            return 1
        tag = found.tag
        print(f"image: {found.image_path}")
        print(f"latitude: {tag.latitude}")
        print(f"longitude: {tag.longitude}")
        if tag.altitude_m is not None:
            print(f"altitude_m: {tag.altitude_m}")
        print(f"source: {tag.source}")
        return 0

    if args.image is None:
        parser.error("Provide an image path or --folder --latest")

    tag = read_exif_gps(args.image.resolve())
    if tag is None:
        print(f"No GPS EXIF in {args.image}", file=sys.stderr)
        return 1

    print(f"latitude: {tag.latitude}")
    print(f"longitude: {tag.longitude}")
    if tag.altitude_m is not None:
        print(f"altitude_m: {tag.altitude_m}")
    print(f"source: {tag.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
