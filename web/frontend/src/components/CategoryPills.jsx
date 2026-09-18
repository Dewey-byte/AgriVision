import React from "react";

export function SummaryPills({ summary }) {
  const s = summary || {};
  return (
    <span style={{ display: "inline-flex", gap: 6, flexWrap: "wrap" }}>
      <span className="pill healthy">{s.healthy ?? 0} healthy</span>
      <span className="pill stressed">{s.stressed ?? 0} stressed</span>
      <span className="pill diseased">{s.diseased ?? 0} diseased</span>
    </span>
  );
}

export function HealthPill({ label }) {
  if (!label) return <span className="pill neutral">n/a</span>;
  const cls =
    label === "good" ? "healthy" : label === "fair" ? "stressed" : "diseased";
  return <span className={`pill ${cls}`}>{label}</span>;
}

const MODEL_PILL = {
  yolov9s: "healthy",
  yolov9t: "model",
  yolov8n: "stressed",
};

export function ModelPill({ detector }) {
  const det = detector || {};
  const name = det.name || det.id;
  if (!name) return <span className="pill neutral">Model: not recorded</span>;
  const cls = MODEL_PILL[(det.id || "").toLowerCase()] || "model";
  const title = det.weights ? `${name} · ${det.weights}` : name;
  return (
    <span className={`pill ${cls}`} title={title}>
      Model: {name}
    </span>
  );
}

export function modelLabel(detector) {
  const det = detector || {};
  const name = det.name || det.id;
  if (!name) return "Model not recorded";
  return det.weights ? `Detected with ${name} (${det.weights})` : `Detected with ${name}`;
}
