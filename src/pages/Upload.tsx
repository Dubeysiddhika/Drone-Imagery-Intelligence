import ImageDetectionWorkbench from "../components/dashboard/ImageDetectionWorkbench";

export default function Upload() {
  return (
    <div className="intelligence-dashboard upload-page">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">IMAGE INGESTION / YOLO INFERENCE</p>
          <h1>Upload Imagery</h1>
          <p>Send a drone image to the backend and inspect its stored detection results.</p>
        </div>
      </header>
      <ImageDetectionWorkbench />
    </div>
  );
}