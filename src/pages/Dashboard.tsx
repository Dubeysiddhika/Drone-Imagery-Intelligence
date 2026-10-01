import { useEffect, useState } from "react";
import {
  Activity,
  CarFront,
  Image as ImageIcon,
  ScanSearch,
  UserRound,
} from "lucide-react";

import ImageDetectionWorkbench from "../components/dashboard/ImageDetectionWorkbench";
import {
  getApiErrorMessage,
  getWorkspaceSummary,
  checkBackendHealth,
  type WorkspaceSummary,
} from "../services/api";

export default function Dashboard() {
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [summaryError, setSummaryError] = useState("");
  const [backendStatus, setBackendStatus] = useState<
    "checking" | "online" | "offline"
  >("checking");

  const refreshSummary = async () => {
    try {
      const nextSummary = await getWorkspaceSummary();
      setSummary(nextSummary);
      setSummaryError("");
    } catch (error) {
      setSummaryError(getApiErrorMessage(error));
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
    { label: "Total Images", value: summary?.totalImages, icon: ImageIcon, tone: "blue" },
    { label: "Total Detections", value: summary?.totalDetections, icon: ScanSearch, tone: "cyan" },
    { label: "Persons Detected", value: summary?.persons, icon: UserRound, tone: "green" },
    { label: "Vehicles Detected", value: summary?.vehicles, icon: CarFront, tone: "orange" },
  ] as const;

  return (
    <div className="intelligence-dashboard">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">AERIAL IMAGERY / LIVE WORKSPACE</p>
          <h1>Drone Imagery Intelligence</h1>
          <p>Upload a survey image, run object detection, and review the measured results.</p>
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
              <strong>{value === undefined ? "—" : value.toLocaleString()}</strong>
            </div>
          </article>
        ))}
        <article className="live-stat average-confidence-stat">
          <span className="live-stat-icon tone-violet"><Activity size={18} /></span>
          <div className="live-stat-copy">
            <span className="live-stat-label">Average Confidence</span>
            <strong>
              {summary
                ? `${(summary.averageConfidence * 100).toFixed(2)}%`
                : "—"}
            </strong>
          </div>
        </article>
      </section>

      {summaryError && (
        <div className="dashboard-inline-error" role="alert">{summaryError}</div>
      )}

      <ImageDetectionWorkbench onDetectionComplete={refreshSummary} />
    </div>
  );
}
