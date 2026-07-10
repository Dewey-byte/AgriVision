"""Windows helpers: put scrcpy full-screen in background behind AgriVision.

The problem this solves
-----------------------
scrcpy opens a window whose pixel size determines the capture resolution.
If the scrcpy window is small (128 × 22 px at startup), AgriVision's
PrintWindow grab is equally tiny and the feed looks blurry after upscaling.

The solution
------------
After scrcpy starts we:
  1. Restore the window (un-minimise / un-hide).
  2. Move + resize it to fill the primary monitor (= maximum capture res).
  3. Strip title-bar decorations so it blends in (--window-borderless in
     scrcpy handles this at launch; this call is a belt-and-suspenders guard).
  4. Remove it from the taskbar and Alt-Tab list so the user only sees
     the AgriVision window.
  5. Push it to the very bottom of the z-order and bring AgriVision on top.

Everything runs on the UI thread via a one-shot QTimer so it does not block
the Qt event loop.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

_AVAILABLE = sys.platform == "win32"

# GetWindowLong / SetWindowLong indices
_GWL_STYLE   = -16
_GWL_EXSTYLE = -20

# Window styles
_WS_CAPTION      = 0x00C00000
_WS_THICKFRAME   = 0x00040000
_WS_BORDER       = 0x00800000
_WS_DLGFRAME     = 0x00400000
_WS_SYSMENU      = 0x00080000
_WS_MINIMIZEBOX  = 0x00020000
_WS_MAXIMIZEBOX  = 0x00010000
_WS_MAXIMIZE     = 0x01000000
_WS_MINIMIZE     = 0x20000000

# Extended styles
_WS_EX_TOOLWINDOW  = 0x00000080  # hide from taskbar + Alt-Tab
_WS_EX_NOACTIVATE  = 0x08000000  # don't steal focus
_WS_EX_APPWINDOW   = 0x00040000  # force taskbar entry (we remove this)

# SetWindowPos flags
_SWP_NOMOVE      = 0x0002
_SWP_NOSIZE      = 0x0001
_SWP_NOZORDER    = 0x0004
_SWP_NOACTIVATE  = 0x0010
_SWP_FRAMECHANGED = 0x0020
_SWP_SHOWWINDOW  = 0x0040

# Special z-order handles
_HWND_BOTTOM = 1   # below all windows

# ShowWindow commands
_SW_RESTORE    = 9
_SW_SHOWNOACTIVATE = 4


def _user32():
    return ctypes.windll.user32


def get_primary_monitor_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor in physical pixels."""
    if not _AVAILABLE:
        return (1920, 1080)
    u = _user32()
    return (int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1)))


def configure_background_capture(scrcpy_hwnd: int, agrivision_hwnd: int) -> bool:
    """Make scrcpy run full-screen, invisible to user, behind AgriVision.

    Parameters
    ----------
    scrcpy_hwnd:
        HWND of the scrcpy mirror window.
    agrivision_hwnd:
        HWND of the AgriVision main window (to bring to front afterwards).

    Returns True if everything succeeded.
    """
    if not _AVAILABLE or not scrcpy_hwnd:
        return False

    u = _user32()

    # 1. Restore the window if it is minimised / off-screen.
    u.ShowWindow(scrcpy_hwnd, _SW_SHOWNOACTIVATE)

    # 2. Strip all decorations (belt-and-suspenders alongside --window-borderless).
    style = u.GetWindowLongW(scrcpy_hwnd, _GWL_STYLE)
    style &= ~(
        _WS_CAPTION | _WS_THICKFRAME | _WS_BORDER |
        _WS_DLGFRAME | _WS_SYSMENU |
        _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX |
        _WS_MINIMIZE | _WS_MAXIMIZE
    )
    u.SetWindowLongW(scrcpy_hwnd, _GWL_STYLE, style)

    # 3. Hide from taskbar and Alt-Tab; prevent focus theft.
    exstyle = u.GetWindowLongW(scrcpy_hwnd, _GWL_EXSTYLE)
    exstyle = (exstyle | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE) & ~_WS_EX_APPWINDOW
    u.SetWindowLongW(scrcpy_hwnd, _GWL_EXSTYLE, exstyle)

    # 4. Resize for capture. Filling the whole monitor maximises resolution but
    #    makes the per-frame PrintWindow grab copy more pixels than the feed can
    #    use (it is downscaled to AGRIVISION_WINDOW_MAX_W anyway). Cap the render
    #    size to that target so capture stays fast with no visible quality loss.
    mw, mh = get_primary_monitor_size()
    tw, th = mw, mh
    try:
        cap_w = int(os.environ.get("AGRIVISION_WINDOW_MAX_W", "0") or "0")
    except ValueError:
        cap_w = 0
    if 0 < cap_w < mw:
        tw = cap_w
        th = max(1, round(mh * cap_w / mw))
    u.SetWindowPos(
        scrcpy_hwnd, 0,
        0, 0, tw, th,
        _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED | _SWP_SHOWWINDOW,
    )

    # 5. Push scrcpy to the very bottom of the z-order.
    u.SetWindowPos(
        scrcpy_hwnd, _HWND_BOTTOM,
        0, 0, 0, 0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE,
    )

    # 6. Bring AgriVision on top.
    if agrivision_hwnd:
        u.BringWindowToTop(agrivision_hwnd)
        u.SetForegroundWindow(agrivision_hwnd)

    return True
