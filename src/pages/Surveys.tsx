import { Plus, Search, MapPin, CalendarDays, Image } from "lucide-react";

const surveys = [
  {
    name: "Kanpur Urban Survey",
    location: "Kanpur, Uttar Pradesh",
    date: "Aug 26, 2026",
    images: 84,
    detections: 1284,
    status: "completed",
  },
  {
    name: "Agricultural Field 04",
    location: "Lucknow, Uttar Pradesh",
    date: "Aug 25, 2026",
    images: 56,
    detections: 923,
    status: "processing",
  },
  {
    name: "Highway Inspection",
    location: "Agra-Lucknow Expressway",
    date: "Aug 24, 2026",
    images: 132,
    detections: 3241,
    status: "completed",
  },
  {
    name: "River Basin Survey",
    location: "Yamuna Basin",
    date: "Aug 22, 2026",
    images: 74,
    detections: 812,
    status: "completed",
  },
];

export default function Surveys() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Surveys</h1>
          <p className="page-description">
            Manage and explore your drone survey missions.
          </p>
        </div>

        <a href="/upload" className="primary-button">
          <Plus size={16} />
          Create Survey
        </a>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="survey-search">
            <Search size={16} />
            <input placeholder="Search surveys..." />
          </div>

          <select className="select">
            <option>All surveys</option>
            <option>Completed</option>
            <option>Processing</option>
          </select>
        </div>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Survey</th>
                <th>Location</th>
                <th>Date</th>
                <th>Images</th>
                <th>Detections</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {surveys.map((survey) => (
                <tr key={survey.name}>
                  <td>
                    <strong>{survey.name}</strong>
                  </td>

                  <td>
                    <span className="table-icon-text">
                      <MapPin size={13} />
                      {survey.location}
                    </span>
                  </td>

                  <td>
                    <span className="table-icon-text">
                      <CalendarDays size={13} />
                      {survey.date}
                    </span>
                  </td>

                  <td>
                    <span className="table-icon-text">
                      <Image size={13} />
                      {survey.images}
                    </span>
                  </td>

                  <td>{survey.detections.toLocaleString()}</td>

                  <td>
                    <span className={`status ${survey.status}`}>
                      {survey.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}