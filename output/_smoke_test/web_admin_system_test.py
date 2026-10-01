"""End-to-end API + data-integrity test for AgriVision web admin.

Run after the API is up: python output/_smoke_test/web_admin_system_test.py
"""

from __future__ import annotations

import json
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8077"
RESULTS: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((status, name, detail))
    mark = "PASS" if status == "PASS" else status
    extra = f": {detail}" if detail else ""
    print(f"{mark}: {name}{extra}")


def request(method: str, path: str, body: dict | None = None, token: str | None = None, timeout: int = 20):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            parsed = json.loads(raw) if "json" in ctype or raw[:1] in (b"{", b"[") else raw
            return resp.status, parsed, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return exc.code, parsed, dict(exc.headers)


def expect(name: str, cond, detail: str = "") -> bool:
    if cond:
        record(name, "PASS", detail)
        return True
    record(name, "FAIL", detail or "assertion failed")
    return False


def check(name: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        record(name, "FAIL", f"{exc}\n{traceback.format_exc()}")


def main() -> int:
    # --- health ---
    def health():
        status, data, _ = request("GET", "/api/health")
        expect("GET /api/health status 200", status == 200, f"got {status}")
        expect("health.status ok", data.get("status") == "ok", str(data))
        expect("health.reports_found > 0", data.get("reports_found", 0) > 0, str(data.get("reports_found")))

    check("health", health)

    # --- auth ---
    token = None

    def login_ok():
        nonlocal token
        status, data, _ = request("POST", "/api/auth/login", {"username": "admin", "password": "agrivision"})
        expect("login valid credentials 200", status == 200, f"got {status} {data}")
        token = data.get("token")
        expect("login returns token", bool(token), str(data))
        expect("login username admin", data.get("username") == "admin", str(data.get("username")))

    check("login ok", login_ok)

    def login_wrong_password():
        status, data, _ = request("POST", "/api/auth/login", {"username": "admin", "password": "wrongpass"})
        expect("login wrong password 401", status == 401, f"got {status} {data}")

    check("login wrong password", login_wrong_password)

    def login_wrong_length_password():
        # hmac.compare_digest raises if lengths differ — must still be 401, not 500
        status, data, _ = request("POST", "/api/auth/login", {"username": "admin", "password": "x"})
        expect(
            "login short password 401 not 500",
            status == 401,
            f"got {status} {data}",
        )

    check("login short password", login_wrong_length_password)

    def login_wrong_length_user():
        status, data, _ = request("POST", "/api/auth/login", {"username": "a", "password": "agrivision"})
        expect(
            "login short username 401 not 500",
            status == 401,
            f"got {status} {data}",
        )

    check("login short username", login_wrong_length_user)

    def unauth_protected():
        status, data, _ = request("GET", "/api/reports")
        expect("GET /api/reports without token 401", status == 401, f"got {status} {data}")

    check("unauth reports", unauth_protected)

    def me():
        status, data, _ = request("GET", "/api/auth/me", token=token)
        expect("GET /api/auth/me 200", status == 200, f"got {status}")
        expect("me.role admin", data.get("role") == "admin", str(data))

    check("auth me", me)

    def bad_token():
        status, data, _ = request("GET", "/api/auth/me", token="not-a-real-token")
        expect("GET /api/auth/me bad token 401", status == 401, f"got {status} {data}")

    check("bad token", bad_token)

    # --- reports ---
    first_id = None

    def reports_list():
        nonlocal first_id
        status, data, _ = request("GET", "/api/reports?limit=50", token=token)
        expect("GET /api/reports 200", status == 200, f"got {status}")
        expect("reports.total > 0", data.get("total", 0) > 0, str(data.get("total")))
        items = data.get("items") or []
        expect("reports.items non-empty", len(items) > 0, str(len(items)))
        if items:
            first_id = items[0]["id"]
            row = items[0]
            for key in ("id", "video_id", "exported_at", "detection_summary", "artifacts"):
                expect(f"report summary has {key}", key in row, str(row.keys()))

    check("reports list", reports_list)

    def reports_search():
        status, data, _ = request("GET", "/api/reports?q=AGV&limit=20", token=token)
        expect("reports search q=AGV 200", status == 200, f"got {status}")
        status2, data2, _ = request("GET", "/api/reports?q=zzzz-no-such-id&limit=20", token=token)
        expect("reports empty search total 0", data2.get("total") == 0, str(data2.get("total")))
        status3, data3, _ = request("GET", "/api/reports?category=diseased&limit=20", token=token)
        expect("reports category=diseased 200", status3 == 200, f"got {status3}")
        if data3.get("items"):
            expect(
                "diseased filter only diseased reports",
                all(r["detection_summary"].get("diseased", 0) > 0 for r in data3["items"]),
                str([r["detection_summary"] for r in data3["items"][:3]]),
            )

    check("reports search", reports_search)

    def report_detail():
        if not first_id:
            record("report detail", "FAIL", "no report id from list")
            return
        status, data, _ = request("GET", f"/api/reports/{first_id}", token=token)
        expect("GET report detail 200", status == 200, f"got {status}")
        expect("detail.id matches", data.get("id") == first_id, str(data.get("id")))
        expect("detail has detections list", isinstance(data.get("detections"), list), type(data.get("detections")).__name__)
        expect("detail has geo", isinstance(data.get("geo"), dict), str(data.get("geo")))

    check("report detail", report_detail)

    def report_404():
        status, data, _ = request("GET", "/api/reports/19990101_000000", token=token)
        expect("GET missing report 404", status == 404, f"got {status} {data}")

    check("report 404", report_404)

    def artifacts():
        if not first_id:
            record("artifacts", "FAIL", "no report id")
            return
        status, rec, _ = request("GET", f"/api/reports/{first_id}", token=token)
        arts = rec.get("artifacts") or {}
        for kind in ("json", "csv", "frame", "map"):
            if kind not in arts:
                record(f"artifact {kind} present", "WARN", f"missing on {first_id}")
                continue
            st, body, headers = request("GET", arts[kind], token=token)
            expect(f"artifact {kind} 200", st == 200, f"got {st}")
            if kind == "json":
                expect("artifact json is object", isinstance(body, dict), type(body).__name__)
            if kind == "map":
                text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
                expect("artifact map has leaflet", "leaflet" in text.lower(), text[:80])
        st, body, _ = request("GET", f"/api/reports/{first_id}/artifact/notakind", token=token)
        expect("unknown artifact kind 404", st == 404, f"got {st} {body}")

    check("artifacts", artifacts)

    # --- sessions ---
    session_id = None

    def sessions_list():
        nonlocal session_id
        status, data, _ = request("GET", "/api/sessions", token=token)
        expect("GET /api/sessions 200", status == 200, f"got {status}")
        expect("sessions.total > 0", data.get("total", 0) > 0, str(data.get("total")))
        items = data.get("items") or []
        if items:
            session_id = items[0]["session_id"]
            expect("session has video_id", bool(items[0].get("video_id")), str(items[0]))

    check("sessions list", sessions_list)

    def session_detail():
        if not session_id:
            record("session detail", "FAIL", "no session id")
            return
        # session_id can contain characters that need encoding
        from urllib.parse import quote
        status, data, _ = request("GET", f"/api/sessions/{quote(session_id, safe='')}", token=token)
        expect("GET session detail 200", status == 200, f"got {status} {str(data)[:200]}")
        expect("session reports list", isinstance(data.get("reports"), list), str(type(data.get("reports"))))

    check("session detail", session_detail)

    def session_404():
        status, data, _ = request("GET", "/api/sessions/does-not-exist", token=token)
        expect("GET missing session 404", status == 404, f"got {status} {data}")

    check("session 404", session_404)

    # --- analytics ---
    def overview():
        status, data, _ = request("GET", "/api/analytics/overview", token=token)
        expect("GET /api/analytics/overview 200", status == 200, f"got {status}")
        for key in (
            "report_count",
            "session_count",
            "detection_totals",
            "healthy_pct",
            "class_distribution",
            "detections_over_time",
        ):
            expect(f"overview has {key}", key in data, str(list(data.keys())))
        totals = data.get("detection_totals") or {}
        parts = totals.get("healthy", 0) + totals.get("stressed", 0) + totals.get("diseased", 0)
        # total can exceed parts if some detections are categorized 'none', but should not be less
        expect(
            "overview totals consistent (parts <= total)",
            parts <= totals.get("total", 0) or totals.get("total", 0) == 0,
            f"parts={parts} total={totals.get('total')}",
        )
        expect("overview report_count > 0", data.get("report_count", 0) > 0, str(data.get("report_count")))

    check("analytics overview", overview)

    def models():
        status, data, _ = request("GET", "/api/analytics/models", token=token)
        expect("GET /api/analytics/models 200", status == 200, f"got {status}")
        expect("models list present", isinstance(data.get("models"), list), str(data.keys()))
        expect("benchmark present", isinstance(data.get("benchmark"), dict), str(data.keys()))
        bench = data.get("benchmark") or {}
        expect("benchmark has contenders", len(bench.get("contenders") or []) > 0, str(bench.get("contenders")))

    check("analytics models", models)

    # --- maps ---
    def disease_map():
        status, data, _ = request("GET", "/api/maps/disease?cluster_radius_m=25", token=token)
        expect("GET /api/maps/disease 200", status == 200, f"got {status}")
        expect("disease map has points", isinstance(data.get("points"), list), str(data.keys()))
        expect("disease map has report_markers", isinstance(data.get("report_markers"), list), str(data.keys()))
        expect("disease map has clusters", isinstance(data.get("disease_clusters"), list), str(data.keys()))
        if data.get("report_markers"):
            m = data["report_markers"][0]
            expect("marker has lat/lon", m.get("lat") is not None and m.get("lon") is not None, str(m))

    check("disease map", disease_map)

    def maps_exports():
        status, data, _ = request("GET", "/api/maps/exports", token=token)
        expect("GET /api/maps/exports 200", status == 200, f"got {status}")
        expect("map exports items list", isinstance(data.get("items"), list), str(data.keys()))

    check("maps exports", maps_exports)

    # --- SPA / docs ---
    def docs_and_root():
        status, body, headers = request("GET", "/docs")
        expect("GET /docs reachable", status in (200, 307, 308), f"got {status}")
        status2, body2, _ = request("GET", "/")
        # dist is missing so root may 404; record as warn if so
        if status2 == 200:
            record("GET / (SPA or API root)", "PASS", str(status2))
        else:
            record("GET / (SPA not built)", "WARN", f"got {status2} — frontend dist missing, use Vite :5173")

    check("docs and root", docs_and_root)

    # --- category consistency (desktop vs web reader) ---
    def category_parity():
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from utils.drawing import detection_category
        from web.api.services.agrivision_reader import label_category

        samples = [
            "panama (0.72)",
            "black_sigatoka (0.65)",
            "healthy (0.56)",
            "Banana Bunchy Top Virus",
            "Fusarium wilt",
            "sigatoka spot",
            "not_banana",
            "bbtv",
            "uncertain",
            "no banana",
            "mildew",
            "disease",
        ]
        mismatches = []
        for s in samples:
            a, b = detection_category(s), label_category(s)
            if a != b:
                mismatches.append(f"{s!r}: desktop={a} web={b}")
        expect(
            "desktop vs web label_category parity",
            not mismatches,
            "; ".join(mismatches) if mismatches else "all samples match",
        )

    check("category parity", category_parity)

    # --- records search fires per keystroke: data sanity ---
    def report_id_format():
        status, data, _ = request("GET", "/api/reports?limit=5", token=token)
        bad = [r["id"] for r in data.get("items", []) if not (len(r["id"]) == 15 and "_" in r["id"])]
        expect("report ids look like YYYYMMDD_HHMMSS", not bad, str(bad))

    check("report id format", report_id_format)

    print("---")
    passed = sum(1 for s, _, _ in RESULTS if s == "PASS")
    failed = [(n, d) for s, n, d in RESULTS if s == "FAIL"]
    warns = [(n, d) for s, n, d in RESULTS if s == "WARN"]
    print(f"API SYSTEM TEST: {passed} passed, {len(failed)} failed, {len(warns)} warnings, {len(RESULTS)} checks")
    for n, d in failed:
        print(f"  FAIL - {n}: {d}")
    for n, d in warns:
        print(f"  WARN - {n}: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
