import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { api, getToken } from "../api.js";
import StatCard from "../components/StatCard.jsx";

const TOOLTIP_STYLE = { background: "#ffffff", border: "1px solid #dde5e0", borderRadius: 10 };
const CLASS_COLORS = {
  healthy: "#52b788",
  black_sigatoka: "#d4a373",
  bunchy_top: "#e76f51",
  panama: "#bc4749",
};

function CommandBlock({ label, cmd }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div className="toolbar" style={{ alignItems: "stretch" }}>
        <code className="mono" style={{ flex: 1, background: "#f1f5f2", border: "1px solid var(--border)", borderRadius: 8, padding: "9px 12px", overflowX: "auto" }}>
          {cmd}
        </code>
        <button className="ghost" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
      </div>
    </div>
  );
}

export default function Training() {
  const [batches, setBatches] = useState(null);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api("/api/training/candidates").then((d) => setBatches(d.items)).catch((e) => setError(e.message));
  }, []);

  const openDetail = (id) =>
    api(`/api/training/candidates/${id}`).then(setDetail).catch((e) => setError(e.message));

  if (error) return <div className="empty">Failed to load: {error}</div>;
  if (!batches) return <div className="spinner">Loading training candidates…</div>;

  const totalFrames = batches.reduce((a, b) => a + (b.frames || 0), 0);
  const totalBoxes = batches.reduce((a, b) => a + (b.boxes || 0), 0);

  if (detail) {
    const classData = Object.entries(detail.class_counts || {}).map(([name, count]) => ({ name, count }));
    return (
      <>
        <div className="page-head">
          <div>
            <h2 className="mono">{detail.batch_id}</h2>
            <p>Auto-labeled from video {detail.video_id} · {detail.frames} frames · {detail.boxes} boxes · interval {detail.frame_interval}, conf {detail.conf_threshold}</p>
          </div>
          <button className="ghost" onClick={() => setDetail(null)}>← All batches</button>
        </div>

        <div className="card section">
          <h3>Next steps: review, then retrain</h3>
          <p className="sub">This batch is in Label-Studio-ready YOLO format. Review the auto-labels, then merge and retrain with your existing pipeline. The dashboard prepares the data and hands off; it does not run training itself.</p>
          <CommandBlock label="1. (Optional) Review/fix labels in Label Studio, or use the local reviewer" cmd={`python tools/label_yolo.py --input datasets/candidates/${detail.batch_id}`} />
          <CommandBlock label="2. Merge into the training dataset (80/20 split)" cmd={detail.prepare_command} />
          <CommandBlock label="3. Retrain the detector" cmd={detail.train_command} />
        </div>

        <div className="grid cols-2 section">
          <div className="card">
            <h3>Class distribution (auto-labels)</h3>
            <div className="chart-box">
              {classData.length === 0 ? (
                <div className="empty">No boxes were detected in this batch.</div>
              ) : (
                <ResponsiveContainer>
                  <BarChart data={classData} layout="vertical" margin={{ left: 30 }}>
                    <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                    <XAxis type="number" tick={{ fill: "#5e7268", fontSize: 11 }} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={110} tick={{ fill: "#5e7268", fontSize: 11 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#16221b" }} cursor={{ fill: "rgba(82,183,136,0.06)" }} />
                    <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                      {classData.map((d) => (
                        <Cell key={d.name} fill={CLASS_COLORS[d.name] || "#74c69d"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
          <div className="card">
            <h3>Provenance</h3>
            <dl className="kv">
              <dt>Source video</dt>
              <dd className="mono">{detail.video_id}</dd>
              <dt>Created</dt>
              <dd>{(detail.created_at || "").replace("T", " ")}</dd>
              <dt>Frames</dt>
              <dd>{detail.frames}</dd>
              <dt>Boxes</dt>
              <dd>{detail.boxes}</dd>
              <dt>Classes</dt>
              <dd className="mono">{(detail.classes || []).join(", ")}</dd>
              <dt>Review status</dt>
              <dd><span className="pill neutral">{detail.review_status}</span></dd>
            </dl>
          </div>
        </div>

        <div className="card">
          <h3>Sample auto-labeled frames</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
            {(detail.preview_frames || []).map((name) => (
              <img
                key={name}
                className="frame-img"
                loading="lazy"
                src={`/api/training/candidates/${detail.batch_id}/frame/${name}?token=${encodeURIComponent(getToken())}`}
                alt={name}
              />
            ))}
            {(detail.preview_frames || []).length === 0 && <div className="empty">No previews.</div>}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Training</h2>
          <p>Auto-labeled training candidates curated from recorded videos. Review them and feed the model to improve its intelligence over time.</p>
        </div>
      </div>

      <div className="grid cols-3 section">
        <StatCard label="Candidate batches" value={batches.length} />
        <StatCard label="Frames curated" value={totalFrames} hint="ready for review + training" />
        <StatCard label="Auto-labeled boxes" value={totalBoxes} />
      </div>

      <div className="card">
        <h3>Candidate batches</h3>
        {batches.length === 0 ? (
          <div className="empty">
            No candidates yet. Go to Video Library, pick a recorded feed, and choose "Send to training curation".
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Batch</th>
                  <th>Source video</th>
                  <th>Created</th>
                  <th>Frames</th>
                  <th>Boxes</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.batch_id} className="clickable" onClick={() => openDetail(b.batch_id)}>
                    <td className="mono">{b.batch_id}</td>
                    <td className="mono">{b.video_id}</td>
                    <td>{(b.created_at || "").slice(0, 16).replace("T", " ")}</td>
                    <td>{b.frames}</td>
                    <td>{b.boxes}</td>
                    <td><span className="pill neutral">{b.review_status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
