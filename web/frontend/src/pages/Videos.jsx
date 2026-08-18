import React, { useEffect, useRef, useState } from "react";
import { api, getToken } from "../api.js";
import StatCard from "../components/StatCard.jsx";
import { SummaryPills } from "../components/CategoryPills.jsx";

function fmtDuration(s) {
  s = Math.round(s || 0);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function streamUrl(video) {
  return `/api/videos/${video.dir_name}/stream?token=${encodeURIComponent(getToken())}`;
}

export default function Videos() {
  const [videos, setVideos] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [curateFor, setCurateFor] = useState(null);

  const load = () => api("/api/videos").then((d) => setVideos(d.items)).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (videos && videos.length && !selected) setSelected(videos[0]);
  }, [videos]);

  if (error) return <div className="empty">Failed to load: {error}</div>;
  if (!videos) return <div className="spinner">Loading video library…</div>;

  const totalFrames = videos.reduce((a, v) => a + (v.frame_count || 0), 0);
  const totalDur = videos.reduce((a, v) => a + (v.duration_s || 0), 0);

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Video Library</h2>
          <p>Every recorded flight feed, stored for review and model training. Stream any feed or send it to training curation.</p>
        </div>
      </div>

      <div className="grid cols-3 section">
        <StatCard label="Stored feeds" value={videos.length} hint="one per recorded session" />
        <StatCard label="Total footage" value={fmtDuration(totalDur)} hint="minutes:seconds across all feeds" />
        <StatCard label="Frames captured" value={totalFrames} hint="raw frames available for training" />
      </div>

      {videos.length === 0 ? (
        <div className="empty">
          No videos recorded yet. In the desktop app, keep "Record &amp; store feed" checked and press Start to record a flight.
        </div>
      ) : (
        <div className="grid cols-2 section">
          <div className="card">
            <h3>Player</h3>
            {selected ? (
              <>
                <video
                  key={selected.dir_name}
                  className="frame-img"
                  style={{ background: "#000", maxHeight: 380 }}
                  controls
                  src={streamUrl(selected)}
                />
                <dl className="kv" style={{ marginTop: 14 }}>
                  <dt>Video ID</dt>
                  <dd className="mono">{selected.video_id}</dd>
                  <dt>Recorded</dt>
                  <dd>{(selected.started_at || "").replace("T", " ")}</dd>
                  <dt>Duration</dt>
                  <dd>{fmtDuration(selected.duration_s)} ({selected.frame_count} frames @ {Math.round(selected.fps)} fps)</dd>
                  <dt>Resolution</dt>
                  <dd>{selected.width}×{selected.height}</dd>
                  <dt>GPS</dt>
                  <dd className="mono">
                    {selected.geo?.latitude != null
                      ? `${Number(selected.geo.latitude).toFixed(5)}, ${Number(selected.geo.longitude).toFixed(5)}`
                      : "—"}
                  </dd>
                </dl>
                <button style={{ marginTop: 12 }} onClick={() => setCurateFor(selected)}>
                  Send to training curation
                </button>
              </>
            ) : (
              <div className="empty">Select a feed</div>
            )}
          </div>

          <div className="card">
            <h3>Recorded feeds</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Video ID</th>
                    <th>Recorded</th>
                    <th>Length</th>
                    <th>Last detections</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {videos.map((v) => (
                    <tr
                      key={v.dir_name}
                      className="clickable"
                      onClick={() => setSelected(v)}
                      style={selected?.dir_name === v.dir_name ? { background: "rgba(82,183,136,0.10)" } : undefined}
                    >
                      <td className="mono">{v.video_id}</td>
                      <td>{(v.started_at || "").slice(0, 16).replace("T", " ")}</td>
                      <td>{fmtDuration(v.duration_s)}</td>
                      <td><SummaryPills summary={v.detection_summary} /></td>
                      <td>
                        <button className="ghost" onClick={(e) => { e.stopPropagation(); setCurateFor(v); }}>
                          Curate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {curateFor && (
        <CurateDialog video={curateFor} onClose={() => setCurateFor(null)} />
      )}
    </>
  );
}

function CurateDialog({ video, onClose }) {
  const [interval, setInterval_] = useState(15);
  const [conf, setConf] = useState(0.35);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const pollRef = useRef(null);

  useEffect(() => () => pollRef.current && clearInterval(pollRef.current), []);

  const start = async () => {
    setError("");
    try {
      const j = await api(`/api/videos/${video.dir_name}/curate`, {
        method: "POST",
        body: JSON.stringify({ frame_interval: Number(interval), conf: Number(conf) }),
      });
      setJob(j);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api(`/api/videos/curate/jobs/${j.job_id}`);
          setJob(status);
          if (status.status === "done" || status.status === "error") {
            clearInterval(pollRef.current);
          }
        } catch {
          clearInterval(pollRef.current);
        }
      }, 1200);
    } catch (e) {
      setError(e.message);
    }
  };

  const pct = job && job.total_estimate
    ? Math.min(100, Math.round((100 * (job.frames_extracted || 0)) / job.total_estimate))
    : job?.status === "done" ? 100 : 0;

  return (
    <div className="login-wrap" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 50 }}>
      <div className="login-card" style={{ width: 440 }}>
        <h3 style={{ margin: 0 }}>Curate training data</h3>
        <p className="muted" style={{ margin: 0 }}>
          Extract frames from <span className="mono">{video.video_id}</span>, auto-label them with the current model, and build a review-ready YOLO batch.
        </p>

        {!job && (
          <>
            <label className="muted">Frame interval (every Nth frame): {interval}</label>
            <input type="range" min="1" max="60" value={interval} onChange={(e) => setInterval_(e.target.value)} />
            <label className="muted">Confidence threshold: {Number(conf).toFixed(2)}</label>
            <input type="range" min="0.1" max="0.9" step="0.05" value={conf} onChange={(e) => setConf(e.target.value)} />
            {error && <div className="error-text">{error}</div>}
            <div className="toolbar">
              <button onClick={start}>Start curation</button>
              <button className="ghost" onClick={onClose}>Cancel</button>
            </div>
          </>
        )}

        {job && (
          <>
            <div style={{ margin: "6px 0" }}>
              <div style={{ height: 8, background: "#eef3f0", borderRadius: 6, overflow: "hidden", border: "1px solid var(--border)" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: "var(--green)", transition: "width .3s" }} />
              </div>
            </div>
            <dl className="kv">
              <dt>Status</dt>
              <dd>{job.status}</dd>
              <dt>Frames</dt>
              <dd>{job.frames_extracted || 0}{job.total_estimate ? ` / ~${job.total_estimate}` : ""}</dd>
              <dt>Boxes</dt>
              <dd>{job.boxes || 0}</dd>
              <dt>Batch</dt>
              <dd className="mono" style={{ fontSize: 11 }}>{job.batch_id}</dd>
            </dl>
            <p className="muted" style={{ margin: 0 }}>{job.message}</p>
            {job.error && <div className="error-text">{job.error}</div>}
            <div className="toolbar">
              <button className="ghost" onClick={onClose}>
                {job.status === "done" || job.status === "error" ? "Close" : "Run in background"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
