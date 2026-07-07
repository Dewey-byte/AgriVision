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
