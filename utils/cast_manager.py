"""Built-in wireless screen mirroring manager for AgriVision.

AgriVision feeds the operator's phone screen into the YOLO detection pipeline by
capturing a mirror window. Instead of asking the user to launch a separate app,
this module *auto-manages* the mirror receivers from inside AgriVision:

* Android  -> ``scrcpy`` (+ ``adb``). USB or wireless (Wi-Fi). Very low latency
  (~35-70 ms), high resolution, no app install on the phone (just enable
  *Wireless debugging* / *USB debugging* once). scrcpy opens a window titled
  :data:`ANDROID_WINDOW_TITLE`, which the existing capture path then grabs.

The module is Windows-first (matching the rest of AgriVision) but degrades
gracefully on other platforms. Nothing here blocks the Qt event loop for long:
adb calls use short timeouts and process launches return immediately.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

ANDROID_WINDOW_TITLE = "AgriVision Android Mirror"

# scrcpy wireless debugging default port (Android "tcpip" mode).
_DEFAULT_ADB_PORT = 5555

# Common Windows mobile-hotspot subnets (laptop as AP).
_HOTSPOT_PREFIXES = ("192.168.137.", "192.168.43.")

# Hide child console windows on Windows (adb spawns a console otherwise).
_NO_WINDOW = 0
if sys.platform == "win32":
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


# Quality presets -> scrcpy flags. ``max_size`` 0 means "native resolution".
QUALITY_PRESETS: dict[str, dict] = {
    "balanced": {"label": "Balanced (1280p)", "max_size": 1280, "bitrate": "8M", "fps": 60},
    "high": {"label": "High (1080p)", "max_size": 1920, "bitrate": "14M", "fps": 60},
    "max": {"label": "Max (native)", "max_size": 0, "bitrate": "24M", "fps": 60},
}
DEFAULT_QUALITY = "high"


@dataclass
class MirrorResult:
    ok: bool
    message: str
    window_title: str = ""


def _candidate_paths(exe: str, extra: list[str]) -> list[str]:
    """Likely install locations for ``exe`` on Windows (PATH first)."""
    found: list[str] = []
    on_path = shutil.which(exe)
    if on_path:
        found.append(on_path)
    for p in extra:
        if p:
            found.append(os.path.expandvars(p))
    seen: set[str] = set()
    out: list[str] = []
    for p in found:
        key = os.path.normcase(os.path.abspath(p)) if p else p
        if key and key not in seen and os.path.isfile(p):
            seen.add(key)
            out.append(p)
    return out


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _winget_package_globs(exe: str) -> list[str]:
    """winget installs scrcpy under a versioned Packages subfolder, not on PATH."""
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return []
    matches = glob.glob(
        os.path.join(local, "Microsoft", "WinGet", "Packages", "Genymobile.scrcpy*", "**", exe),
        recursive=True,
    )
    # Newest version folder first (e.g. scrcpy-win64-v4.0 before v2.x).
    return sorted(matches, reverse=True)


def find_scrcpy() -> Optional[str]:
    """Locate ``scrcpy.exe`` (PATH, bundled tools/, scoop, choco, common dirs)."""
    override = os.environ.get("AGRIVISION_SCRCPY_PATH", "").strip()
    if override and os.path.isfile(override):
        return override
    exe = "scrcpy.exe" if sys.platform == "win32" else "scrcpy"
    extra = [
        os.path.join(_repo_root(), "tools", "scrcpy", exe),
        r"%USERPROFILE%\scoop\apps\scrcpy\current\scrcpy.exe",
        r"%LOCALAPPDATA%\Microsoft\WinGet\Links\scrcpy.exe",
        r"C:\ProgramData\chocolatey\bin\scrcpy.exe",
        r"C:\scrcpy\scrcpy.exe",
        r"C:\tools\scrcpy\scrcpy.exe",
    ]
    extra += _winget_package_globs(exe)
    paths = _candidate_paths(exe, extra)
    return paths[0] if paths else None


def find_adb() -> Optional[str]:
    """Locate ``adb.exe`` (next to scrcpy, Android SDK platform-tools, PATH)."""
    override = os.environ.get("AGRIVISION_ADB_PATH", "").strip()
    if override and os.path.isfile(override):
        return override
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    extra: list[str] = []
    scrcpy = find_scrcpy()
    if scrcpy:
        extra.append(os.path.join(os.path.dirname(scrcpy), exe))
    extra += [
        os.path.join(_repo_root(), "tools", "scrcpy", exe),
        r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
        r"%USERPROFILE%\scoop\apps\scrcpy\current\adb.exe",
        r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"C:\ProgramData\chocolatey\bin\adb.exe",
        r"C:\platform-tools\adb.exe",
    ]
    extra += _winget_package_globs(exe)
    paths = _candidate_paths(exe, extra)
    return paths[0] if paths else None


def _run_adb(adb: str, args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=_NO_WINDOW,
    )


def _normalize_serial(device_ip: str) -> str:
    """``192.168.1.5`` -> ``192.168.1.5:5555``; pass through if port present."""
    ip = (device_ip or "").strip()
    if not ip:
        return ""
    if ":" in ip:
        return ip
    return f"{ip}:{_DEFAULT_ADB_PORT}"


def _serial_to_display_ip(serial: str) -> str:
    """``192.168.1.5:5555`` -> ``192.168.1.5`` for the UI field."""
    serial = (serial or "").strip()
    if not serial:
        return ""
    if ":" in serial:
        host, port = serial.rsplit(":", 1)
        if port.isdigit() and int(port) == _DEFAULT_ADB_PORT:
            return host
        return serial
    return serial


def _parse_wireless_adb_serials(adb_devices_text: str) -> list[str]:
    serials: list[str] = []
    for line in (adb_devices_text or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = parts[0]
        if ":" in serial and not serial.startswith("emulator-"):
            serials.append(serial)
    return serials


def _parse_mdns_adb_serials(mdns_text: str) -> list[str]:
    serials: list[str] = []
    for line in (mdns_text or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of discovered"):
            continue
        match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d+)", line)
        if match:
            serials.append(match.group(1))
    return serials


def _ipv4_addresses_from_ipconfig(text: str) -> list[str]:
    return re.findall(r"IPv4 Address[^:]*:\s*([\d.]+)", text, flags=re.I)


def _hotspot_host_ips_from_ipconfig(text: str) -> list[str]:
    hosts: list[str] = []
    blocks = re.split(r"\n(?=\S)", text or "")
    for block in blocks:
        block_ips = _ipv4_addresses_from_ipconfig(block)
        low = block.lower()
        hotspot_block = any(
            token in low
            for token in (
                "hotspot",
                "wi-fi direct",
                "wifi direct",
                "local area connection",
                "mobile hotspot",
            )
        ) or any(ip.startswith(_HOTSPOT_PREFIXES) for ip in block_ips)
        if not hotspot_block:
            continue
        for ip in block_ips:
            if ip.startswith(_HOTSPOT_PREFIXES) or ip.endswith(".1"):
                hosts.append(ip)
    if not hosts:
        for ip in _ipv4_addresses_from_ipconfig(text):
            if ip.startswith(_HOTSPOT_PREFIXES):
                hosts.append(ip)
    return list(dict.fromkeys(hosts))


def _arp_neighbors_for_interface(interface_ip: str, arp_text: str) -> list[str]:
    neighbors: list[str] = []
    section = False
    for line in (arp_text or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("interface:"):
            section = interface_ip in stripped
            continue
        if not section:
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[0].count(".") == 3:
            ip = parts[0]
            if ip != interface_ip and not ip.endswith(".255"):
                neighbors.append(ip)
    return neighbors


def _tcp_reachable(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _adb_devices_text(adb: str) -> str:
    try:
        out = _run_adb(adb, ["devices"], timeout=6.0)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (out.stdout or "") + (out.stderr or "")


def _adb_mdns_text(adb: str) -> str:
    try:
        out = _run_adb(adb, ["mdns", "services"], timeout=8.0)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (out.stdout or "") + (out.stderr or "")


def _hotspot_neighbor_ips() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        ipcfg = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            timeout=6.0,
            check=False,
            creationflags=_NO_WINDOW,
        )
        arp = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=6.0,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    ipcfg_text = (ipcfg.stdout or "") + (ipcfg.stderr or "")
    arp_text = (arp.stdout or "") + (arp.stderr or "")
    neighbors: list[str] = []
    for host_ip in _hotspot_host_ips_from_ipconfig(ipcfg_text):
        neighbors.extend(_arp_neighbors_for_interface(host_ip, arp_text))
    return list(dict.fromkeys(neighbors))


def _try_adb_connect_serial(adb: str, serial: str) -> bool:
    try:
        _run_adb(adb, ["start-server"], timeout=8.0)
        out = _run_adb(adb, ["connect", serial], timeout=8.0)
    except (OSError, subprocess.TimeoutExpired):
        return False
    text = ((out.stdout or "") + (out.stderr or "")).lower()
    return "connected to" in text or "already connected" in text


def discover_android_device_ip() -> tuple[str, str]:
    """Find a wireless Android device IP for scrcpy.

    Returns ``(ip_or_serial, source)`` where *source* is a short label such as
    ``adb``, ``mdns``, or ``hotspot``. Empty strings when nothing is found.
    """
    adb = find_adb()
    if not adb:
        return "", ""

    for serial in _parse_wireless_adb_serials(_adb_devices_text(adb)):
        return _serial_to_display_ip(serial), "adb"

    for serial in _parse_mdns_adb_serials(_adb_mdns_text(adb)):
        if _try_adb_connect_serial(adb, serial):
            return _serial_to_display_ip(serial), "mdns"

    for ip in _hotspot_neighbor_ips():
        if not _tcp_reachable(ip, _DEFAULT_ADB_PORT):
            continue
        serial = f"{ip}:{_DEFAULT_ADB_PORT}"
        if _try_adb_connect_serial(adb, serial):
            return _serial_to_display_ip(serial), "hotspot"

    return "", ""


def resolve_android_device_ip(device_ip: str = "") -> tuple[str, str]:
    """Use manual IP when set; otherwise auto-discover on laptop hotspot."""
    manual = (device_ip or "").strip()
    if manual:
        return manual, "manual"
    return discover_android_device_ip()


@dataclass
class MirrorManager:
    """Spawns and tracks the mirror receiver child processes."""

    _procs: list[subprocess.Popen] = field(default_factory=list)
    _serial: Optional[str] = None
    last_window_title: str = ""

    # -- discovery -------------------------------------------------------
    def android_available(self) -> bool:
        return find_scrcpy() is not None

    # -- Android (scrcpy) ------------------------------------------------
    def start_android(
        self,
        device_ip: str = "",
        quality: str = DEFAULT_QUALITY,
        window_title: str = ANDROID_WINDOW_TITLE,
    ) -> MirrorResult:
        scrcpy = find_scrcpy()
        if not scrcpy:
            return MirrorResult(
                False,
                "scrcpy not found. Install it (winget install Genymobile.scrcpy "
                "or scoop install scrcpy) or drop scrcpy.exe in tools\\scrcpy\\, "
                "then retry. Wireless also needs adb.",
            )

        resolved_ip, resolve_source = resolve_android_device_ip(device_ip)
        serial = _normalize_serial(resolved_ip)
        if serial:
            connected, msg = self._adb_connect(serial)
            if not connected:
                return MirrorResult(False, msg)
            self._serial = serial

        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS[DEFAULT_QUALITY])
        # Short flags chosen for broad scrcpy version compatibility (1.15+ .. 3.x):
        #   -m max_size, -b bitrate, --max-fps, --window-title, -w stay-awake.
        cmd = [scrcpy]
        if serial:
            cmd += ["-s", serial]
        if preset["max_size"]:
            cmd += ["-m", str(preset["max_size"])]
        cmd += [
            "-b", str(preset["bitrate"]),
            "--max-fps", str(preset["fps"]),
            "--window-title", window_title,
            "--window-borderless",  # no title bar / decorations
            "-w",  # keep phone awake while mirroring
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            )
        except OSError as exc:
            return MirrorResult(False, f"Could not launch scrcpy: {exc}")

        self._procs.append(proc)
        self.last_window_title = window_title
        if serial:
            src = resolve_source if resolve_source != "manual" else "wireless"
            where = f"wireless ({serial}, {src})"
        else:
            where = "USB"
        return MirrorResult(
            True,
            f"Android mirror starting via scrcpy [{where}, {preset['label']}].",
            window_title,
        )

    def _adb_connect(self, serial: str) -> tuple[bool, str]:
        adb = find_adb()
        if not adb:
            return (
                False,
                "adb not found for wireless Android mirror. Install Android "
                "platform-tools (or use the adb bundled with scrcpy), or connect "
                "the phone by USB and leave the IP blank.",
            )
        try:
            _run_adb(adb, ["start-server"], timeout=10.0)
            out = _run_adb(adb, ["connect", serial], timeout=10.0)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"adb connect failed: {exc}"

        text = (out.stdout or "") + (out.stderr or "")
        low = text.lower()
        if "connected to" in low or "already connected" in low:
            return True, "adb connected"
        if "failed to connect" in low or "cannot connect" in low or "refused" in low:
            return (
                False,
                f"Could not reach {serial}. On the phone enable Developer options "
                "-> Wireless debugging (Android 11+) or run 'adb tcpip 5555' once "
                "over USB, and make sure the phone is on the same Wi-Fi/hotspot.",
            )
        return True, text.strip() or "adb connect issued"

    # -- lifecycle -------------------------------------------------------
    def is_running(self) -> bool:
        return any(p.poll() is None for p in self._procs)

    def stop(self) -> None:
        for proc in self._procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
        for proc in self._procs:
            if proc.poll() is None:
                try:
                    proc.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    try:
                        proc.kill()
                    except OSError:
                        pass
        if self._serial:
            adb = find_adb()
            if adb:
                try:
                    _run_adb(adb, ["disconnect", self._serial], timeout=5.0)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        self._procs.clear()
        self._serial = None
