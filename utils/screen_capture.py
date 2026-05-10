import os
import mss
import sys
import numpy as np
import pygetwindow as gw
import cv2


def widget_exclude_screen_rect(widget, margin: int = 4):
    """Physical-screen rectangle of this window (Windows HWND when available).

    Used to paint black over AgriVision in the grabbed bitmap so LetsView can sit on the
    same monitor without infinite mirror feedback.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(widget.winId())
            if hwnd:
                r = wintypes.RECT()
                if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r)):
                    w = r.right - r.left
                    h = r.bottom - r.top
                    m = int(margin)
                    return (r.left - m, r.top - m, w + 2 * m, h + 2 * m)
        except Exception:
            pass
    fg = widget.frameGeometry()
    return (fg.x(), fg.y(), fg.width(), fg.height())


def _mask_screen_rect_on_capture(
    frame_bgr: np.ndarray, capture_left: int, capture_top: int, exclude_screen_rect
) -> np.ndarray:
    if exclude_screen_rect is None:
        return frame_bgr
    ex, ey, ew, eh = exclude_screen_rect
    cap_left, cap_top = capture_left, capture_top
    cap_right = cap_left + frame_bgr.shape[1]
    cap_bottom = cap_top + frame_bgr.shape[0]

    ix1 = max(cap_left, ex)
    iy1 = max(cap_top, ey)
    ix2 = min(cap_right, ex + ew)
    iy2 = min(cap_bottom, ey + eh)
    if ix1 >= ix2 or iy1 >= iy2:
        return frame_bgr

    lx1 = int(ix1 - cap_left)
    ly1 = int(iy1 - cap_top)
    lx2 = int(ix2 - cap_left)
    ly2 = int(iy2 - cap_top)
    cv2.rectangle(frame_bgr, (lx1, ly1), (lx2 - 1, ly2 - 1), (0, 0, 0), thickness=-1)
    return frame_bgr


def _window_capture_max_w() -> int:
    v = (os.environ.get("AGRIVISION_WINDOW_MAX_W") or "0").strip().lower()
    if v in ("", "0", "full", "none", "off"):
        return 0
    return int(v)


def get_frame(
    window_title="LetsView",
    fallback_size=(1280, 720),
    exclude_screen_rect=None,
    max_width: int = 0,
):
    """BGR frame from the LetsView (or matching) window; masks ``exclude_screen_rect``."""
    windows = gw.getWindowsWithTitle(window_title)

    if not windows:
        print(f'Window "{window_title}" not found — black placeholder')
        h, w = fallback_size[1], fallback_size[0]
        return np.zeros((h, w, 3), dtype=np.uint8)

    win = windows[0]
    if win.width < 1 or win.height < 1:
        h, w = fallback_size[1], fallback_size[0]
        return np.zeros((h, w, 3), dtype=np.uint8)

    capture_left = max(0, win.left)
    capture_top = max(0, win.top)
    region = {
        "left": capture_left,
        "top": capture_top,
        "width": win.width,
        "height": win.height,
    }

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        frame = np.array(screenshot)[:, :, :3].copy()

    _mask_screen_rect_on_capture(frame, capture_left, capture_top, exclude_screen_rect)

    mw = int(max_width) if max_width > 0 else _window_capture_max_w()
    if mw > 0 and frame.shape[1] > mw:
        scale = mw / float(frame.shape[1])
        new_w = mw
        new_h = max(1, int(round(frame.shape[0] * scale)))
        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    return frame


def grab_letsview_cast(window_title: str, exclude_screen_rect, fallback_size=(1280, 720)):
    """LetsView-only capture: ``window_title`` substring for pygetwindow."""
    title = (window_title or "").strip() or "LetsView"
    return get_frame(
        window_title=title,
        fallback_size=fallback_size,
        exclude_screen_rect=exclude_screen_rect,
    )
