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

// Stable per-contender colours so a model keeps its colour across every chart.
const SERIES_COLORS = ["#2d6a4f", "#d4a373", "#457b9d", "#bc4749", "#7d5ba6"];

const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(2)}%`);
const pct1 = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

function colorFor(id, series) {
  const index = series.findIndex((s) => s.id === id);
  return SERIES_COLORS[(index < 0 ? 0 : index) % SERIES_COLORS.length];
}

function Leaderboard({ bench, series }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Model</th>
            <th>mAP@0.5</th>
            <th>mAP@0.5:0.95</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1</th>
            <th>Params</th>
            <th>Inference</th>
          </tr>
        </thead>
        <tbody>
          {bench.contenders.map((c) => {
            if (!c.evaluated) {
              return (
                <tr key={c.id}>
                  <td className="muted">—</td>
                  <td>
                    <strong>{c.name}</strong>
                    <div className="muted" style={{ fontSize: 11.5 }}>{c.family}</div>
                  </td>
                  <td colSpan={7} className="muted">
                    Not evaluated yet — no results in output/metrics/benchmarks
                  </td>
                </tr>
              );
            }
            const o = c.overall;
            const inference = c.speed_ms_per_image?.inference;
            return (
              <tr key={c.id} style={c.is_best ? { background: "rgba(64,145,108,0.10)" } : undefined}>
                <td>
                  <span className={`pill ${c.is_best ? "healthy" : "neutral"}`}>{c.rank}</span>
                </td>
                <td>
                  <strong style={{ color: colorFor(c.id, series) }}>{c.name}</strong>
                  <div className="muted" style={{ fontSize: 11.5 }}>{c.family}</div>
                </td>
                <td>
                  <strong>{pct(o.mAP50)}</strong>
                </td>
                <td>{pct(o.mAP50_95)}</td>
                <td>{pct1(o.precision)}</td>
                <td>{pct1(o.recall)}</td>
                <td>{pct1(o.f1)}</td>
                <td>{c.params_millions ? `${c.params_millions.toFixed(2)} M` : "—"}</td>
                <td>{inference ? `${inference.toFixed(1)} ms` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BenchmarkSection({ bench }) {
  const series = bench.series || [];
  const scored = bench.contenders.filter((c) => c.evaluated);

  if (scored.length === 0) {
    return (
      <div className="card section">
        <h3>Head-to-head accuracy</h3>
        <p className="sub">{bench.protocol}</p>
        <div className="empty">
          No benchmark results yet. Train the contenders, then run{" "}
          <code className="mono">python tools/benchmark_models.py</code> to score them all on the
          same held-out split.
        </div>
      </div>
    );
  }

  const overallChart = scored.map((c) => ({
    name: c.name,
    map50: c.overall.mAP50,
    map50_95: c.overall.mAP50_95,
  }));

  return (
    <>
      <div className="card section">
        <h3>Head-to-head accuracy — {bench.split} split</h3>
        <p className="sub">{bench.protocol}</p>
        {bench.best && (
          <p style={{ margin: "0 0 14px", fontSize: 14 }}>
            <strong style={{ color: "var(--green)" }}>{bench.best.name}</strong> is the most
            accurate of the {scored.length} evaluated model{scored.length === 1 ? "" : "s"}, at{" "}
            <strong>{pct(bench.best.overall.mAP50)}</strong> mAP@0.5 and{" "}
            <strong>{pct(bench.best.overall.mAP50_95)}</strong> mAP@0.5:0.95.
          </p>
        )}
        <Leaderboard bench={bench} series={series} />
        {bench.pending?.length > 0 && (
          <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
            Awaiting evaluation: {bench.pending.join(", ")}.
          </p>
        )}
      </div>

      <div className="grid cols-2 section">
        <div className="card">
          <h3>Overall accuracy</h3>
          <p className="sub">Mean average precision on the held-out {bench.split} split.</p>
          <div className="chart-box">
            <ResponsiveContainer>
              <BarChart data={overallChart}>
                <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fill: "#5e7268", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#5e7268", fontSize: 11 }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: "#16221b" }}
                  formatter={(v) => pct1(v)}
                />
                <Legend wrapperStyle={{ color: "#5e7268" }} />
                <Bar dataKey="map50" name="mAP@0.5" fill="#52b788" radius={[6, 6, 0, 0]} />
                <Bar dataKey="map50_95" name="mAP@0.5:0.95" fill="#2d6a4f" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3>Per-class mAP@0.5</h3>
          <p className="sub">
            Where each architecture wins or collapses — the rare classes are the hard ones.
          </p>
          <div className="chart-box">
            <ResponsiveContainer>
              <BarChart data={bench.per_class_matrix}>
                <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                <XAxis dataKey="class" tick={{ fill: "#5e7268", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#5e7268", fontSize: 11 }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: "#16221b" }}
                  formatter={(v) => pct1(v)}
                />
                <Legend wrapperStyle={{ color: "#5e7268" }} />
                {series.map((s) => (
                  <Bar
                    key={s.id}
                    dataKey={s.id}
                    name={s.name}
                    fill={colorFor(s.id, series)}
                    radius={[6, 6, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {bench.curve_series?.length > 0 && (
        <div className="card section">
          <h3>Convergence</h3>
          <p className="sub">
            Validation mAP@0.5 per epoch for every contender, on one axis — shows which
            architecture learns this dataset faster, not just which ends up ahead.
          </p>
          <div className="chart-box">
            <ResponsiveContainer>
              <LineChart data={bench.convergence}>
                <CartesianGrid stroke="#dde5e0" strokeDasharray="3 3" />
                <XAxis dataKey="epoch" tick={{ fill: "#5e7268", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#5e7268", fontSize: 11 }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: "#16221b" }}
                  formatter={(v) => pct1(v)}
                />
                <Legend wrapperStyle={{ color: "#5e7268" }} />
                {bench.curve_series.map((s) => (
                  <Line
                    key={s.id}
                    type="monotone"
                    dataKey={s.id}
                    name={s.name}
                    stroke={colorFor(s.id, series)}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="card section">
        <h3>Full per-class breakdown</h3>
        <p className="sub">
          mAP@0.5 for every class and contender on the {bench.split} split, with the number of
          ground-truth boxes available to score against.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th>Instances</th>
                {series.map((s) => (
                  <th key={s.id}>{s.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bench.per_class_matrix.map((row) => {
                const best = Math.max(...series.map((s) => row[s.id] ?? 0));
                return (
                  <tr key={row.class}>
                    <td className="mono">{row.class}</td>
                    <td>{row.instances}</td>
                    {series.map((s) => (
                      <td key={s.id}>
                        {row[s.id] != null && row[s.id] === best && best > 0 ? (
                          <strong style={{ color: colorFor(s.id, series) }}>{pct1(row[s.id])}</strong>
                        ) : (
                          pct1(row[s.id])
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid cols-3 section">
        {bench.contenders.map((c) => (
          <div className="card" key={`notes-${c.id}`}>
            <h3 style={{ marginBottom: 6 }}>{c.name}</h3>
            <span className={`pill ${c.is_best ? "healthy" : "neutral"}`}>
              {c.evaluated ? (c.is_best ? "most accurate" : `rank ${c.rank}`) : "pending"}
            </span>
            <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>
              {c.notes}
            </p>
            <dl className="kv">
              <dt>Family</dt>
              <dd>{c.family}</dd>
              <dt>Trained by</dt>
              <dd className="mono">{c.runner}</dd>
              <dt>Weights</dt>
              <dd className="mono">{c.weights}</dd>
              {c.training?.epochs_trained != null && (
                <>
                  <dt>Epochs</dt>
                  <dd>{c.training.epochs_trained}</dd>
                </>
              )}
              {c.evaluated_at && (
                <>
                  <dt>Evaluated</dt>
                  <dd>{c.evaluated_at.slice(0, 16).replace("T", " ")} UTC</dd>
                </>
              )}
            </dl>
          </div>
        ))}
      </div>
    </>
  );
}

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
  const bench = data.benchmark;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Model Comparison</h2>
          <p>
            Architecture benchmark — YOLOv8, YOLOv9 and YOLO-NAS scored on one held-out split —
            followed by the models the desktop pipeline actually deploys.
          </p>
        </div>
      </div>

      {bench?.contenders?.length > 0 && <BenchmarkSection bench={bench} />}

      <div className="page-head" style={{ marginTop: 8 }}>
        <div>
          <h2 style={{ fontSize: 18 }}>Deployed pipeline</h2>
          <p>
            The deployed aerial detector, the two-stage leaf classifier, and the
            secondary-dataset retraining track.
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
