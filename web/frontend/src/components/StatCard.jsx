import React from "react";

export default function StatCard({ label, value, hint, color }) {
  return (
    <div className="card stat-card">
      <div className="label">{label}</div>
      <div className="value" style={color ? { color } : undefined}>
        {value}
      </div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}
