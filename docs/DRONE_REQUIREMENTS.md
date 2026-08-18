# AgriVision — Drone Technical Requirements

This document specifies the minimum and recommended technical requirements for
drones used in AgriVision field operations, and the standard pre-flight
procedure that ties every flight to a unique video ID.

---

## 1. Minimum drone requirements

| Requirement | Minimum | Recommended | Rationale |
|---|---|---|---|
| Camera resolution | 1080p @ 30 fps | 4K @ 30 fps (downscaled to 640 px for inference) | YOLOv8n input is 640 px; higher capture resolution preserves leaf detail after cropping |
| Video output | Live view to companion phone app (RTMP/screen-mirrorable) | Clean HDMI / low-latency phone mirror | AgriVision captures the mirrored phone screen via scrcpy |
| Gimbal | 1-axis (pitch) | 3-axis stabilized | Frame-quality gate rejects blurred/tilted frames; stabilization raises analyzable-frame yield |
| GNSS | GPS | GPS + GLONASS/Galileo, accuracy ≤ 5 m | Report geo-tagging and disease-radius mapping accuracy |
| Altitude hold | Barometric | Barometric + visual positioning | Consistent ground sample distance across a survey |
| Flight time | 15 min | 25+ min per battery | One battery should cover a 1–2 ha banana block |
| Wind resistance | Level 4 (~8 m/s) | Level 5 (~10 m/s) | Plantation flights in coastal Davao region conditions |
| Weight class | < 900 g | < 249 g (registration-exempt class) or certified | CAAP registration requirements (Philippines) |
| Transmission range | 1 km | 4+ km with live video | Maintain live view for the operator at field edge |

Reference platforms meeting the recommended tier: DJI Mini 3 Pro / Mini 4 Pro,
DJI Air 2S, Autel EVO Nano+. The primary dataset was captured with a DJI-class
camera drone (`DJI_*.JPG` source imagery).

## 2. Flight parameters for detection missions

| Parameter | Value |
|---|---|
| Survey altitude | 10–20 m above canopy (leaf-level detail); 30–40 m for block overview |
| Ground speed | ≤ 3 m/s during detection passes |
| Camera angle | 60–90° downward (nadir to oblique) |
| Overlap | ≥ 70% front, ≥ 60% side for full-coverage mapping passes |
| Lighting | 08:00–10:00 or 15:00–17:00 local; avoid harsh midday glare |
| Weather | No rain; wind below drone's rated resistance; visibility ≥ 3 km |

## 3. Pre-flight procedure (video ID protocol)

Every flight is identified by a **unique video ID** assigned **before
take-off**. The ID travels with every session record, field report (JSON +
CSV), and appears throughout the web admin dashboard.

1. Power on the drone and controller; connect the phone running the drone's
   live-view app.
2. Start AgriVision desktop and the wireless mirror (scrcpy).
3. In the sidebar **Video Source** card, check the **Flight Video ID** field:
   - Leave it blank/auto to accept the generated ID
     (`AGV-YYYYMMDD-HHMMSS-XXXXXX`), or
   - Click **New ID** to regenerate, or type an operation-specific ID
     (e.g. `AGV-BLOCKB-0708-01`).
4. Set the plantation GPS coordinates (Detect My Location, or paste field
   coordinates) and optionally draw the field area on the map.
5. Press **Start** — the session locks in the video ID and it is logged in
   the Activity Log.
6. Take off and fly the survey pattern in §2.
7. Export field reports during/after the flight; each report embeds the
   video ID for later lookup in the web dashboard.

## 4. Data link and companion hardware

| Component | Requirement |
|---|---|
| Companion phone | Android 10+, USB debugging or Wireless debugging enabled |
| Mirror link | scrcpy over USB or Wi-Fi (phone on laptop hotspot) |
| Ground laptop | Windows 10/11, dedicated GPU recommended (CUDA) for live YOLO inference; 8 GB RAM minimum |
| GPS source priority | Android phone GPS (ADB) → Windows location → browser → IP geolocation → manual |

## 5. Regulatory notes (Philippines)

- Drones > 250 g and/or commercial operations require CAAP registration and
  an RPAS operator certificate.
- Maintain visual line of sight; maximum 400 ft (~120 m) AGL.
- No flight within 10 km of airports without authorization.
- Secure landowner permission for plantation overflight and observe local
  privacy rules when capturing imagery.
