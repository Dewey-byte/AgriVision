import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { api } from "../api.js";
import StatCard from "../components/StatCard.jsx";
import { SummaryPills, HealthPill } from "../components/CategoryPills.jsx";

const CAT_COLORS = { healthy: "#52b788", stressed: "#d4a373", diseased: "#bc4749" };

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api("/api/analytics/overview"), api("/api/sessions")])
      .then(([overview, sess]) => {
        setData(overview);
        setSessions(sess.items.slice(0, 5));
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">Failed to load: {error}</div>;
  if (!data) return <div className="spinner">Loading dashboard…</div>;

  const t = data.detection_totals;
  const pieData = [
    { name: "Healthy", value: t.healthy, key: "healthy" },
    { name: "Stressed", value: t.stressed, key: "stressed" },
    { name: "Diseased", value: t.diseased, key: "diseased" },
  ].filter((d) => d.value > 0);

  const series = data.detections_over_time.map((d) => ({
    ...d,
    time: d.exported_at.replace("T", " "),
  }));

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Dashboard</h2>
          <p>Historical overview of all field operations recorded by the desktop app.</p>
        </div>
        <Link className="btn ghost" to="/records">
          Browse records →
        </Link>
      </div>

      <div className="grid cols-4 section">
        <StatCard label="Field Reports" value={data.report_count} hint="exported bundles in output/reports" />
        <StatCard label="Flight Sessions" value={data.session_count} hint="grouped by session start" />
        <StatCard label="Total Detections" value={t.total} hint="across all exported reports" />
        <StatCard
          label="Healthy Rate"
          value={`${data.healthy_pct}%`}
          color={data.healthy_pct >= 70 ? "#52b788" : data.healthy_pct >= 40 ? "#d4a373" : "#bc4749"}
          hint="healthy / total detections"
        />
      </div>

      <div className="grid cols-2 section">
        <div className="card">
          <h3>Detections per report</h3>
          <div className="chart-box">
            <ResponsiveContainer>
              <AreaChart data={series}>
                <CartesianGrid stroke="#2b4234" strokeDasharray="3 3" />
                <XAxis dataKey="report_id" tick={{ fill: "#93ab99", fontSize: 11 }} />
                <YAxis tick={{ fill: "#93ab99", fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1a2a21", border: "1px solid #2b4234", borderRadius: 10 }}
                  labelStyle={{ color: "#e8f2ea" }}
                />
                <Area type="monotone" dataKey="healthy" stackId="1" stroke={CAT_COLORS.healthy} fill={CAT_COLORS.healthy} fillOpacity={0.5} />
                <Area type="monotone" dataKey="stressed" stackId="1" stroke={CAT_COLORS.stressed} fill={CAT_COLORS.stressed} fillOpacity={0.5} />
                <Area type="monotone" dataKey="diseased" stackId="1" stroke={CAT_COLORS.diseased} fill={CAT_COLORS.diseased} fillOpacity={0.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3>Health category distribution</h3>
          <div className="chart-box">
            {pieData.length === 0 ? (
              <div className="empty">No detections yet</div>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>
                    {pieData.map((d) => (
                      <Cell key={d.key} fill={CAT_COLORS[d.key]} />
                    ))}
                  </Pie>
                  <Legend wrapperStyle={{ color: "#93ab99" }} />
                  <Tooltip contentStyle={{ background: "#1a2a21", border: "1px solid #2b4234", borderRadius: 10 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Recent flight sessions</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Video ID</th>
                <th>Started</th>
                <th>Reports</th>
                <th>Frames</th>
                <th>Last summary</th>
                <th>Vegetation</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id}>
                  <td className="mono">{s.video_id}</td>
                  <td>{(s.started_at || "").replace("T", " ")}</td>
                  <td>{s.report_count}</td>
                  <td>
                    {s.frames_processed} <span className="muted">({s.frames_analyzed} analyzed)</span>
                  </td>
                  <td>
                    <SummaryPills summary={s.last_detection_summary} />
                  </td>
                  <td>
                    <HealthPill label={s.last_vegetation?.health_label} />
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty">
                    No sessions recorded yet — export a field report from the desktop app.
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
