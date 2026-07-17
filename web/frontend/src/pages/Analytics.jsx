import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  Cell,
} from "recharts";
import { api } from "../api.js";
import StatCard from "../components/StatCard.jsx";

const TOOLTIP_STYLE = {
  background: "#ffffff",
  border: "1px solid #dde5e0",
  borderRadius: 10,
};

const CLASS_COLORS = {
  healthy: "#52b788",
  black_sigatoka: "#d4a373",
  yellow_sigatoka: "#e9c46a",
  panama: "#bc4749",
  panama_disease: "#bc4749",
  moko: "#9b2226",
  bunchy_top: "#e76f51",
};

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/analytics/overview")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">Failed to load: {error}</div>;
  if (!data) return <div className="spinner">Loading analytics…</div>;

  const classData = Object.entries(data.class_distribution)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  const stress = data.stress_over_time.map((s) => ({
    ...s,
    mean_stress_pct: s.mean_stress != null ? +(s.mean_stress * 100).toFixed(1) : null,
  }));

  const t = data.detection_totals;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Analytics</h2>
          <p>Aggregated trends across all exported field reports.</p>
        </div>
      </div>

      <div className="grid cols-4 section">
        <StatCard label="Healthy" value={t.healthy} color="#52b788" />
        <StatCard label="Stressed" value={t.stressed} color="#d4a373" />
        <StatCard label="Diseased" value={t.diseased} color="#bc4749" />
        <StatCard label="Distinct classes" value={classData.length} />
      </div>

      <div className="grid cols-2 section">
        <div className="card">
          <h3>Detections by class label</h3>
          <p className="sub">Class names parsed from detection labels across all reports.</p>
          <div className="chart-box">
            {classData.length === 0 ? (
              <div className="empty">No detections yet</div>
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
          <h3>Vegetation stress trend</h3>
          <p className="sub">Mean ExG-proxy stress and high-stress pixel percentage per report.</p>
          <div className="chart-box">
            {stress.length === 0 ? (
              <div className="empty">No vegetation data yet</div>
            ) : (
              <ResponsiveContainer>
                <LineChart data={stress}>
                  <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                  <XAxis dataKey="report_id" tick={{ fill: "#5e7268", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#5e7268", fontSize: 11 }} unit="%" />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#16221b" }} />
                  <Legend wrapperStyle={{ color: "#5e7268" }} />
                  <Line type="monotone" dataKey="mean_stress_pct" name="Mean stress %" stroke="#e9c46a" dot strokeWidth={2} />
                  <Line type="monotone" dataKey="high_stress_pct" name="High-stress area %" stroke="#bc4749" dot strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Overall vegetation health labels</h3>
        <p className="sub">Distribution of the health verdict (good / fair / poor) across reports.</p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {Object.entries(data.health_label_distribution).map(([label, count]) => (
            <span
              key={label}
              className={`pill ${label === "good" ? "healthy" : label === "fair" ? "stressed" : "diseased"}`}
              style={{ fontSize: 14, padding: "8px 16px" }}
            >
              {label}: {count} report{count === 1 ? "" : "s"}
            </span>
          ))}
          {Object.keys(data.health_label_distribution).length === 0 && (
            <span className="muted">No vegetation labels recorded yet.</span>
          )}
        </div>
      </div>
    </>
  );
}
