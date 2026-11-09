import ImageDetectionWorkbench from "../components/dashboard/ImageDetectionWorkbench";

export default function Analysis() {
  return (
    <div className="intelligence-dashboard analysis-workspace-page">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">VISION / PERSISTED INFERENCE</p>
          <h1>Image Analysis</h1>
          <p>
            Reopen an uploaded image, inspect saved detections, or run either
            available model again.
          </p>
        </div>
      </header>
      <ImageDetectionWorkbench />
    </div>
  );
}
