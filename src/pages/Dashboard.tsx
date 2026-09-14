import { Plus, Search, MapPin, CalendarDays, Image, TrendingUp } from "lucide-react";
import { useState } from "react";

export default function Dashboard() {
  const [surveys] = useState([
    {
      id: 1,
      name: "Urban Development Survey",
      date: "2024-01-15",
      location: "Downtown District",
      images: 245,
      status: "Processed",
    },
    {
      id: 2,
      name: "Agricultural Assessment",
      date: "2024-01-10",
      location: "North Valley",
      images: 892,
      status: "Processing",
    },
    {
      id: 3,
      name: "Coastal Erosion Study",
      date: "2024-01-08",
      location: "Pacific Coast",
      images: 156,
      status: "Pending",
    },
  ]);

  const stats = [
    { label: "Total Surveys", value: "12", trend: "+2" },
    { label: "Images Processed", value: "3.2K", trend: "+240" },
    { label: "Analysis Complete", value: "89%", trend: "+5%" },
    { label: "Active Projects", value: "4", trend: "+1" },
  ];

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Welcome back! Here's your intelligence overview.</p>
        </div>
        <button className="primary-button">
          <Plus size={18} /> New Survey
        </button>
      </div>

      <div className="stats-grid">
        {stats.map((stat, i) => (
          <div key={i} className="stat-card">
            <div className="stat-label">{stat.label}</div>
            <div className="stat-value">{stat.value}</div>
            <div className="stat-trend">
              <TrendingUp size={14} /> {stat.trend}
            </div>
          </div>
        ))}
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Recent Surveys</h2>
          <input
            type="text"
            placeholder="Search surveys..."
            className="search-input"
          />
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Survey Name</th>
                <th>Date</th>
                <th>Location</th>
                <th>Images</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {surveys.map((survey) => (
                <tr key={survey.id}>
                  <td className="survey-name">{survey.name}</td>
                  <td>{survey.date}</td>
                  <td>
                    <MapPin size={14} /> {survey.location}
                  </td>
                  <td>
                    <Image size={14} /> {survey.images}
                  </td>
                  <td>
                    <span className={`badge badge-${survey.status.toLowerCase()}`}>
                      {survey.status}
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
