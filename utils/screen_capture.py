import mss
import numpy as np
import pygetwindow as gw
import cv2


def _mask_screen_rect_on_capture(
    frame_bgr: np.ndarray, capture_left: int, capture_top: int, exclude_screen_rect
) -> np.ndarray:
    """Paint black over pixels that correspond to an on-screen rectangle (e.g. this app).

    ``mss`` captures whatever is *visible* at those coordinates. If AgriVision overlaps
    the source window, you would otherwise see the UI inside itself (infinite mirror).
    """
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


def get_frame(
    window_title="Google Chrome",
    fallback_size=(1280, 720),
    exclude_screen_rect=None,
):
    """Grab BGR from a desktop window (e.g. drone live view in browser).

    ``exclude_screen_rect`` is optional ``(x, y, w, h)`` in **global screen coordinates**
    (same space as ``pygetwindow`` / ``mss``). Overlapping pixels are filled black so the
    capture does not include this app's window (avoids video feedback / "hall of mirrors").

    If the window is missing, returns a black placeholder.
    """
    windows = gw.getWindowsWithTitle(window_title)

    if not windows:
        print(f'Window "{window_title}" not found — using black placeholder')
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
    return frame