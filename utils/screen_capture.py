import os
import re
import time
import mss
import sys
import ctypes
from ctypes import wintypes
import numpy as np
import pygetwindow as gw
import cv2

from utils.phone_frame import crop_phone_content, phone_crop_enabled, phone_content_rect

PW_RENDERFULLCONTENT = 2


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def widget_exclude_screen_rect(widget, margin: int = 4):
    """Physical-screen rectangle of this window (Windows HWND when available).

    Used to paint black over AgriVision in the grabbed bitmap so the scrcpy window can sit on the
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


def _prefer_window_capture() -> bool:
    """OBS-style window capture (PrintWindow), not desktop pixels under other apps."""
    if sys.platform != "win32":
        return False
    v = (os.environ.get("AGRIVISION_DESKTOP_CAPTURE") or "").strip().lower()
    return v not in ("1", "true", "yes", "on")


def _hwnd_is_valid(hwnd: int) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        return bool(ctypes.windll.user32.IsWindow(hwnd))
    except Exception:
        return False


def _hwnd_screen_rect(hwnd: int):
    """(left, top, width, height) in screen coordinates."""
    if sys.platform != "win32" or not hwnd:
        return None
    try:
        r = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
        w = r.right - r.left
        h = r.bottom - r.top
        if w < 1 or h < 1:
            return None
        return (r.left, r.top, w, h)
    except Exception:
        return None


def _capture_hwnd_bgr(hwnd: int):
    """Capture the window bitmap via PrintWindow (OBS-style; not blocked by overlap)."""
    if sys.platform != "win32" or not hwnd:
        return None
    rect = _hwnd_screen_rect(hwnd)
    if rect is None:
        return None
    _, _, width, height = rect

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hwnd_dc = mfc_dc = hbmp = None
    try:
        hwnd_dc = user32.GetWindowDC(hwnd)
        if not hwnd_dc:
            return None
        mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        if not mfc_dc:
            return None
        hbmp = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
        if not hbmp:
            return None
        gdi32.SelectObject(mfc_dc, hbmp)
        ok = user32.PrintWindow(hwnd, mfc_dc, PW_RENDERFULLCONTENT)
        if not ok:
            ok = user32.PrintWindow(hwnd, mfc_dc, 0)
        if not ok:
            return None

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        buf_size = width * height * 4
        buffer = (ctypes.c_ubyte * buf_size)()
        lines = gdi32.GetDIBits(
            mfc_dc,
            hbmp,
            0,
            height,
            buffer,
            ctypes.byref(bmi),
            0,
        )
        if not lines:
            return None
        bgra = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
        return bgra[:, :, :3].copy()
    except Exception:
        return None
    finally:
        if hbmp:
            gdi32.DeleteObject(hbmp)
        if mfc_dc:
            gdi32.DeleteDC(mfc_dc)
        if hwnd_dc:
            user32.ReleaseDC(hwnd, hwnd_dc)


_CAST_PREFER_DEFAULT = (
    "scrcpy,agrivision android mirror,mirror,mirroring,screen,display,stream,android,phone"
)
_CAST_SKIP_DEFAULT = (
    "home,main,welcome,launcher,首页,主页,设置,settings,about,"
    "agrivision,cursor,visual studio,code,program manager,taskbar,python,"
    "microsoft edge,chrome,firefox,explorer,windows input"
)
_MIRROR_FALLBACK_TITLES = ("AgriVision Android Mirror", "scrcpy")


def _title_tokens(env_key: str, default: str) -> list[str]:
    raw = os.environ.get(env_key, default)
    return [t.strip().lower() for t in raw.split(",") if t.strip()]


def _window_title_lower(win) -> str:
    return (getattr(win, "title", None) or "").lower()


def _window_area(win) -> int:
    return max(0, int(getattr(win, "width", 0) or 0)) * max(
        0, int(getattr(win, "height", 0) or 0)
    )


def _score_cast_window(win) -> int:
    """Higher score = more likely the live cast/mirror window (not app home/chrome)."""
    title = _window_title_lower(win)
    score = 0
    for kw in _title_tokens("AGRIVISION_CAST_PREFER", _CAST_PREFER_DEFAULT):
        if kw in title:
            score += 100
    for kw in _title_tokens("AGRIVISION_CAST_SKIP", _CAST_SKIP_DEFAULT):
        if kw in title:
            score -= 120
    min_area = int(os.environ.get("AGRIVISION_CAST_MIN_AREA", "60000"))
    area = _window_area(win)
    if area < min_area:
        score -= 80
    else:
        score += min(area // 10000, 60)
    return score


_last_logged_capture_title = None


def _log_capture_target(win) -> None:
    global _last_logged_capture_title
    title = getattr(win, "title", "") or ""
    if title == _last_logged_capture_title:
        return
    _last_logged_capture_title = title
    w = getattr(win, "width", 0)
    h = getattr(win, "height", 0)
    print(f'Mirror capture window: "{title}" ({w}x{h})')


def _title_search_variants(sub: str) -> list[str]:
    """Build search strings (brackets/spacing) so titled mirror windows still match."""
    sub = (sub or "").strip()
    if not sub:
        return []
    variants = [sub]
    if "[" in sub or "]" in sub:
        variants.append(sub.replace("[", " ").replace("]", " ").strip())
        inner = re.findall(r"\[([^\]]+)\]", sub)
        for part in inner:
            if part.strip():
                variants.append(part.strip())
    seen = set()
    out = []
    for v in variants:
        key = v.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _windows_matching_title(sub: str) -> list:
    hits = []
    seen_hwnd = set()
    for variant in _title_search_variants(sub):
        for w in gw.getWindowsWithTitle(variant):
            hwnd = int(getattr(w, "_hWnd", 0) or 0)
            key = hwnd or id(w)
            if key not in seen_hwnd:
                seen_hwnd.add(key)
                hits.append(w)
    if hits:
        return hits
    sub_l = sub.lower()
    for w in gw.getAllWindows():
        if not getattr(w, "title", ""):
            continue
        if sub_l in _window_title_lower(w):
            hwnd = int(getattr(w, "_hWnd", 0) or 0)
            key = hwnd or id(w)
            if key not in seen_hwnd:
                seen_hwnd.add(key)
                hits.append(w)
    return hits


def _auto_mirror_candidates() -> list:
    """Pick likely scrcpy mirror windows when no title filter matches."""
    min_area = int(os.environ.get("AGRIVISION_CAST_MIN_AREA", "60000"))
    skip = _title_tokens("AGRIVISION_CAST_SKIP", _CAST_SKIP_DEFAULT)
    candidates = []
    for w in gw.getAllWindows():
        title = _window_title_lower(w)
        if not title or len(title) < 2:
            continue
        if any(k in title for k in skip):
            continue
        if _window_area(w) < min_area:
            continue
        candidates.append(w)
    if not candidates:
        return []
    scored = [(w, _score_cast_window(w)) for w in candidates]
    best_score = max(s for _, s in scored)
    top = [w for w, s in scored if s == best_score]
    return top


def pick_mirror_cast_window(title_substring: str):
    """Choose the scrcpy mirror window by title substring."""
    sub = (title_substring or "").strip()
    windows: list = []

    if sub:
        windows = _windows_matching_title(sub)

    if not windows:
        for fallback in _MIRROR_FALLBACK_TITLES:
            if sub and sub.lower() == fallback.lower():
                continue
            windows = _windows_matching_title(fallback)
            if windows:
                break

    if not windows:
        windows = _auto_mirror_candidates()

    cast_must = (os.environ.get("AGRIVISION_CAST_TITLE") or "").strip().lower()
    if cast_must:
        filtered = [w for w in windows if cast_must in _window_title_lower(w)]
        if filtered:
            windows = filtered

    if not windows:
        return None

    if len(windows) == 1:
        return windows[0]

    scored = [(w, _score_cast_window(w)) for w in windows]
    best_score = max(s for _, s in scored)
    top = [w for w, s in scored if s == best_score]
    if best_score < 0:
        return max(windows, key=_window_area)
    return max(top, key=_window_area)


def pick_letsview_cast_window(title_substring: str):
    """Backward-compatible alias for :func:`pick_mirror_cast_window`."""
    return pick_mirror_cast_window(title_substring)


def _scale_frame_max_w(frame_bgr: np.ndarray, max_width: int) -> np.ndarray:
    mw = int(max_width) if max_width > 0 else _window_capture_max_w()
    if mw <= 0 or frame_bgr.shape[1] <= mw:
        return frame_bgr
    scale = mw / float(frame_bgr.shape[1])
    new_w = mw
    new_h = max(1, int(round(frame_bgr.shape[0] * scale)))
    return cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def get_frame(
    window_title="",
    fallback_size=(1280, 720),
    exclude_screen_rect=None,
    max_width: int = 0,
):
    """BGR frame from the scrcpy mirror window.

    On Windows uses PrintWindow (like OBS window capture): other apps on top,
    minimized state, and AgriVision overlapping do not block the feed.
    Falls back to desktop grab (MSS) if window capture fails.
    """
    win = pick_mirror_cast_window(window_title)

    if win is None:
        hint = (window_title or "").strip() or "AgriVision Android Mirror"
        print(f'Mirror window "{hint}" not found — black placeholder')
        h, w = fallback_size[1], fallback_size[0]
        return np.zeros((h, w, 3), dtype=np.uint8)

    _log_capture_target(win)
    hwnd = int(getattr(win, "_hWnd", 0) or 0)
    screen_rect = _hwnd_screen_rect(hwnd) if hwnd else None

    if hwnd and _prefer_window_capture():
        frame = _capture_hwnd_bgr(hwnd)
        if frame is not None and frame.size > 0:
            return _scale_frame_max_w(frame, max_width)

    if screen_rect:
        capture_left, capture_top, cap_w, cap_h = screen_rect
    else:
        if win.width < 1 or win.height < 1:
            h, w = fallback_size[1], fallback_size[0]
            return np.zeros((h, w, 3), dtype=np.uint8)
        capture_left = max(0, win.left)
        capture_top = max(0, win.top)
        cap_w, cap_h = win.width, win.height

    region = {
        "left": capture_left,
        "top": capture_top,
        "width": cap_w,
        "height": cap_h,
    }

    with mss.mss() as sct:
        screenshot = sct.grab(region)
        frame = np.array(screenshot)[:, :, :3].copy()

    _mask_screen_rect_on_capture(frame, capture_left, capture_top, exclude_screen_rect)
    return _scale_frame_max_w(frame, max_width)


def _finalize_mirror_frame(frame_bgr: np.ndarray, max_width: int) -> np.ndarray:
    if frame_bgr is None or frame_bgr.size == 0:
        return frame_bgr
    if phone_crop_enabled():
        frame_bgr = crop_phone_content(frame_bgr)
    return _scale_frame_max_w(frame_bgr, max_width)


_finalize_letsview_frame = _finalize_mirror_frame


def grab_mirror_cast(window_title: str, exclude_screen_rect, fallback_size=(1280, 720)):
    """Phone mirror capture (scrcpy): ``window_title`` substring for pygetwindow."""
    title = (window_title or "").strip()
    max_w = _window_capture_max_w()
    frame = get_frame(
        window_title=title,
        fallback_size=fallback_size,
        exclude_screen_rect=exclude_screen_rect,
        max_width=max_w,
    )
    return _finalize_mirror_frame(frame, max_w)


def grab_letsview_cast(window_title: str, exclude_screen_rect, fallback_size=(1280, 720)):
    """Backward-compatible alias for :func:`grab_mirror_cast`."""
    return grab_mirror_cast(window_title, exclude_screen_rect, fallback_size)


class LiveMirrorCapture:
    """Low-latency, stateful capture of a phone-mirror window.

    The plain :func:`grab_mirror_cast` re-enumerates every OS window and rescans
    the frame for letterbox bars on *each* call, which throttles the live feed
    to a fraction of the mirror's real frame rate. This class caches:

    * the target window handle (re-resolved only every ``rescan_sec`` seconds or
      when capture fails), and
    * the phone-content crop rectangle (recomputed only every ``crop_every``
      frames or when the captured size changes),

    so the per-frame cost is essentially just the PrintWindow grab — giving a
    scrcpy-smooth, crisp feed. Falls back to the slow path on any cache miss.
    """

    def __init__(self) -> None:
        self._hwnd = 0
        self._title = None
        self._last_resolve = 0.0
        self._rescan_sec = float(os.environ.get("AGRIVISION_WINDOW_RESCAN_SEC", "1.0"))
        self._crop_rect = None
        self._crop_shape = None
        self._crop_age = 0
        self._crop_every = max(1, int(os.environ.get("AGRIVISION_PHONE_CROP_EVERY", "20")))

    def reset(self) -> None:
        self._hwnd = 0
        self._title = None
        self._last_resolve = 0.0
        self._crop_rect = None
        self._crop_shape = None
        self._crop_age = 0

    def _resolve_hwnd(self, title: str) -> int:
        now = time.monotonic()
        if (
            self._hwnd
            and self._title == title
            and _hwnd_is_valid(self._hwnd)
            and (now - self._last_resolve) < self._rescan_sec
        ):
            return self._hwnd

        win = pick_mirror_cast_window(title)
        self._last_resolve = now
        self._title = title
        if win is None:
            self._hwnd = 0
            return 0
        _log_capture_target(win)
        self._hwnd = int(getattr(win, "_hWnd", 0) or 0)
        return self._hwnd

    def _finalize(self, frame_bgr: np.ndarray) -> np.ndarray:
        max_w = _window_capture_max_w()
        if not phone_crop_enabled():
            return _scale_frame_max_w(frame_bgr, max_w)

        shape = frame_bgr.shape[:2]
        if (
            self._crop_rect is None
            or self._crop_shape != shape
            or self._crop_age >= self._crop_every
        ):
            self._crop_rect = phone_content_rect(frame_bgr)
            self._crop_shape = shape
            self._crop_age = 0
        else:
            self._crop_age += 1

        rect = self._crop_rect
        if rect is not None:
            x1, y1, x2, y2 = rect
            h, w = shape
            if 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h:
                frame_bgr = frame_bgr[y1:y2, x1:x2]
        return _scale_frame_max_w(frame_bgr, max_w)

    def grab(self, window_title: str, exclude_screen_rect=None, fallback_size=(1280, 720)):
        title = (window_title or "").strip()
        hwnd = self._resolve_hwnd(title)

        # Fast path: cached HWND + OBS-style PrintWindow capture (full resolution).
        if hwnd and _prefer_window_capture() and _hwnd_is_valid(hwnd):
            frame = _capture_hwnd_bgr(hwnd)
            if frame is not None and frame.size > 0:
                return self._finalize(frame)

        # Cache miss: drop the cache and use the robust (slower) path this tick.
        self.reset()
        return grab_mirror_cast(title, exclude_screen_rect, fallback_size)
