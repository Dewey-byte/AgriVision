import React from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", ico: "◆", end: true },
  { to: "/records", label: "Records", ico: "☰" },
  { to: "/analytics", label: "Analytics", ico: "▤" },
  { to: "/models", label: "Model Comparison", ico: "⚖" },
  { to: "/disease-map", label: "Disease Map", ico: "◎" },
  { to: "/reports", label: "Reports", ico: "▣" },
];

export default function Layout({ children, onLogout }) {
  return (
    <div className="shell">
      <aside className="sidenav">
        <div className="brand">
          <div className="brand-logo">A</div>
          <div>
            <h1>AgriVision</h1>
            <p>Admin Dashboard</p>
          </div>
        </div>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `navlink${isActive ? " active" : ""}`}
          >
            <span className="ico">{item.ico}</span>
            {item.label}
          </NavLink>
        ))}
        <div className="nav-footer">
          Signed in as <strong>admin</strong>
          <button className="ghost" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
