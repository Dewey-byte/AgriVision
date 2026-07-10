"""Convert Qt pixmaps/images to OpenCV BGR for the vision pipeline."""

from typing import Optional

import cv2
import numpy as np
from PyQt5.QtGui import QImage


def qpixmap_to_bgr(pm) -> Optional[np.ndarray]:
    """BGR ``uint8`` ``(h,w,3)`` or ``None`` if empty."""
    if pm is None or pm.isNull():
        return None
    img = pm.toImage().convertToFormat(QImage.Format_RGB888)
    w, h = img.width(), img.height()
    if w < 1 or h < 1:
        return None
    bpl = img.bytesPerLine()
    n = bpl * h
    buf = img.bits().asstring(n)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, bpl // 3, 3))[:, :w, :].copy()
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
