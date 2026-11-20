import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Activity, Image as ImageIcon, ScanSearch, Satellite, MapPin } from "lucide-react";

import ImageDetectionWorkbench from "../components/dashboard/ImageDetectionWorkbench";
import {
  checkBackendHealth, getApiErrorMessage, getDashboardSummary, getImagePreviewUrl,
  listSurveys, type DashboardSummary, type SurveyRecord,
} from "../services/api";

const colors = ["#16847c", "#e68543", "#8b5cf6", "#3b82f6", "#eab308", "#ef4444", "#06b6d4", "#ec4899"];

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [surveys, setSurveys] = useState<SurveyRecord[]>([]);
  const [summaryError, setSummaryError] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [surveyId, setSurveyId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const refreshSummary = async () => {
    setSummaryLoading(true);
    try {
      const nextSummary = await getDashboardSummary({
        ...(surveyId ? { survey_id: Number(surveyId) } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      });
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
    void listSurveys().then((records) => { if (active) setSurveys(records); }).catch(() => undefined);
    const refreshBackendStatus = async () => {
      try {
        const online = await checkBackendHealth();
        if (active) setBackendStatus(online ? "online" : "offline");
      } catch {
        if (active) setBackendStatus("offline");
      }
    };
    void refreshBackendStatus();
    const intervalId = window.setInterval(() => { void refreshBackendStatus(); }, 15_000);
    return () => { active = false; window.clearInterval(intervalId); };
  }, []);

  useEffect(() => { void refreshSummary(); }, [surveyId, dateFrom, dateTo]);

  const cards = [
    { label: "Surveys", value: summary?.total_surveys, icon: Activity, tone: "violet" },
    { label: "Images Uploaded", value: summary?.total_images, icon: ImageIcon, tone: "blue" },
    { label: "Detected Objects", value: summary?.total_detections, icon: ScanSearch, tone: "cyan" },
    { label: "GPS-tagged Images", value: summary?.gps_statistics.available_images, icon: MapPin, tone: "green" },
  ] as const;
  const detectionTime = summary?.processing_time.detection;
  const localization = summary?.localization_statistics;

  return (
    <div className="intelligence-dashboard">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">AERIAL IMAGERY / LIVE WORKSPACE</p>
          <h1>Drone Imagery Intelligence</h1>
          <p>Survey, image, detection and localization statistics from stored platform records.</p>
        </div>
        <div className={`backend-indicator backend-${backendStatus}`} role="status">
          <span className="backend-indicator-dot" />
          <span>{backendStatus === "checking" ? "Checking backend" : backendStatus === "online" ? "Backend online" : "Backend unavailable"}</span>
          <Activity size={16} aria-hidden="true" />
        </div>
      </header>

      <section className="dashboard-filter-bar" aria-label="Analytics filters">
        <label>Survey
          <select value={surveyId} onChange={(event) => setSurveyId(event.target.value)}>
            <option value="">All surveys</option>
            {surveys.map((survey) => <option key={survey.id} value={survey.id}>{survey.name}</option>)}
          </select>
        </label>
        <label>Uploaded from<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
        <label>Uploaded through<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
        {(surveyId || dateFrom || dateTo) && <button type="button" className="dashboard-text-link" onClick={() => { setSurveyId(""); setDateFrom(""); setDateTo(""); }}>Clear filters</button>}
      </section>

      {summaryError && <div className="dashboard-inline-error" role="alert">{summaryError}<button type="button" onClick={() => void refreshSummary()}>Retry</button></div>}

      <section className="live-summary" aria-label="Workspace summary">
        {cards.map(({ label, value, icon: Icon, tone }) => (
          <article className="live-stat" key={label}>
            <span className={`live-stat-icon tone-${tone}`}><Icon size={18} /></span>
            <div className="live-stat-copy"><span className="live-stat-label">{label}</span><strong>{value === undefined ? summaryLoading ? "Loading…" : "Unavailable" : value.toLocaleString()}</strong></div>
          </article>
        ))}
      </section>

      <section className="dashboard-ops-grid" aria-label="Processing status">
        <article className="workbench-panel dashboard-ops-card">
          <p className="panel-kicker">DETECTION PIPELINE</p>
          <h2>{summary?.detection_processing.processed_images ?? (summaryLoading ? "Loading…" : 0)} processed <span>·</span> {summary?.detection_processing.pending_images ?? (summaryLoading ? "Loading…" : 0)} pending</h2>
          <p>{detectionTime?.completed_runs ?? 0} completed runs{detectionTime?.mean_seconds != null ? ` · mean ${detectionTime.mean_seconds.toFixed(2)} s` : " · no timing records yet"}</p>
        </article>
        <article className="workbench-panel dashboard-ops-card">
          <p className="panel-kicker">UAV-VISLOC</p>
          <h2><Satellite size={18} /> {localization?.completed_runs ?? 0} completed / {localization?.total_runs ?? 0} runs</h2>
          <p>{localization?.candidate_patches_returned ?? 0} candidate patches · {localization?.estimated_images ?? 0} image-center estimates · {localization?.evaluated_images ?? 0} evaluated against matched ground truth.</p>
          {localization?.median_error_m != null && <p>Median ground-truth error {localization.median_error_m.toFixed(2)} m across {localization.sample_size ?? 0} images. Within 5 / 10 / 25 / 50 m: {[localization.within_5m_percent, localization.within_10m_percent, localization.within_25m_percent, localization.within_50m_percent].map((value) => value == null ? "—" : `${value.toFixed(1)}%`).join(" / ")}</p>}
          {localization?.per_flight?.length ? <details><summary>Evaluation by flight</summary><div className="dashboard-flight-evaluation">{localization.per_flight.map((flight) => <p key={flight.flight_sequence}>Flight {flight.flight_sequence}: {flight.estimated_images}/{flight.localization_runs} estimated · {flight.evaluated_images} evaluated · median {flight.median_error_m == null ? "—" : `${flight.median_error_m.toFixed(2)} m`}</p>)}</div></details> : null}
        </article>
      </section>

      <section className="dashboard-chart-grid" aria-label="Detection analytics">
        <article className="workbench-panel dashboard-chart-card">
          <div className="dashboard-section-heading"><div><p className="panel-kicker">OBJECT CLASS DISTRIBUTION</p><h2>Detections by class</h2></div></div>
          {summaryLoading ? <p className="dashboard-empty-note">Loading class statistics…</p> : summary?.class_counts.length ? (
            <div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={summary.class_counts} margin={{ top: 8, right: 8, bottom: 30, left: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="class_name" angle={-25} textAnchor="end" interval={0} tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="count" name="Stored detections" radius={[5, 5, 0, 0]}>{summary.class_counts.map((entry, index) => <Cell key={entry.class_name} fill={colors[index % colors.length]} />)}</Bar></BarChart></ResponsiveContainer></div>
          ) : <p className="dashboard-empty-note">No stored detections for these filters.</p>}
        </article>
        <article className="workbench-panel dashboard-chart-card">
          <div className="dashboard-section-heading"><div><p className="panel-kicker">MODEL CONFIDENCE</p><h2>Confidence distribution</h2></div></div>
          {summaryLoading ? <p className="dashboard-empty-note">Loading confidence statistics…</p> : summary && summary.total_detections ? (
            <div className="dashboard-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={summary.confidence_distribution}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="range" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="count" name="Detections" fill="#3b82f6" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div>
          ) : <p className="dashboard-empty-note">No confidence values are stored for these filters.</p>}
        </article>
      </section>

      <article className="workbench-panel dashboard-survey-panel">
        <div className="dashboard-section-heading"><div><p className="panel-kicker">MISSION BREAKDOWN</p><h2>Survey-wise analytics</h2></div></div>
        {summaryLoading ? <p className="dashboard-empty-note">Loading survey statistics…</p> : summary?.survey_statistics.length ? (
          <div className="dashboard-survey-table"><div className="dashboard-survey-row dashboard-survey-header"><span>Survey</span><span>Images</span><span>Detections</span><span>GPS-tagged</span></div>{summary.survey_statistics.map((survey) => <div className="dashboard-survey-row" key={survey.survey_id}><span>{survey.survey_name}</span><span>{survey.image_count}</span><span>{survey.detection_count}</span><span>{survey.gps_image_count}</span></div>)}</div>
        ) : <p className="dashboard-empty-note">No survey-linked images match the current filters.</p>}
      </article>

      <section className="dashboard-live-grid" aria-label="Recent workspace activity">
        <article className="workbench-panel dashboard-recent-panel">
          <div className="dashboard-section-heading"><div><p className="panel-kicker">LATEST INGESTION</p><h2>Recent images</h2></div><Link to="/upload" className="dashboard-text-link">Upload imagery</Link></div>
          {summary?.recent_images.length ? <div className="recent-image-grid">{summary.recent_images.slice(0, 4).map((image) => <Link className="recent-image-card" key={image.image_id} to={`/analysis?image_id=${image.image_id}`}><img src={getImagePreviewUrl(image.image_id)} alt="" loading="lazy" /><span>{image.filename}</span><small>{image.detection_count ?? 0} stored detections · {image.gps_available ? "GPS available" : "No GPS"}</small></Link>)}</div> : <p className="dashboard-empty-note">{summaryLoading ? "Loading recent images…" : "No uploaded images match these filters."}</p>}
        </article>
        <article className="workbench-panel dashboard-recent-panel">
          <div className="dashboard-section-heading"><div><p className="panel-kicker">PROCESSING HISTORY</p><h2>Recent activity</h2></div><Link to="/analytics" className="dashboard-text-link">Detection analytics</Link></div>
          {summary?.recent_processing_activity.length ? <ul className="recent-activity-list">{summary.recent_processing_activity.slice(0, 8).map((run) => <li key={run.id}><Link to={`/analysis?image_id=${run.image_id}`}><span><strong>{run.pipeline === "localization" ? "UAV-VisLoc" : "YOLO detection"}</strong>{run.mode ? ` · ${run.mode.replaceAll("_", " ")}` : ""} · {run.filename}</span><small>{run.status}{run.processing_seconds != null ? ` · ${run.processing_seconds.toFixed(2)} s` : ""}{run.result_count != null ? ` · ${run.result_count} results` : ""}{run.error_message ? ` · ${run.error_message}` : ""}</small></Link></li>)}</ul> : <p className="dashboard-empty-note">{summaryLoading ? "Loading processing activity…" : "No processing runs are stored for these filters."}</p>}
        </article>
      </section>

      <ImageDetectionWorkbench onDetectionComplete={refreshSummary} />
    </div>
  );
}
