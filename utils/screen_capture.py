import mss
import numpy as np
import pygetwindow as gw


def get_frame(window_title="Google Chrome", fallback_size=(1280, 720)):
    """Grab BGR-ish RGB from a desktop window (e.g. drone live view in browser).

    Returns a 3-channel uint8 image; if the window is missing, returns a black frame
    so the UI keeps running.
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

    region = {
        "left": max(0, win.left),
        "top": max(0, win.top),
        "width": win.width,
        "height": win.height,
    }

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        frame = np.array(screenshot)
        return frame[:, :, :3].copy()  # BGRA -> BGR for OpenCV