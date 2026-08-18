import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, fetchArtifactBlob } from "../api.js";
import { SummaryPills, HealthPill } from "../components/CategoryPills.jsx";

export default function Reports() {
  const { reportId } = useParams();
  const navigate = useNavigate();
  const [list, setList] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/reports?limit=500")
      .then(setList)
      .catch((e) => setError(e.message));
  }, []);

  const grouped = useMemo(() => {
    const groups = new Map();
    (list?.items || []).forEach((r) => {
      const day = r.exported_at.slice(0, 10);
      if (!groups.has(day)) groups.set(day, []);
      groups.get(day).push(r);
    });
    return [...groups.entries()];
  }, [list]);

  if (error) return <div className="empty">Failed to load: {error}</div>;

  if (reportId) {
    return <ReportDetail reportId={reportId} onBack={() => navigate("/reports")} />;
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Reports</h2>
          <p>Exported field report bundles organized by day. Each bundle contains JSON, CSV, annotated frame, and a Leaflet map.</p>
        </div>
      </div>

      {!list && <div className="spinner">Loading reports…</div>}

      {grouped.map(([day, items]) => (
        <div className="card section" key={day}>
          <h3>
            {day} <span className="muted">— {items.length} report{items.length === 1 ? "" : "s"}</span>
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Video ID</th>
                  <th>Detections</th>
                  <th>Vegetation</th>
                  <th>Artifacts</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/reports/${r.id}`)}>
                    <td className="mono">{r.exported_at.slice(11)}</td>
                    <td className="mono">{r.video_id}</td>
                    <td>
                      <SummaryPills summary={r.detection_summary} />
                    </td>
                    <td>
                      <HealthPill label={r.vegetation?.health_label} />
                    </td>
                    <td className="muted">{Object.keys(r.artifacts).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {list && list.items.length === 0 && (
        <div className="empty">No reports exported yet — use "Export Field Report" in the desktop app.</div>
      )}
    </>
  );
}

function ReportDetail({ reportId, onBack }) {
  const [report, setReport] = useState(null);
  const [frameUrl, setFrameUrl] = useState("");
  const [mapUrl, setMapUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let revoked = [];
    api(`/api/reports/${reportId}`)
      .then(async (rec) => {
        setReport(rec);
        if (rec.artifacts.frame) {
          const u = await fetchArtifactBlob(rec.artifacts.frame);
          revoked.push(u);
          setFrameUrl(u);
        }
        if (rec.artifacts.map) {
          const u = await fetchArtifactBlob(rec.artifacts.map);
          revoked.push(u);
          setMapUrl(u);
        }
      })
      .catch((e) => setError(e.message));
    return () => revoked.forEach((u) => URL.revokeObjectURL(u));
  }, [reportId]);

  const download = async (url, filename) => {
    const blob = await fetchArtifactBlob(url);
    const a = document.createElement("a");
    a.href = blob;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(blob);
  };

  if (error) return <div className="empty">Failed to load report: {error}</div>;
  if (!report) return <div className="spinner">Loading report {reportId}…</div>;

  const sess = report.session || {};

  return (
    <>
      <div className="page-head">
        <div>
          <h2 className="mono">Report {report.id}</h2>
          <p>
            Video <span className="mono">{report.video_id}</span> · exported {report.exported_at.replace("T", " ")} · source {report.video_source}
          </p>
        </div>
        <div className="toolbar">
          <button className="ghost" onClick={onBack}>
            ← All reports
          </button>
          {report.artifacts.json && (
            <button className="ghost" onClick={() => download(report.artifacts.json, `agrivision_${report.id}_report.json`)}>
              JSON
            </button>
          )}
          {report.artifacts.csv && (
            <button className="ghost" onClick={() => download(report.artifacts.csv, `agrivision_${report.id}_report.csv`)}>
              CSV
            </button>
          )}
        </div>
      </div>

      <div className="grid cols-2 section">
        <div className="card">
          <h3>Annotated frame</h3>
          {frameUrl ? <img className="frame-img" src={frameUrl} alt={`Report ${report.id} frame`} /> : <div className="empty">No frame artifact</div>}
        </div>
        <div className="card">
          <h3>Field map</h3>
          {mapUrl ? (
            <iframe title="report map" src={mapUrl} style={{ width: "100%", height: 420, border: "none", borderRadius: 10 }} />
          ) : (
            <div className="empty">No map artifact</div>
          )}
        </div>
      </div>

      <div className="grid cols-3 section">
        <div className="card">
          <h3>Detection summary</h3>
          <SummaryPills summary={report.detection_summary} />
          <dl className="kv" style={{ marginTop: 14 }}>
            <dt>Total</dt>
            <dd>{report.detection_summary.total}</dd>
            <dt>Vegetation</dt>
            <dd>
              <HealthPill label={report.vegetation?.health_label} />
            </dd>
            <dt>Mean stress</dt>
            <dd>{report.vegetation?.mean_stress != null ? `${(report.vegetation.mean_stress * 100).toFixed(1)}%` : "—"}</dd>
            <dt>High-stress area</dt>
            <dd>{report.vegetation?.high_stress_pct != null ? `${report.vegetation.high_stress_pct}%` : "—"}</dd>
          </dl>
        </div>

        <div className="card">
          <h3>GPS</h3>
          <dl className="kv">
            <dt>Latitude</dt>
            <dd className="mono">{report.geo.latitude ?? "—"}</dd>
            <dt>Longitude</dt>
            <dd className="mono">{report.geo.longitude ?? "—"}</dd>
            <dt>Accuracy</dt>
            <dd>{report.geo.accuracy_m != null ? `${report.geo.accuracy_m} m` : "—"}</dd>
            <dt>Altitude</dt>
            <dd>{report.geo.altitude_m != null ? `${report.geo.altitude_m} m` : "—"}</dd>
            <dt>Source</dt>
            <dd>{report.geo.source ?? "—"}</dd>
          </dl>
        </div>

        <div className="card">
          <h3>Session</h3>
          <dl className="kv">
            <dt>Video ID</dt>
            <dd className="mono">{sess.video_id || report.video_id}</dd>
            <dt>Started (UTC)</dt>
            <dd>{(sess.started_at || "—").replace("T", " ")}</dd>
            <dt>Frames processed</dt>
            <dd>{sess.frames_processed ?? "—"}</dd>
            <dt>Frames analyzed</dt>
            <dd>{sess.frames_analyzed ?? "—"}</dd>
            <dt>Total detections</dt>
            <dd>{sess.total_detections ?? "—"}</dd>
            <dt>Peak per frame</dt>
            <dd>{sess.peak_detections ?? "—"}</dd>
            <dt>Manual tags</dt>
            <dd>{sess.manual_tag_count ?? 0}</dd>
          </dl>
        </div>
      </div>

      <div className="card">
        <h3>Detections ({report.detections.length})</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Label</th>
                <th>Confidence</th>
                <th>Class ID</th>
                <th>BBox (x1 y1 x2 y2)</th>
              </tr>
            </thead>
            <tbody>
              {report.detections.map((d, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{d.label}</td>
                  <td>{d.confidence != null ? `${(d.confidence * 100).toFixed(1)}%` : "—"}</td>
                  <td>{d.class}</td>
                  <td className="mono">{(d.bbox || []).join(" ")}</td>
                </tr>
              ))}
              {report.detections.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty">
                    No detections in this report.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
