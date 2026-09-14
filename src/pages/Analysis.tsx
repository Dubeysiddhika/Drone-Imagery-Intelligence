import {
  ScanSearch,
  CheckCircle2,
  Car,
  UserRound,
  Building2,
  Truck,
} from "lucide-react";

const detections = [
  { name: "Vehicle", count: 12, confidence: "94%", icon: Car },
  { name: "Person", count: 5, confidence: "89%", icon: UserRound },
  { name: "Building", count: 8, confidence: "91%", icon: Building2 },
  { name: "Truck", count: 3, confidence: "86%", icon: Truck },
];

export default function Analysis() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Image Analysis</h1>
          <p className="page-description">
            Review AI-generated detections from your aerial imagery.
          </p>
        </div>

        <span className="status completed">
          AI PROCESSING COMPLETE
        </span>
      </div>

      <div className="analysis-layout">
        <div className="card analysis-image">
          <div className="analysis-toolbar">
            <span>DJI_00482.jpg</span>

            <span>
              <CheckCircle2 size={13} />
              Processed
            </span>
          </div>

          <div className="drone-analysis">
            <div className="fake-building" />

            <div className="bbox bbox-one">
              <span>CAR · 94%</span>
            </div>

            <div className="bbox bbox-two">
              <span>PERSON · 89%</span>
            </div>

            <div className="bbox bbox-three">
              <span>BUILDING · 91%</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Detection Results</div>
              <div className="card-subtitle">
                AI object recognition
              </div>
            </div>

            <ScanSearch size={18} color="#2563eb" />
          </div>

          <div className="object-list">
            {detections.map((item) => {
              const Icon = item.icon;

              return (
                <div className="object-row" key={item.name}>
                  <div className="object-info">
                    <div className="stat-icon">
                      <Icon size={16} />
                    </div>

                    <div>
                      <div className="object-name">
                        {item.name}
                      </div>

                      <div
                        style={{
                          color: "#98a1af",
                          fontSize: 9,
                          marginTop: 3,
                        }}
                      >
                        Confidence {item.confidence}
                      </div>
                    </div>
                  </div>

                  <strong>{item.count}</strong>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}