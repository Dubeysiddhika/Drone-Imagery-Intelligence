import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Image as ImageIcon, ScanSearch, Target } from "lucide-react";

import {
  getApiErrorMessage,
  getDashboardSummary,
  type DashboardSummary,
} from "../services/api";

const chartColors = [
  "#16847c", "#e68543", "#8b5cf6", "#3b82f6", "#eab308",
  "#ef4444", "#06b6d4", "#ec4899", "#84cc16", "#64748b",
];

export default function Analytics() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getDashboardSummary()
      .then((result) => {
        if (active) setSummary(result);
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const classCounts = summary?.class_counts ?? [];
  const hasDetections = classCounts.some((item) => item.count > 0);

  return (
    <div className="analytics-workspace">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">MODEL OUTPUT / DATABASE AGGREGATES</p>
          <h1>Detection Analytics</h1>
          <p>Counts and confidence are computed from persisted detections.</p>
        </div>
        {summary?.model_version && (
          <span className="model-version-chip">
            {summary.model_name} · {summary.model_version}
          </span>
        )}
      </header>

      {error && <div className="dashboard-inline-error" role="alert">{error}</div>}

      <section className="analytics-stat-grid" aria-label="Detection statistics">
        <AnalyticsStat
          icon={<ImageIcon size={18} />}
          title="Uploaded images"
          value={summary?.total_images}
          loading={loading}
        />
        <AnalyticsStat
          icon={<ScanSearch size={18} />}
          title="Persisted detections"
          value={summary?.total_detections}
          loading={loading}
        />
        <AnalyticsStat
          icon={<Activity size={18} />}
          title="Surveys"
          value={summary?.total_surveys}
          loading={loading}
        />
        <AnalyticsStat
          icon={<Target size={18} />}
          title="Average confidence"
          value={summary?.average_confidence === null
            ? "No detections"
            : summary?.average_confidence === undefined
              ? undefined
              : `${(summary.average_confidence * 100).toFixed(2)}%`}
          loading={loading}
        />
      </section>

      {loading ? (
        <div className="map-empty-state" role="status">Loading persisted analytics…</div>
      ) : hasDetections ? (
        <div className="analytics-chart-grid">
          <article className="workbench-panel analytics-chart-card">
            <div className="dashboard-section-heading">
              <div>
                <p className="panel-kicker">CLASS DISTRIBUTION</p>
                <h2>Objects by class</h2>
              </div>
            </div>
            <div className="analytics-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={classCounts} margin={{ top: 8, right: 12, bottom: 36, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="class_name"
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                    tick={{ fontSize: 10 }}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" name="Detections" radius={[5, 5, 0, 0]}>
                    {classCounts.map((entry, index) => (
                      <Cell key={entry.class_name} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
          <article className="workbench-panel analytics-chart-card">
            <div className="dashboard-section-heading">
              <div>
                <p className="panel-kicker">SHARE OF RESULTS</p>
                <h2>Detection distribution</h2>
              </div>
            </div>
            <div className="analytics-chart">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={classCounts}
                    dataKey="count"
                    nameKey="class_name"
                    cx="50%"
                    cy="48%"
                    outerRadius={112}
                    label={({ name, percent }) =>
                      `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                  >
                    {classCounts.map((entry, index) => (
                      <Cell key={entry.class_name} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </article>
        </div>
      ) : (
        <div className="map-empty-state">
          <strong>No persisted detections to chart.</strong>
          <span>Upload an image and run a model to populate class analytics.</span>
        </div>
      )}

      {summary && (
        <p className="analytics-category-note">
          People/pedestrians group: {summary.category_definitions.pedestrians.join(", ")}.
          Motor-vehicle group: {summary.category_definitions.vehicles.join(", ")}.
          Bicycle counts remain separate.
        </p>
      )}
    </div>
  );
}

function AnalyticsStat({
  icon,
  title,
  value,
  loading,
}: {
  icon: React.ReactNode;
  title: string;
  value: number | string | undefined;
  loading: boolean;
}) {
  return (
    <article className="workbench-panel analytics-stat-card">
      <span className="analytics-stat-icon">{icon}</span>
      <span>{title}</span>
      <strong>
        {value === undefined
          ? loading ? "Loading…" : "Unavailable"
          : typeof value === "number" ? value.toLocaleString() : value}
      </strong>
    </article>
  );
}
