import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  BarChart,
  Bar,
} from "recharts";
import { api } from "../api.js";

const TOOLTIP_STYLE = {
  background: "#ffffff",
  border: "1px solid #dde5e0",
  borderRadius: 10,
};

const STATUS_PILL = {
  deployed: "healthy",
  optional: "stressed",
  planned: "neutral",
};

export default function ModelComparison() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/analytics/models")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">Failed to load: {error}</div>;
  if (!data) return <div className="spinner">Loading model data…</div>;

  const withCurve = data.models.filter((m) => (m.training_curve || []).length > 0);
  const classMetrics = data.class_metrics || [];

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Model Comparison</h2>
          <p>
            Three-model line-up: the deployed aerial detector, the two-stage leaf
            classifier, and the secondary-dataset retraining track.
          </p>
        </div>
      </div>

      <div className="grid cols-3 section">
        {data.models.map((m) => (
          <div className="card" key={m.id}>
            <h3 style={{ marginBottom: 6 }}>{m.name}</h3>
            <span className={`pill ${STATUS_PILL[m.status] || "neutral"}`}>{m.status}</span>
            <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>
              {m.description}
            </p>
            <dl className="kv">
              <dt>Task</dt>
              <dd>{m.task}</dd>
              <dt>Weights</dt>
              <dd className="mono">{m.weights}</dd>
              <dt>Dataset</dt>
              <dd>{m.dataset}</dd>
              {m.metrics?.best_map50 != null && (
                <>
                  <dt>Best mAP@0.5</dt>
                  <dd>
                    <strong>{(m.metrics.best_map50 * 100).toFixed(2)}%</strong>
                  </dd>
                  <dt>Epochs</dt>
                  <dd>{m.metrics.epochs_trained}</dd>
                  <dt>Final P / R</dt>
                  <dd>
                    {(m.metrics.final_precision * 100).toFixed(1)}% /{" "}
                    {(m.metrics.final_recall * 100).toFixed(1)}%
                  </dd>
                </>
              )}
              {m.metrics?.best_map50 == null && (
                <>
                  <dt>Metrics</dt>
                  <dd className="muted">not yet available</dd>
                </>
              )}
            </dl>
          </div>
        ))}
      </div>

      {withCurve.map((m) => (
        <div className="card section" key={`curve-${m.id}`}>
          <h3>Training curves — {m.name}</h3>
          <p className="sub">Per-epoch validation mAP@0.5, precision, recall, and losses from results.csv.</p>
          <div className="grid cols-2">
            <div className="chart-box">
              <ResponsiveContainer>
                <LineChart data={m.training_curve}>
                  <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                  <XAxis dataKey="epoch" tick={{ fill: "#5e7268", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#5e7268", fontSize: 11 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#16221b" }} />
                  <Legend wrapperStyle={{ color: "#5e7268" }} />
                  <Line type="monotone" dataKey="map50" name="mAP@0.5" stroke="#52b788" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="precision" name="Precision" stroke="#74c69d" dot={false} strokeDasharray="4 3" />
                  <Line type="monotone" dataKey="recall" name="Recall" stroke="#d4a373" dot={false} strokeDasharray="4 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-box">
              <ResponsiveContainer>
                <LineChart data={m.training_curve}>
                  <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                  <XAxis dataKey="epoch" tick={{ fill: "#5e7268", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#5e7268", fontSize: 11 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#16221b" }} />
                  <Legend wrapperStyle={{ color: "#5e7268" }} />
                  <Line type="monotone" dataKey="train_loss" name="Train loss (box+cls)" stroke="#e9c46a" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="val_loss" name="Val loss (box+cls)" stroke="#bc4749" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ))}

      <div className="card">
        <h3>Per-class validation metrics (deployed detector)</h3>
        <p className="sub">Validation split results for models/best.pt — highlights the class-imbalance gap the secondary datasets target.</p>
        <div className="grid cols-2">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Class</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>mAP@0.5</th>
                  <th>mAP@0.5:0.95</th>
                </tr>
              </thead>
              <tbody>
                {classMetrics.map((c) => (
                  <tr key={c.class}>
                    <td className="mono">{c.class}</td>
                    <td>{(c.precision * 100).toFixed(1)}%</td>
                    <td>{(c.recall * 100).toFixed(1)}%</td>
                    <td>
                      <strong>{(c.map50 * 100).toFixed(1)}%</strong>
                    </td>
                    <td>{(c.map50_95 * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="chart-box">
            <ResponsiveContainer>
              <BarChart data={classMetrics.filter((c) => c.class !== "all")}>
                <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                <XAxis dataKey="class" tick={{ fill: "#5e7268", fontSize: 11 }} />
                <YAxis tick={{ fill: "#5e7268", fontSize: 11 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#16221b" }} formatter={(v) => `${(v * 100).toFixed(1)}%`} />
                <Legend wrapperStyle={{ color: "#5e7268" }} />
                <Bar dataKey="map50" name="mAP@0.5" fill="#52b788" radius={[6, 6, 0, 0]} />
                <Bar dataKey="map50_95" name="mAP@0.5:0.95" fill="#2d6a4f" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </>
  );
}
