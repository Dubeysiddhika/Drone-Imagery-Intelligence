import {
  FileText,
  Download,
  Eye,
  Plus,
  FileSpreadsheet,
} from "lucide-react";

const reports = [
  {
    name: "Kanpur Urban Survey Report",
    date: "Aug 26, 2026",
    images: 84,
    detections: 1284,
  },
  {
    name: "Highway Inspection Report",
    date: "Aug 24, 2026",
    images: 132,
    detections: 3241,
  },
  {
    name: "River Basin Analysis",
    date: "Aug 22, 2026",
    images: 74,
    detections: 812,
  },
];

export default function Reports() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Survey Reports</h1>
          <p className="page-description">
            Generate and manage automated intelligence reports.
          </p>
        </div>

        <button className="primary-button">
          <Plus size={15} />
          Generate Report
        </button>
      </div>

      <div className="report-grid">
        {reports.map((report) => (
          <div className="card report-card" key={report.name}>
            <div className="report-icon">
              <FileText size={24} />
            </div>

            <h3>{report.name}</h3>

            <p>{report.date}</p>

            <div className="report-stats">
              <span>{report.images} Images</span>
              <span>{report.detections.toLocaleString()} Objects</span>
            </div>

            <div className="report-actions">
              <button className="secondary-button">
                <Eye size={14} />
                Preview
              </button>

              <button className="primary-button">
                <Download size={14} />
                PDF
              </button>

              <button className="secondary-button">
                <FileSpreadsheet size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}