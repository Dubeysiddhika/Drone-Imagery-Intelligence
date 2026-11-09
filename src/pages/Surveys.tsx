import { FormEvent, useEffect, useState } from "react";
import { CalendarDays, MapPin, Plus, RefreshCw } from "lucide-react";

import {
  createSurvey,
  getApiErrorMessage,
  listSurveys,
  type SurveyRecord,
} from "../services/api";

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function Surveys() {
  const [surveys, setSurveys] = useState<SurveyRecord[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const refreshSurveys = async () => {
    try {
      setSurveys(await listSurveys());
      setError("");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshSurveys();
  }, []);

  const submitSurvey = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await createSurvey(trimmedName, description.trim());
      setName("");
      setDescription("");
      setSuccess("Survey created.");
      await refreshSurveys();
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="survey-workspace">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">MISSION ORGANIZATION</p>
          <h1>Surveys</h1>
          <p>Manage survey records stored by the backend.</p>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={() => {
            setLoading(true);
            void refreshSurveys();
          }}
          disabled={loading}
        >
          <RefreshCw size={15} /> Refresh
        </button>
      </header>

      {error && <div className="dashboard-inline-error" role="alert">{error}</div>}
      {success && <div className="workflow-message workflow-complete" role="status">{success}</div>}

      <section className="workbench-panel survey-create-panel">
        <div className="dashboard-section-heading">
          <div>
            <p className="panel-kicker">NEW RECORD</p>
            <h2>Create a survey</h2>
          </div>
        </div>
        <form className="survey-create-form" onSubmit={(event) => void submitSurvey(event)}>
          <label>
            <span>Survey name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={200}
              required
              placeholder="e.g. North field inspection"
            />
          </label>
          <label>
            <span>Description</span>
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional notes"
            />
          </label>
          <button type="submit" className="workbench-primary-button" disabled={saving || !name.trim()}>
            <Plus size={15} /> {saving ? "Creating…" : "Create survey"}
          </button>
        </form>
      </section>

      <section className="workbench-panel survey-list-panel">
        <div className="dashboard-section-heading">
          <div>
            <p className="panel-kicker">DATABASE RECORDS</p>
            <h2>Survey register</h2>
          </div>
          <span className="map-record-count">{surveys.length} surveys</span>
        </div>
        {loading ? (
          <p className="dashboard-empty-note" role="status">Loading surveys…</p>
        ) : surveys.length ? (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr><th>Survey</th><th>Description</th><th>Created</th></tr>
              </thead>
              <tbody>
                {surveys.map((survey) => (
                  <tr key={survey.id}>
                    <td><strong>{survey.name}</strong></td>
                    <td>{survey.description || "—"}</td>
                    <td>
                      <span className="table-icon-text">
                        <CalendarDays size={13} /> {formatDate(survey.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="map-empty-state">
            <MapPin size={20} />
            <strong>No surveys in the database.</strong>
            <span>Create a survey record above. Image-to-survey assignment is not currently exposed by the backend.</span>
          </div>
        )}
      </section>
    </div>
  );
}
