import { useEffect, useMemo, useState } from "react";
import { Download, FileText, Printer } from "lucide-react";

import {
  getApiErrorMessage,
  getImage,
  getImagePreviewUrl,
  getStoredDetections,
  listImages,
  type Detection,
  type DetectionResponse,
  type ImageMetadata,
} from "../services/api";

function formatDate(value: string | null | undefined): string {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function escapeCsv(value: string | number | null): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

export default function Reports() {
  const [images, setImages] = useState<ImageMetadata[]>([]);
  const [selectedImageId, setSelectedImageId] = useState("");
  const [image, setImage] = useState<ImageMetadata | null>(null);
  const [result, setResult] = useState<DetectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listImages()
      .then((records) => {
        if (active) setImages(records);
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const loadReport = async () => {
    const imageId = Number(selectedImageId);
    if (!Number.isInteger(imageId) || imageId <= 0) return;
    setLoading(true);
    setError("");
    try {
      const [nextImage, nextResult] = await Promise.all([
        getImage(imageId),
        getStoredDetections(imageId),
      ]);
      setImage(nextImage);
      setResult(nextResult);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
      setImage(null);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const detections = result?.detections ?? [];
  const classCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const detection of detections) {
      counts.set(detection.class_name, (counts.get(detection.class_name) ?? 0) + 1);
    }
    return [...counts.entries()].sort((left, right) => left[0].localeCompare(right[0]));
  }, [detections]);

  const exportCsv = () => {
    if (!image || !result) return;
    const header = [
      "detection_id", "image_id", "class_id", "class_name", "confidence",
      "x1", "y1", "x2", "y2", "model_name", "model_version",
    ];
    const rows = detections.map((detection: Detection) => [
      detection.id,
      image.image_id,
      detection.class_id,
      detection.class_name,
      detection.confidence,
      detection.bbox.x1,
      detection.bbox.y1,
      detection.bbox.x2,
      detection.bbox.y2,
      detection.model_name ?? result.model_name ?? "",
      detection.model_version ?? result.model_version ?? "",
    ]);
    const content = [header, ...rows]
      .map((row) => row.map(escapeCsv).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `image-${image.image_id}-report.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="reports-workspace">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">EXPORT / TRACEABLE RESULTS</p>
          <h1>Analysis Reports</h1>
          <p>Create exports from images and detections stored by the backend.</p>
        </div>
      </header>

      {error && <div className="dashboard-inline-error" role="alert">{error}</div>}

      <section className="workbench-panel report-controls">
        <label htmlFor="report-image">Analyzed image</label>
        <select
          id="report-image"
          value={selectedImageId}
          onChange={(event) => setSelectedImageId(event.target.value)}
          disabled={loading && images.length === 0}
        >
          <option value="">{loading && images.length === 0 ? "Loading images…" : "Select an image"}</option>
          {images.map((record) => (
            <option key={record.image_id} value={record.image_id}>
              #{record.image_id} · {record.filename} ({record.detection_count ?? 0} detections)
            </option>
          ))}
        </select>
        <button
          type="button"
          className="workbench-primary-button"
          onClick={() => void loadReport()}
          disabled={!selectedImageId || loading}
        >
          <FileText size={15} /> {loading && selectedImageId ? "Loading…" : "Build report"}
        </button>
        {images.length === 0 && !loading && (
          <p className="dashboard-empty-note">Upload imagery and run detection before generating a report.</p>
        )}
      </section>

      {image && result && (
        <article className="workbench-panel report-preview">
          <div className="report-preview-heading">
            <div>
              <p className="panel-kicker">DRONE IMAGERY INTELLIGENCE PLATFORM</p>
              <h2>Image Detection Report</h2>
              <p>Generated from persisted image metadata and detection records.</p>
            </div>
            <div className="report-actions no-print">
              <button type="button" className="secondary-button" onClick={exportCsv}>
                <Download size={15} /> Export CSV
              </button>
              <button type="button" className="workbench-primary-button" onClick={() => window.print()}>
                <Printer size={15} /> Print / Save as PDF
              </button>
            </div>
          </div>

          <div className="report-overview-grid">
            <div>
              <span>Filename</span>
              <strong>{image.filename}</strong>
            </div>
            <div>
              <span>Image ID</span>
              <strong>{image.image_id}</strong>
            </div>
            <div>
              <span>Uploaded</span>
              <strong>{formatDate(image.uploaded_at)}</strong>
            </div>
            <div>
              <span>Model</span>
              <strong>{result.model_name ?? "Not available"}</strong>
            </div>
            <div>
              <span>Model version</span>
              <strong>{result.model_version ?? "Not available"}</strong>
            </div>
            <div>
              <span>Total detections</span>
              <strong>{result.detection_count}</strong>
            </div>
            <div>
              <span>Capture timestamp</span>
              <strong>{formatDate(image.capture_time ?? image.captured_at)}</strong>
            </div>
            <div>
              <span>Image dimensions</span>
              <strong>{image.width && image.height ? `${image.width} × ${image.height} px` : "Not available"}</strong>
            </div>
            <div>
              <span>Capture GPS</span>
              <strong>
                {image.latitude !== null && image.longitude !== null
                  ? `${image.latitude.toFixed(6)}, ${image.longitude.toFixed(6)}`
                  : "Not available"}
              </strong>
            </div>
            <div>
              <span>Altitude</span>
              <strong>{image.altitude === null ? "Not available" : `${image.altitude.toFixed(2)} m`}</strong>
            </div>
            <div>
              <span>Camera</span>
              <strong>{[image.camera_make, image.camera_model].filter(Boolean).join(" ") || "Not available"}</strong>
            </div>
            <div>
              <span>Average confidence</span>
              <strong>
                {detections.length
                  ? `${(detections.reduce((sum, detection) => sum + detection.confidence, 0) / detections.length * 100).toFixed(2)}%`
                  : "No detections"}
              </strong>
            </div>
          </div>

          <div className="report-content-grid">
            <img
              className="report-image-preview"
              src={getImagePreviewUrl(image.image_id)}
              alt={`Preview of ${image.filename}`}
            />
            <section>
              <h3>Class counts</h3>
              {classCounts.length ? (
                <ul className="report-class-list">
                  {classCounts.map(([className, count]) => (
                    <li key={className}><span>{className}</span><strong>{count}</strong></li>
                  ))}
                </ul>
              ) : (
                <p className="dashboard-empty-note">The model returned no persisted detections for this image.</p>
              )}
            </section>
          </div>

          <div className="table-wrapper report-detection-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Detection ID</th><th>Class ID</th><th>Class</th><th>Confidence</th>
                  <th>X1</th><th>Y1</th><th>X2</th><th>Y2</th><th>Model</th><th>Version</th>
                </tr>
              </thead>
              <tbody>
                {detections.map((detection) => (
                  <tr key={detection.id}>
                    <td>{detection.id}</td>
                    <td>{detection.class_id}</td>
                    <td>{detection.class_name}</td>
                    <td>{(detection.confidence * 100).toFixed(2)}%</td>
                    <td>{detection.bbox.x1.toFixed(2)}</td>
                    <td>{detection.bbox.y1.toFixed(2)}</td>
                    <td>{detection.bbox.x2.toFixed(2)}</td>
                    <td>{detection.bbox.y2.toFixed(2)}</td>
                    <td>{detection.model_name ?? result.model_name ?? "—"}</td>
                    <td>{detection.model_version ?? result.model_version ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="report-coordinate-note">
            Bounding boxes use source-image pixel coordinates in xyxy order and are not geographic coordinates.
          </p>
        </article>
      )}
      <p className="report-limit-note">
        Reports are image-specific because the current backend does not associate uploaded images with surveys.
        “Print / Save as PDF” uses your browser’s print dialog.
      </p>
    </div>
  );
}
