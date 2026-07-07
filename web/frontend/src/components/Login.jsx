import React, { useState } from "react";
import { login } from "../api.js";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      onLogin();
    } catch (err) {
      setError(err.status === 401 ? "Invalid credentials" : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-logo">A</div>
          <div>
            <h1>AgriVision</h1>
            <p>Administrative access</p>
          </div>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Central hub for field records, analytics, and model oversight. Live
          detection stays on the desktop operator app.
        </p>
        <input
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <input
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <div className="error-text">{error}</div>}
        <button disabled={busy || !username || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
