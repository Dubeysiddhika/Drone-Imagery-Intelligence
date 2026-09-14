import {
  Layers3,
  LocateFixed,
  ZoomIn,
  ZoomOut,
  Navigation,
  Car,
  UserRound,
  Building2,
} from "lucide-react";

export default function MapPage() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Geospatial Intelligence</h1>
          <p className="page-description">
            Explore detected objects and survey locations spatially.
          </p>
        </div>
      </div>

      <div className="full-map">
        <div className="map-control">
          <h3>Detection Layers</h3>

          <Filter
            icon={<Car size={13} />}
            name="Vehicles"
            checked
          />

          <Filter
            icon={<UserRound size={13} />}
            name="People"
            checked
          />

          <Filter
            icon={<Building2 size={13} />}
            name="Buildings"
            checked
          />

          <div
            style={{
              borderTop: "1px solid #edf0f3",
              marginTop: 10,
              paddingTop: 12,
            }}
          >
            <div className="filter-row">
              <span>Confidence</span>
              <strong>75%</strong>
            </div>

            <input
              type="range"
              min="0"
              max="100"
              defaultValue="75"
              style={{ width: "100%" }}
            />
          </div>
        </div>

        <div
          style={{
            position: "absolute",
            right: 18,
            top: 18,
            display: "flex",
            flexDirection: "column",
            gap: 6,
            zIndex: 3,
          }}
        >
          <MapButton icon={<ZoomIn size={16} />} />
          <MapButton icon={<ZoomOut size={16} />} />
          <MapButton icon={<LocateFixed size={16} />} />
          <MapButton icon={<Layers3 size={16} />} />
        </div>

        <div
          className="big-marker blue"
          style={{ left: "47%", top: "38%" }}
        />

        <div
          className="big-marker green"
          style={{ left: "62%", top: "54%" }}
        />

        <div
          className="big-marker orange"
          style={{ left: "32%", top: "61%" }}
        />

        <div
          className="big-marker blue"
          style={{ left: "70%", top: "30%" }}
        />

        <div className="map-info-card">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 12,
            }}
          >
            <Navigation size={15} color="#2563eb" />

            <strong style={{ fontSize: 12 }}>
              Selected Detection
            </strong>
          </div>

          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              marginBottom: 6,
            }}
          >
            Vehicle
          </div>

          <div
            style={{
              fontSize: 10,
              color: "#6b7280",
              lineHeight: 1.8,
            }}
          >
            Confidence: <strong>94%</strong>
            <br />
            Latitude: 26.4499°
            <br />
            Longitude: 80.3319°
            <br />
            Image: DJI_00482.jpg
          </div>

          <button
            className="secondary-button"
            style={{
              width: "100%",
              marginTop: 12,
            }}
          >
            View Image
          </button>
        </div>
      </div>
    </div>
  );
}

function Filter({
  icon,
  name,
  checked,
}: {
  icon: React.ReactNode;
  name: string;
  checked: boolean;
}) {
  return (
    <div className="filter-row">
      <div className="filter-left">
        <input
          className="filter-checkbox"
          type="checkbox"
          defaultChecked={checked}
        />

        {icon}

        <span>{name}</span>
      </div>
    </div>
  );
}

function MapButton({ icon }: { icon: React.ReactNode }) {
  return (
    <button
      style={{
        width: 35,
        height: 35,
        border: "1px solid #e3e8ee",
        background: "white",
        borderRadius: 8,
        display: "grid",
        placeItems: "center",
        color: "#475569",
      }}
    >
      {icon}
    </button>
  );
}