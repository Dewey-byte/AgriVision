import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api.js";
import StatCard from "../components/StatCard.jsx";

const CAT_COLORS = { healthy: "#40916c", stressed: "#d4a373", diseased: "#bc4749" };
const DEFAULT_CENTER = [7.3669, 125.91]; // Compostela Valley fallback (matches desktop app)

export default function DiseaseMap() {
  const mapEl = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [radius, setRadius] = useState(25);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/maps/disease?cluster_radius_m=${radius}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [radius]);

  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    const map = L.map(mapEl.current).setView(DEFAULT_CENTER, 15);
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "Tiles © Esri — World Imagery", maxZoom: 19 }
    ).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer || !data) return;
    layer.clearLayers();

    const bounds = [];

    data.report_markers.forEach((m) => {
      bounds.push([m.lat, m.lon]);
      L.circleMarker([m.lat, m.lon], {
        radius: 7,
        color: "#74c69d",
        weight: 2,
        fillColor: "#1a2a21",
        fillOpacity: 0.9,
      })
        .bindPopup(
          `<b>Report ${m.report_id}</b><br/>Video: ${m.video_id}<br/>` +
            `Detections: ${m.summary.total} (H ${m.summary.healthy} / S ${m.summary.stressed} / D ${m.summary.diseased})<br/>` +
            `${m.exported_at}`
        )
        .addTo(layer);
    });

    data.points.forEach((p) => {
      bounds.push([p.lat, p.lon]);
      L.circleMarker([p.lat, p.lon], {
        radius: 6,
        color: CAT_COLORS[p.category] || "#74c69d",
        weight: 2,
        fillColor: CAT_COLORS[p.category] || "#74c69d",
        fillOpacity: 0.7,
      })
        .bindPopup(`<b>${p.label || p.category}</b><br/>Report ${p.report_id}<br/>Video: ${p.video_id}`)
        .addTo(layer);
    });

    data.disease_clusters.forEach((c) => {
      bounds.push([c.lat, c.lon]);
      L.circle([c.lat, c.lon], {
        radius: c.radius_m,
        color: CAT_COLORS[c.dominant_category] || "#bc4749",
        weight: 2,
        dashArray: "6 4",
        fillColor: CAT_COLORS[c.dominant_category] || "#bc4749",
        fillOpacity: 0.18,
      })
        .bindPopup(
          `<b>Disease cluster #${c.cluster_id}</b><br/>` +
            `Dominant: ${c.dominant_category}<br/>` +
            `Points: ${c.point_count}<br/>` +
            `Affected radius: ~${c.radius_m} m<br/>` +
            `Reports: ${c.reports.join(", ")}`
        )
        .addTo(layer);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
    }
  }, [data]);

  const clusterCount = data?.disease_clusters.length ?? 0;
  const affectedPoints = data ? data.points.filter((p) => p.category !== "healthy").length : 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Disease Radius Map</h2>
          <p>
            Confirmed disease/stress tags clustered into affected zones with an
            estimated radius. Report GPS centers shown as outlined markers.
          </p>
        </div>
        <div className="toolbar">
          <label className="muted">Cluster radius: {radius} m</label>
          <input
            type="range"
            min="5"
            max="200"
            step="5"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          />
        </div>
      </div>

      {error && <div className="empty">Failed to load: {error}</div>}

      <div className="grid cols-3 section">
        <StatCard label="Disease clusters" value={clusterCount} hint={`grouped within ${radius} m`} color={clusterCount ? "#bc4749" : undefined} />
        <StatCard label="Affected tag points" value={affectedPoints} hint="stressed + diseased manual tags" />
        <StatCard label="Report locations" value={data?.report_markers.length ?? 0} hint="GPS centers of exported reports" />
      </div>

      <div className="map-frame">
        <div ref={mapEl} className="leaflet-host" />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Clusters</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Dominant</th>
                <th>Center</th>
                <th>Radius</th>
                <th>Points</th>
                <th>Reports</th>
              </tr>
            </thead>
            <tbody>
              {(data?.disease_clusters || []).map((c) => (
                <tr key={c.cluster_id}>
                  <td>{c.cluster_id}</td>
                  <td>
                    <span className={`pill ${c.dominant_category}`}>{c.dominant_category}</span>
                  </td>
                  <td className="mono">
                    {c.lat.toFixed(6)}, {c.lon.toFixed(6)}
                  </td>
                  <td>~{c.radius_m} m</td>
                  <td>{c.point_count}</td>
                  <td className="mono">{c.reports.join(", ")}</td>
                </tr>
              ))}
              {clusterCount === 0 && (
                <tr>
                  <td colSpan={6} className="empty">
                    No stressed/diseased tags recorded yet — tag spots on the desktop
                    app's field map, then export a report.
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
