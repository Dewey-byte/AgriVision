"""Aerial frame preprocessing: resize, denoise, CLAHE, and temporal alignment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


def _env_on(key: str, default: bool = True) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


@dataclass
class PreprocessConfig:
    enabled: bool = True
    max_side: int = 0
    denoise: bool = True
    denoise_d: int = 5
    clahe: bool = True
    clahe_clip: float = 2.0
    clahe_grid: int = 8
    align: bool = True
    align_max_side: int = 320

    @classmethod
    def from_env(cls) -> PreprocessConfig:
        denoise_d = int(os.environ.get("AGRIVISION_PREPROC_DENOISE_D", "5"))
        if denoise_d % 2 == 0:
            denoise_d += 1
        return cls(
            enabled=_env_on("AGRIVISION_PREPROCESS", True),
            max_side=int(os.environ.get("AGRIVISION_PREPROC_MAX_SIDE", "0")),
            denoise=_env_on("AGRIVISION_PREPROC_DENOISE", True),
            denoise_d=max(3, denoise_d),
            clahe=_env_on("AGRIVISION_PREPROC_CLAHE", True),
            clahe_clip=float(os.environ.get("AGRIVISION_PREPROC_CLAHE_CLIP", "2.0")),
            clahe_grid=max(2, int(os.environ.get("AGRIVISION_PREPROC_CLAHE_GRID", "8"))),
            align=_env_on("AGRIVISION_PREPROC_ALIGN", True),
            align_max_side=int(os.environ.get("AGRIVISION_PREPROC_ALIGN_MAX", "320")),
        )


def resize_max_side(frame: np.ndarray, max_side: int) -> np.ndarray:
    h, w = frame.shape[:2]
    side = max(h, w)
    if max_side <= 0 or side <= max_side:
        return frame
    scale = max_side / float(side)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)


def denoise_bgr(frame: np.ndarray, diameter: int = 5) -> np.ndarray:
    d = diameter if diameter % 2 == 1 else diameter + 1
    return cv2.bilateralFilter(frame, d=d, sigmaColor=50, sigmaSpace=50)


def apply_clahe_lab(frame_bgr: np.ndarray, clahe: cv2.CLAHE) -> np.ndarray:
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _downscale_gray(gray: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = gray.shape[:2]
    side = max(h, w)
    if max_side <= 0 or side <= max_side:
        return gray, 1.0
    scale = max_side / float(side)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_AREA), scale


class FramePreprocessor:
    """Stateful preprocessor for live drone frames."""

    def __init__(self, config: Optional[PreprocessConfig] = None):
        self.config = config or PreprocessConfig.from_env()
        self._prev_gray: Optional[np.ndarray] = None
        self._clahe: Optional[cv2.CLAHE] = None

    def reset(self) -> None:
        self._prev_gray = None

    def _clahe_op(self) -> cv2.CLAHE:
        if self._clahe is None:
            cfg = self.config
            self._clahe = cv2.createCLAHE(
                clipLimit=cfg.clahe_clip,
                tileGridSize=(cfg.clahe_grid, cfg.clahe_grid),
            )
        return self._clahe

    def process(self, frame_bgr: np.ndarray) -> np.ndarray:
        if frame_bgr is None or frame_bgr.size == 0 or not self.config.enabled:
            return frame_bgr

        out = frame_bgr
        cfg = self.config

        if cfg.max_side > 0:
            out = resize_max_side(out, cfg.max_side)

        if cfg.denoise:
            out = denoise_bgr(out, cfg.denoise_d)

        if cfg.clahe:
            out = apply_clahe_lab(out, self._clahe_op())

        if cfg.align:
            out = self._align_temporal(out)

        return out

    def _align_temporal(self, frame_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        work_gray, scale = _downscale_gray(gray, self.config.align_max_side)

        if self._prev_gray is None or self._prev_gray.shape != work_gray.shape:
            self._prev_gray = work_gray.copy()
            return frame_bgr

        h, w = frame_bgr.shape[:2]
        warp = np.eye(2, 3, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 1e-4)
        try:
            _, warp_small = cv2.findTransformECC(
                self._prev_gray,
                work_gray,
                warp,
                cv2.MOTION_EUCLIDEAN,
                criteria,
                None,
                1,
            )
            if scale != 1.0:
                warp_small[0, 2] /= scale
                warp_small[1, 2] /= scale
            aligned = cv2.warpAffine(
                frame_bgr,
                warp_small,
                (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
        except cv2.error:
            aligned = frame_bgr

        self._prev_gray = work_gray.copy()
        return aligned
