import {
  ArrowRight,
  Map,
  Scan,
  Satellite,
  BarChart3,
  FileText,
  UploadCloud,
  CheckCircle2,
} from "lucide-react";

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="landing-brand">
          <div className="brand-icon">
            <Satellite size={20} />
          </div>

          <div>
            <strong>AEROVISION</strong>
            <span>INTELLIGENCE</span>
          </div>
        </div>

        <div className="landing-links">
          <a href="#features">Features</a>
          <a href="#workflow">How it works</a>
          <a href="#usecases">Applications</a>
        </div>

        <div className="landing-actions">
          <a href="/login" className="login-link">
            Sign in
          </a>

          <a href="/dashboard" className="primary-button">
            Launch Platform
            <ArrowRight size={15} />
          </a>
        </div>
      </nav>

      <section className="hero">
        <div className="hero-content">
          <div className="eyebrow">
            <span />
            AI-POWERED AERIAL INTELLIGENCE
          </div>

          <h1>
            Turn Drone Imagery
            <br />
            Into <span>Intelligence.</span>
          </h1>

          <p>
            Process aerial imagery, extract geospatial metadata,
            detect objects with AI, and transform your surveys into
            actionable spatial intelligence.
          </p>

          <div className="hero-buttons">
            <a href="/dashboard" className="primary-button hero-button">
              Explore Platform
              <ArrowRight size={17} />
            </a>

            <a href="#workflow" className="hero-secondary">
              See how it works
            </a>
          </div>

          <div className="hero-trust">
            <CheckCircle2 size={15} />
            Automated processing
            <CheckCircle2 size={15} />
            GIS visualization
            <CheckCircle2 size={15} />
            AI detection
          </div>
        </div>

        <div className="hero-visual">
          <div className="hero-map">
            <div className="hero-map-grid" />

            <div className="scan-line" />

            <div className="drone-card">
              <Satellite size={17} />
              <div>
                <strong>LIVE SURVEY</strong>
                <span>26.4499° N · 80.3319° E</span>
              </div>
            </div>

            <div className="detection detection-a">
              <div />
              <span>VEHICLE · 94%</span>
            </div>

            <div className="detection detection-b">
              <div />
              <span>BUILDING · 91%</span>
            </div>

            <div className="detection detection-c">
              <div />
              <span>PERSON · 87%</span>
            </div>

            <div className="coordinate">
              <span>LAT</span>
              26.4499°
              <br />
              <span>LNG</span>
              80.3319°
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="landing-section">
        <div className="section-heading">
          <div className="eyebrow">
            <span />
            PLATFORM CAPABILITIES
          </div>

          <h2>Everything your aerial survey needs.</h2>
        </div>

        <div className="feature-grid">
          <Feature
            icon={<UploadCloud />}
            title="Smart Image Processing"
            text="Upload and process hundreds of drone images with automatic metadata extraction."
          />

          <Feature
            icon={<Scan />}
            title="AI Object Detection"
            text="Identify vehicles, people, buildings and other objects using computer vision."
          />

          <Feature
            icon={<Map />}
            title="Geospatial Intelligence"
            text="Visualize imagery and detected objects on an interactive GIS map."
          />

          <Feature
            icon={<BarChart3 />}
            title="Survey Analytics"
            text="Understand object distributions, confidence levels and spatial density."
          />

          <Feature
            icon={<FileText />}
            title="Automated Reports"
            text="Generate professional survey reports from your processed data."
          />
        </div>
      </section>

      <section id="workflow" className="workflow-section">
        <div className="section-heading center">
          <div className="eyebrow">
            <span />
            SIMPLE WORKFLOW
          </div>

          <h2>From raw imagery to insight.</h2>
        </div>

        <div className="workflow">
          <Step number="01" title="Upload" text="Upload your drone imagery." />
          <Step number="02" title="Process" text="Extract GPS and metadata." />
          <Step number="03" title="Detect" text="AI identifies objects." />
          <Step number="04" title="Visualize" text="Explore results on a map." />
          <Step number="05" title="Analyze" text="Generate insights and reports." />
        </div>
      </section>
    </div>
  );
}

function Feature({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="feature-card">
      <div className="feature-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

function Step({
  number,
  title,
  text,
}: {
  number: string;
  title: string;
  text: string;
}) {
  return (
    <div className="step">
      <span>{number}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}