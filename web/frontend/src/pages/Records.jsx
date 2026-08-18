import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { SummaryPills, HealthPill } from "../components/CategoryPills.jsx";

export default function Records() {
  const [tab, setTab] = useState("reports");
  const [reports, setReports] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams({ limit: "200" });
    if (q) params.set("q", q);
    if (category) params.set("category", category);
    api(`/api/reports?${params}`)
      .then(setReports)
      .catch((e) => setError(e.message));
  }, [q, category]);

  useEffect(() => {
    api("/api/sessions")
      .then(setSessions)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">Failed to load: {error}</div>;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Records Management</h2>
          <p>Every session record and field report exported by the operator app.</p>
        </div>
        <div className="toolbar">
          <button className={tab === "reports" ? "" : "ghost"} onClick={() => setTab("reports")}>
            Field Reports {reports ? `(${reports.total})` : ""}
          </button>
          <button className={tab === "sessions" ? "" : "ghost"} onClick={() => setTab("sessions")}>
            Sessions {sessions ? `(${sessions.total})` : ""}
          </button>
        </div>
      </div>

      {tab === "reports" && (
        <div className="card">
          <div className="toolbar" style={{ marginBottom: 14 }}>
            <input
              placeholder="Search by video ID, report ID, source…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ width: 300 }}
            />
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              <option value="healthy">Has healthy</option>
              <option value="stressed">Has stressed</option>
              <option value="diseased">Has diseased</option>
            </select>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Video ID</th>
                  <th>Exported</th>
                  <th>Detections</th>
                  <th>Vegetation</th>
                  <th>GPS</th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                {(reports?.items || []).map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/reports/${r.id}`)}>
                    <td className="mono">{r.id}</td>
                    <td className="mono">{r.video_id}</td>
                    <td>{r.exported_at.replace("T", " ")}</td>
                    <td>
                      <SummaryPills summary={r.detection_summary} />
                    </td>
                    <td>
                      <HealthPill label={r.vegetation?.health_label} />
                    </td>
                    <td className="mono">
                      {r.geo.latitude != null
                        ? `${Number(r.geo.latitude).toFixed(4)}, ${Number(r.geo.longitude).toFixed(4)}`
                        : "—"}
                      <span className="muted"> {r.geo.source ? `(${r.geo.source})` : ""}</span>
                    </td>
                    <td>{r.manual_tag_count}</td>
                  </tr>
                ))}
                {reports && reports.items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty">
                      No reports match the filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "sessions" && (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Video ID</th>
                  <th>Started (UTC)</th>
                  <th>Reports</th>
                  <th>Frames processed</th>
                  <th>Frames analyzed</th>
                  <th>Total detections</th>
                  <th>Peak</th>
                  <th>Manual tags</th>
                </tr>
              </thead>
              <tbody>
                {(sessions?.items || []).map((s) => (
                  <tr
                    key={s.session_id}
                    className="clickable"
                    onClick={() => navigate(`/reports/${s.report_ids[s.report_ids.length - 1]}`)}
                  >
                    <td className="mono">{s.video_id}</td>
                    <td>{(s.started_at || "").replace("T", " ")}</td>
                    <td>{s.report_count}</td>
                    <td>{s.frames_processed}</td>
                    <td>{s.frames_analyzed}</td>
                    <td>{s.total_detections}</td>
                    <td>{s.peak_detections}</td>
                    <td>{s.manual_tag_count}</td>
                  </tr>
                ))}
                {sessions && sessions.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="empty">
                      No sessions recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
