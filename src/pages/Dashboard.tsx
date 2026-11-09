import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  CarFront,
  Image as ImageIcon,
  ScanSearch,
  UserRound,
} from "lucide-react";

import ImageDetectionWorkbench from "../components/dashboard/ImageDetectionWorkbench";
import {
  checkBackendHealth,
  getApiErrorMessage,
  getDashboardSummary,
  getImagePreviewUrl,
  type DashboardSummary,
} from "../services/api";

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryError, setSummaryError] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<
    "checking" | "online" | "offline"
  >("checking");

  const refreshSummary = async () => {
    try {
      const nextSummary = await getDashboardSummary();
      setSummary(nextSummary);
      setSummaryError("");
    } catch (error) {
      setSummaryError(getApiErrorMessage(error));
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const refreshBackendStatus = async () => {
      try {
        const online = await checkBackendHealth();
        if (active) setBackendStatus(online ? "online" : "offline");
      } catch {
        if (active) setBackendStatus("offline");
      }
    };

    void refreshBackendStatus();
    const intervalId = window.setInterval(() => {
      void refreshBackendStatus();
    }, 15_000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    void refreshSummary();
  }, []);

  const cards = [
    { label: "Images Uploaded", value: summary?.total_images, icon: ImageIcon, tone: "blue" },
    { label: "Detected Objects", value: summary?.total_detections, icon: ScanSearch, tone: "cyan" },
    { label: "People / Pedestrians", value: summary?.pedestrian_count, icon: UserRound, tone: "green" },
    { label: "Motor Vehicles", value: summary?.vehicle_count, icon: CarFront, tone: "orange" },
    { label: "Surveys", value: summary?.total_surveys, icon: Activity, tone: "violet" },
  ] as const;

  return (
    <div className="intelligence-dashboard">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">AERIAL IMAGERY / LIVE WORKSPACE</p>
          <h1>Drone Imagery Intelligence</h1>
          <p>Upload an image, run object detection, and review database-backed results.</p>
        </div>
        <div className={`backend-indicator backend-${backendStatus}`} role="status">
          <span className="backend-indicator-dot" />
          <span>
            {backendStatus === "checking"
              ? "Checking backend"
              : backendStatus === "online"
                ? "Backend online"
                : "Backend unavailable"}
          </span>
          <Activity size={16} aria-hidden="true" />
        </div>
      </header>

      <section className="live-summary" aria-label="Workspace summary">
        {cards.map(({ label, value, icon: Icon, tone }) => (
          <article className="live-stat" key={label}>
            <span className={`live-stat-icon tone-${tone}`}><Icon size={18} /></span>
            <div className="live-stat-copy">
              <span className="live-stat-label">{label}</span>
              <strong>
                {value === undefined
                  ? summaryLoading ? "Loading…" : "Unavailable"
                  : value.toLocaleString()}
              </strong>
              {(label === "People / Pedestrians" || label === "Motor Vehicles") && summary && (
                <small className="stat-definition">
                  {label === "People / Pedestrians"
                    ? `Includes ${summary.category_definitions.pedestrians.join(" and ")}`
                    : `Includes ${summary.category_definitions.vehicles.join(", ")}`}
                </small>
              )}
            </div>
          </article>
        ))}
        <article className="live-stat average-confidence-stat">
          <span className="live-stat-icon tone-violet"><Activity size={18} /></span>
          <div className="live-stat-copy">
            <span className="live-stat-label">Average Confidence</span>
            <strong>
              {summary?.average_confidence === null
                ? "No detections"
                : summary
                  ? `${(summary.average_confidence * 100).toFixed(2)}%`
                  : summaryLoading ? "Loading…" : "Unavailable"}
            </strong>
          </div>
        </article>
      </section>

      {summaryError && (
        <div className="dashboard-inline-error" role="alert">{summaryError}</div>
      )}

      <section className="dashboard-live-grid" aria-label="Recent workspace activity">
        <article className="workbench-panel dashboard-recent-panel">
          <div className="dashboard-section-heading">
            <div>
              <p className="panel-kicker">LATEST INGESTION</p>
              <h2>Recent images</h2>
            </div>
            <Link to="/upload" className="dashboard-text-link">Upload imagery</Link>
          </div>
          {summary?.recent_images.length ? (
            <div className="recent-image-grid">
              {summary.recent_images.slice(0, 4).map((image) => (
                <Link
                  className="recent-image-card"
                  key={image.image_id}
                  to={`/analysis?image_id=${image.image_id}`}
                >
                  <img src={getImagePreviewUrl(image.image_id)} alt="" loading="lazy" />
                  <span>{image.filename}</span>
                  <small>{image.detection_count ?? 0} stored detections</small>
                </Link>
              ))}
            </div>
          ) : (
            <p className="dashboard-empty-note">
              {summaryLoading ? "Loading recent images…" : "No uploaded images yet."}
            </p>
          )}
        </article>

        <article className="workbench-panel dashboard-recent-panel">
          <div className="dashboard-section-heading">
            <div>
              <p className="panel-kicker">MODEL ACTIVITY</p>
              <h2>Recent detections</h2>
            </div>
            <Link to="/analytics" className="dashboard-text-link">View analytics</Link>
          </div>
          {summary?.recent_activity.length ? (
            <ul className="recent-activity-list">
              {summary.recent_activity.slice(0, 6).map((activity) => (
                <li key={activity.id}>
                  <Link to={`/analysis?image_id=${activity.image_id}`}>
                    <span><strong>{activity.class_name}</strong> · {activity.filename}</span>
                    <small>
                      {activity.model_version ?? "Model unavailable"} ·{" "}
                      {(activity.confidence * 100).toFixed(1)}%
                    </small>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dashboard-empty-note">
              {summaryLoading ? "Loading detection activity…" : "No persisted detections yet."}
            </p>
          )}
        </article>
      </section>

      <ImageDetectionWorkbench onDetectionComplete={refreshSummary} />
    </div>
  );
}
