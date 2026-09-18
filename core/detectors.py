"""Live detectors the desktop app can switch between.

Only Ultralytics ``.pt`` weights belong here. YOLO-NAS needs a separate
``super-gradients`` runtime and must not ship inside the installable .exe —
it would add a second deep-learning stack and it lost the accuracy benchmark.

Weights live under ``models/`` with stable names so a packager can collect that
one folder. Training-run paths under ``runs/`` stay out of the installer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from utils.app_paths import models_dir, resource_root

DEFAULT_DETECTOR_ID = "yolov9s"
SETTINGS_ORG = "AgriVision"
SETTINGS_APP = "AgriVision"
SETTINGS_KEY = "detector_id"


@dataclass(frozen=True)
class DetectorSpec:
    id: str
    name: str
    label: str
    description: str
    filename: str
    fallbacks: tuple[str, ...] = field(default_factory=tuple)
    recommended: bool = False

    def candidate_paths(self):
        root = models_dir()
        yield root / self.filename
        for name in self.fallbacks:
            yield root / name

    def weights_path(self):
        for path in self.candidate_paths():
            if path.is_file():
                return path
        return None

    def available(self) -> bool:
        return self.weights_path() is not None


DETECTORS: tuple[DetectorSpec, ...] = (
    DetectorSpec(
        id="yolov9s",
        name="YOLOv9s",
        label="YOLOv9s — recommended",
        description="Default live detector. Larger YOLOv9; slightly slower overlay than YOLOv8n.",
        filename="yolov9s_banana.pt",
        recommended=True,
    ),
    DetectorSpec(
        id="yolov9t",
        name="YOLOv9t",
        label="YOLOv9t — compact",
        description="Smallest YOLOv9 (2.0M params). Highest mAP@0.5 on the held-out test, close in live speed to YOLOv9s.",
        filename="yolov9t_banana.pt",
    ),
    DetectorSpec(
        id="yolov8n",
        name="YOLOv8n",
        label="YOLOv8n — faster",
        description="Smaller and faster. Prefer this on lower-end PCs; slightly weaker on rare diseases.",
        filename="yolov8n_banana.pt",
        fallbacks=("best.pt",),
    ),
)

_BY_ID = {spec.id: spec for spec in DETECTORS}


def get_spec(detector_id: str | None) -> DetectorSpec:
    if detector_id and detector_id in _BY_ID:
        return _BY_ID[detector_id]
    return _BY_ID[DEFAULT_DETECTOR_ID]


def available_detectors() -> list[DetectorSpec]:
    found = [spec for spec in DETECTORS if spec.available()]
    if found:
        return found
    # Last-resort: generic COCO nano if no banana weights shipped.
    return list(DETECTORS)


def resolve_detector_id(preferred: str | None = None) -> str:
    """Pick a detector that actually has weights on disk."""
    env = (os.environ.get("AGRIVISION_DETECTOR") or "").strip().lower()
    order = [preferred, env, DEFAULT_DETECTOR_ID, *[s.id for s in DETECTORS]]
    seen: set[str] = set()
    for candidate in order:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        spec = _BY_ID.get(candidate)
        if spec and spec.available():
            return spec.id
    return DEFAULT_DETECTOR_ID


def load_saved_detector_id() -> str | None:
    """User's last choice from QSettings, or None if Qt is not available yet."""
    try:
        from PyQt5.QtCore import QSettings
    except ImportError:
        return None
    value = QSettings(SETTINGS_ORG, SETTINGS_APP).value(SETTINGS_KEY, "", type=str)
    return value.strip() or None


def save_detector_id(detector_id: str) -> None:
    try:
        from PyQt5.QtCore import QSettings
    except ImportError:
        return
    QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(SETTINGS_KEY, detector_id)


def fallback_weights():
    """Generic Ultralytics nano if no banana checkpoint is present."""
    repo = resource_root() / "yolov8n.pt"
    if repo.is_file():
        return repo
    return "yolov8n.pt"
