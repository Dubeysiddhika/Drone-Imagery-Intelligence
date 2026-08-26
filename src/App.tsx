import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Map,
  UploadCloud,
  ScanSearch,
  BarChart3,
  FileText,
  Settings,
  Plane,
  Menu,
  Bell,
  Search,
  ChevronDown,
} from "lucide-react";
import { useState } from "react";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import Surveys from "./pages/Surveys";
import Upload from "./pages/Upload";
import Analysis from "./pages/Analysis";
import MapPage from "./pages/Map";
import Analytics from "./pages/Analytics";
import Reports from "./pages/Reports";
import SettingsPage from "./pages/Settings";

const navItems = [
  {
    name: "Dashboard",
    path: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Surveys",
    path: "/surveys",
    icon: Map,
  },
  {
    name: "Upload Imagery",
    path: "/upload",
    icon: UploadCloud,
  },
  {
    name: "Image Analysis",
    path: "/analysis",
    icon: ScanSearch,
  },
  {
    name: "GIS Map",
    path: "/map",
    icon: Map,
  },
  {
    name: "Analytics",
    path: "/analytics",
    icon: BarChart3,
  },
  {
    name: "Reports",
    path: "/reports",
    icon: FileText,
  },
];

function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        <div className="brand">
          <div className="brand-icon">
            <Plane size={21} />
          </div>

          {!collapsed && (
            <div>
              <div className="brand-title">AEROVISION</div>
              <div className="brand-subtitle">INTELLIGENCE</div>
            </div>
          )}
        </div>

        <button
          className="collapse-btn"
          onClick={() => setCollapsed(!collapsed)}
        >
          <Menu size={19} />
        </button>
      </div>

      <div className="nav-section">
        {!collapsed && <div className="nav-label">WORKSPACE</div>}

        {navItems.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;

          return (
            <a
              key={item.path}
              href={item.path}
              className={`nav-item ${active ? "active" : ""}`}
              title={collapsed ? item.name : ""}
            >
              <Icon size={19} />
              {!collapsed && <span>{item.name}</span>}
            </a>
          );
        })}
      </div>

      <div className="sidebar-bottom">
        {!collapsed && <div className="nav-label">SYSTEM</div>}

        <a
          href="/settings"
          className={`nav-item ${
            location.pathname === "/settings" ? "active" : ""
          }`}
        >
          <Settings size={19} />
          {!collapsed && <span>Settings</span>}
        </a>

        {!collapsed && (
          <div className="storage-card">
            <div className="storage-header">
              <span>Storage</span>
              <span>68%</span>
            </div>

            <div className="progress">
              <div style={{ width: "68%" }} />
            </div>

            <p>6.8 GB of 10 GB used</p>
          </div>
        )}
      </div>
    </aside>
  );
}

function Topbar() {
  return (
    <header className="topbar">
      <div className="top-search">
        <Search size={18} />
        <input placeholder="Search surveys, images, detections..." />
        <kbd>⌘ K</kbd>
      </div>

      <div className="top-actions">
        <button className="icon-button">
          <Bell size={19} />
          <span className="notification-dot" />
        </button>

        <div className="profile">
          <div className="avatar">SD</div>

          <div className="profile-info">
            <strong>Siddhika</strong>
            <span>Researcher</span>
          </div>

          <ChevronDown size={16} />
        </div>
      </div>
    </header>
  );
}

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />

      <main className="main-area">
        <Topbar />
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      <Route
        path="/dashboard"
        element={
          <AppLayout>
            <Dashboard />
          </AppLayout>
        }
      />

      <Route
        path="/surveys"
        element={
          <AppLayout>
            <Surveys />
          </AppLayout>
        }
      />

      <Route
        path="/upload"
        element={
          <AppLayout>
            <Upload />
          </AppLayout>
        }
      />

      <Route
        path="/analysis"
        element={
          <AppLayout>
            <Analysis />
          </AppLayout>
        }
      />

      <Route
        path="/map"
        element={
          <AppLayout>
            <MapPage />
          </AppLayout>
        }
      />

      <Route
        path="/analytics"
        element={
          <AppLayout>
            <Analytics />
          </AppLayout>
        }
      />

      <Route
        path="/reports"
        element={
          <AppLayout>
            <Reports />
          </AppLayout>
        }
      />

      <Route
        path="/settings"
        element={
          <AppLayout>
            <SettingsPage />
          </AppLayout>
        }
      />

      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}