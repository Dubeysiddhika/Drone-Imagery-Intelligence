import {
  TrendingUp,
  Target,
  Layers,
  Gauge,
} from "lucide-react";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

const data = [
  { name: "Cars", value: 823 },
  { name: "People", value: 312 },
  { name: "Buildings", value: 241 },
  { name: "Trucks", value: 106 },
];

export default function Analytics() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Survey Analytics</h1>
          <p className="page-description">
            Turn detection data into actionable intelligence.
          </p>
        </div>

        <select className="select">
          <option>All Surveys</option>
          <option>Kanpur Urban Survey</option>
          <option>Highway Inspection</option>
        </select>
      </div>

      <div className="stats-grid">
        <MiniStat
          icon={<Target size={18} />}
          title="Detection Accuracy"
          value="91.8%"
        />

        <MiniStat
          icon={<Layers size={18} />}
          title="Objects / km²"
          value="401"
        />

        <MiniStat
          icon={<Gauge size={18} />}
          title="Avg. Confidence"
          value="87.4%"
        />

        <MiniStat
          icon={<TrendingUp size={18} />}
          title="Growth"
          value="+23.4%"
        />
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              Object Detection Distribution
            </div>

            <div className="card-subtitle">
              Number of objects detected by category
            </div>
          </div>
        </div>

        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#edf0f4"
              />

              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                fontSize={10}
              />

              <YAxis
                axisLine={false}
                tickLine={false}
                fontSize={10}
              />

              <Tooltip />

              <Bar
                dataKey="value"
                fill="#2563eb"
                radius={[6,6,0,0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function MiniStat({
  icon,
  title,
  value,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
}) {
  return (
    <div className="card stat-card">
      <div className="stat-icon">{icon}</div>

      <div className="stat-value">{value}</div>

      <div className="stat-label">{title}</div>
    </div>
  );
}