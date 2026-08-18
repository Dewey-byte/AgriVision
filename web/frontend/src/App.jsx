import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { getToken, setToken } from "./api.js";
import Layout from "./components/Layout.jsx";
import Login from "./components/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Records from "./pages/Records.jsx";
import Analytics from "./pages/Analytics.jsx";
import ModelComparison from "./pages/ModelComparison.jsx";
import DiseaseMap from "./pages/DiseaseMap.jsx";
import Reports from "./pages/Reports.jsx";

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));

  useEffect(() => {
    const onUnauthorized = () => setAuthed(false);
    window.addEventListener("agrivision:unauthorized", onUnauthorized);
    return () => window.removeEventListener("agrivision:unauthorized", onUnauthorized);
  }, []);

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  const logout = () => {
    setToken("");
    setAuthed(false);
  };

  return (
    <Layout onLogout={logout}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/records" element={<Records />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/models" element={<ModelComparison />} />
        <Route path="/disease-map" element={<DiseaseMap />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/reports/:reportId" element={<Reports />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
