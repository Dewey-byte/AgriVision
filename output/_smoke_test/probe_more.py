"""Extra probes: session IDs, pagination, data quality, frontend HTML."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8077"
VITE = "http://127.0.0.1:5173"


def req(method: str, url: str, body=None, token=None, timeout=20):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, raw, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def main():
    import urllib.error

    st, raw, _ = req("POST", BASE + "/api/auth/login", {"username": "admin", "password": "agrivision"})
    token = json.loads(raw)["token"]
    print("login", st)

    st, raw, _ = req("GET", BASE + "/api/sessions", token=token)
    sessions = json.loads(raw)
    print("session_count", sessions["total"])
    print("first_5_session_ids:")
    for s in sessions["items"][:5]:
        print(" ", s["session_id"], "| video", s["video_id"], "| reports", s["report_count"], "| started", s["started_at"])

    iso = [s["session_id"] for s in sessions["items"] if "T" in s["session_id"]]
    if iso:
        sid = iso[0]
        print("iso_session_id", sid)
        for label, enc in [
            ("raw", sid),
            ("quote_all", urllib.parse.quote(sid, safe="")),
            ("quote_keep_colon", urllib.parse.quote(sid, safe=":")),
        ]:
            st, raw, _ = req("GET", BASE + "/api/sessions/" + enc, token=token)
            print(f"  session GET {label}: {st} body={raw[:140]!r}")

    st, raw, hdr = req("GET", BASE + "/", token=token)
    print("GET /", st, "ctype", hdr.get("content-type"), "body", raw[:80])

    st, raw, _ = req("GET", BASE + "/api/maps/live", token=token)
    print("GET /api/maps/live", st, raw[:80])

    st, raw, _ = req("GET", BASE + "/api/reports?limit=2&offset=0", token=token)
    p0 = json.loads(raw)
    st, raw, _ = req("GET", BASE + "/api/reports?limit=2&offset=2", token=token)
    p1 = json.loads(raw)
    print("page0", [r["id"] for r in p0["items"]], "page1", [r["id"] for r in p1["items"]], "total", p0["total"])

    st, raw, _ = req("GET", BASE + "/api/analytics/overview", token=token)
    ov = json.loads(raw)
    print("overview", {k: ov[k] for k in ["report_count", "session_count", "healthy_pct", "detection_totals"]})
    print("class_distribution", ov["class_distribution"])
    print("health_labels", ov["health_label_distribution"])

    st, raw, _ = req("GET", BASE + "/api/maps/disease?cluster_radius_m=25", token=token)
    dm = json.loads(raw)
    print("points", len(dm["points"]), "markers", len(dm["report_markers"]), "clusters", len(dm["disease_clusters"]))
    for c in dm["disease_clusters"][:8]:
        print(" cluster", c["cluster_id"], c["dominant_category"], c["radius_m"], "m", c["point_count"], "pts")

    # Data quality: reports missing artifacts / detector / geo
    st, raw, _ = req("GET", BASE + "/api/reports?limit=200", token=token)
    reports = json.loads(raw)["items"]
    missing_frame = [r["id"] for r in reports if "frame" not in r["artifacts"]]
    missing_map = [r["id"] for r in reports if "map" not in r["artifacts"]]
    missing_det = [r["id"] for r in reports if not r.get("detector")]
    no_geo = [r["id"] for r in reports if r["geo"].get("latitude") is None]
    print("missing_frame", len(missing_frame), missing_frame[:8])
    print("missing_map", len(missing_map), missing_map[:8])
    print("missing_detector", len(missing_det), missing_det[:8])
    print("no_geo", len(no_geo), no_geo[:8])

    # Frontend
    st, raw, hdr = req("GET", VITE + "/")
    print("VITE /", st, "ctype", hdr.get("content-type"), "has root", b'id="root"' in raw)
    for path in ["/", "/records", "/analytics", "/models", "/disease-map", "/reports", "/videos", "/training"]:
        st, raw, _ = req("GET", VITE + path)
        print(f"  vite {path}: {st} bytes={len(raw)}")

    # orphaned API routes referenced by unused pages
    for path in ["/api/videos", "/api/training"]:
        st, raw, _ = req("GET", BASE + path, token=token)
        print(f"  api {path}: {st} {raw[:100]!r}")


if __name__ == "__main__":
    main()
