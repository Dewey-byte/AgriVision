import mss
import numpy as np
import pygetwindow as gw


def get_frame(window_title="Google Chrome"):
    windows = gw.getWindowsWithTitle(window_title)

    if not windows:
        print("Window not found")
        return None

    win = windows[0]

    region = {
        "left": win.left,
        "top": win.top,
        "width": win.width,
        "height": win.height
    }

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        frame = np.array(screenshot)
        return frame[:, :, :3].copy()  # Drop alpha channel