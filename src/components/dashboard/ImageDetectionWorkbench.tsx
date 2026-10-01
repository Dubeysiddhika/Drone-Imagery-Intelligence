import {
  AlertCircle,
  CheckCircle2,
  CloudUpload,
  Image as ImageIcon,
  LoaderCircle,
  MapPin,
  RefreshCw,
  ScanLine,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  getApiErrorMessage,
  runDetection,
  uploadImage,
  type Detection,
  type ImageMetadata,
} from "../../services/api";

type WorkflowPhase = "idle" | "uploading" | "detecting" | "complete" | "error";

const supportedImageExtensions = new Set([".jpg", ".jpeg", ".png", ".tif", ".tiff"]);

function formatConfidence(confidence: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: 2,
  }).format(confidence);
}

function formatCoordinate(value: number | null): string {
  return value === null ? "Not available" : value.toFixed(6);
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function boxClass(className: string): string {
  return className.toLowerCase() === "person" ? "detection-person" : "detection-vehicle";
}

export default function ImageDetectionWorkbench({
  onDetectionComplete,
}: {
  onDetectionComplete?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [metadata, setMetadata] = useState<ImageMetadata | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [phase, setPhase] = useState<WorkflowPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const selectFile = (nextFile?: File) => {
    if (!nextFile) return;
    const extension = `.${nextFile.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!supportedImageExtensions.has(extension)) {
      setFile(null);
      setPreviewUrl("");
      setMetadata(null);
      setDetections([]);
      if (inputRef.current) inputRef.current.value = "";
      setErrorMessage("Unsupported image format. Choose JPG, PNG, or TIFF.");
      setPhase("error");
      return;
    }

    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
    setMetadata(null);
    setDetections([]);
    setImageSize({ width: 0, height: 0 });
    setProgress(0);
    setErrorMessage("");
    setPhase("idle");
  };

  const startDetection = async (image: ImageMetadata) => {
    setPhase("detecting");
    setErrorMessage("");
    try {
      const result = await runDetection(image.image_id || image.id);
      setDetections(result.detections);
      setPhase("complete");
      onDetectionComplete?.();
    } catch (error) {
      setPhase("error");
      setErrorMessage(getApiErrorMessage(error));
    }
  };

  const uploadAndAnalyze = async () => {
    if (!file) return;
    setPhase("uploading");
    setProgress(0);
    setErrorMessage("");

    try {
      const uploadedImage = await uploadImage(file, setProgress);
      setMetadata(uploadedImage);
      await startDetection(uploadedImage);
    } catch (error) {
      setPhase("error");
      setErrorMessage(getApiErrorMessage(error));
    }
  };

  const clearSelection = () => {
    setFile(null);
    setPreviewUrl("");
    setMetadata(null);
    setDetections([]);
    setProgress(0);
    setErrorMessage("");
    setImageSize({ width: 0, height: 0 });
    setPhase("idle");
    if (inputRef.current) inputRef.current.value = "";
  };

  const hasGps = metadata?.latitude !== null &&
    metadata?.latitude !== undefined &&
    metadata?.longitude !== null &&
    metadata?.longitude !== undefined;
  const width = imageSize.width || metadata?.width || 0;
  const height = imageSize.height || metadata?.height || 0;
  const averageConfidence = detections.length
    ? detections.reduce((total, detection) => total + detection.confidence, 0) /
      detections.length
    : 0;
  const isBusy = phase === "uploading" || phase === "detecting";

  return (
    <section className="image-workbench" aria-label="Image upload and detection">
      <div className="workbench-grid">
        <article className="workbench-panel image-panel">
          <div className="workbench-panel-heading">
            <div>
              <p className="panel-kicker">IMAGE INGESTION</p>
              <h2>Upload and analyze</h2>
            </div>
            {metadata && (
              <span className="image-id-tag">IMAGE #{metadata.image_id || metadata.id}</span>
            )}
          </div>

          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept=".jpg,.jpeg,.png,.tif,.tiff,image/jpeg,image/png,image/tiff"
            onChange={(event) => selectFile(event.target.files?.[0])}
            aria-label="Choose a drone image"
          />

          {!previewUrl ? (
            <div
              className={`upload-drop-target ${isDragging ? "is-dragging" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  inputRef.current?.click();
                }
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                selectFile(event.dataTransfer.files[0]);
              }}
            >
              <span className="drop-target-icon"><CloudUpload size={24} /></span>
              <strong>Drop an image here</strong>
              <span>or select a JPG, PNG, or TIFF file</span>
              <span className="drop-target-button">Browse files</span>
            </div>
          ) : (
            <div className="image-preview-shell">
              <div className="preview-toolbar">
                <div className="preview-file-name" title={file?.name ?? metadata?.filename}>
                  <ImageIcon size={15} />
                  <span>{file?.name ?? metadata?.filename}</span>
                </div>
                <button
                  type="button"
                  className="subtle-icon-button"
                  onClick={clearSelection}
                  disabled={isBusy}
                  aria-label="Remove selected image"
                  title="Remove image"
                >
                  <Trash2 size={15} />
                </button>
              </div>
              <figure className="detection-image-frame">
                <img
                  src={previewUrl}
                  alt={`Preview of ${file?.name ?? metadata?.filename ?? "uploaded drone image"}`}
                  onLoad={(event) => {
                    setImageSize({
                      width: event.currentTarget.naturalWidth,
                      height: event.currentTarget.naturalHeight,
                    });
                  }}
                />
                {detections.length > 0 && width > 0 && height > 0 && (
                  <svg
                    className="detection-overlay"
                    viewBox={`0 0 ${width} ${height}`}
                    preserveAspectRatio="none"
                    role="img"
                    aria-label={`${detections.length} detected object bounding boxes`}
                  >
                    {detections.map((detection) => {
                      const x1 = Math.max(0, Math.min(width, detection.bbox.x1));
                      const y1 = Math.max(0, Math.min(height, detection.bbox.y1));
                      const x2 = Math.max(x1, Math.min(width, detection.bbox.x2));
                      const y2 = Math.max(y1, Math.min(height, detection.bbox.y2));
                      const fontSize = Math.max(13, width * 0.017);
                      const label = `${detection.class_name.toUpperCase()} ${formatConfidence(detection.confidence)}`;
                      const labelWidth = Math.min(width - x1, label.length * fontSize * 0.58 + fontSize);
                      const labelHeight = fontSize * 1.45;
                      const labelY = y1 >= labelHeight ? y1 - labelHeight : y1;

                      return (
                        <g key={detection.id} className={boxClass(detection.class_name)}>
                          <rect
                            className="detection-box"
                            x={x1}
                            y={y1}
                            width={Math.max(0, x2 - x1)}
                            height={Math.max(0, y2 - y1)}
                            vectorEffect="non-scaling-stroke"
                          />
                          <rect
                            x={x1}
                            y={labelY}
                            width={labelWidth}
                            height={labelHeight}
                            rx={fontSize * 0.18}
                            className="detection-label-bg"
                          />
                          <text
                            x={x1 + fontSize * 0.45}
                            y={labelY + fontSize}
                            fontSize={fontSize * 0.75}
                            className="detection-label-text"
                          >
                            {label}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </figure>
              <div className="preview-dimensions">
                {width > 0 && height > 0 ? `${width} × ${height} px` : "Reading image dimensions…"}
                {detections.length > 0 && <span>{detections.length} boxes overlaid</span>}
              </div>
            </div>
          )}

          {phase === "uploading" && (
            <div className="upload-progress-block" role="status">
              <div className="progress-copy"><span>Uploading image</span><strong>{progress}%</strong></div>
              <div className="upload-progress-track"><span style={{ width: `${progress}%` }} /></div>
            </div>
          )}
          {phase === "detecting" && (
            <div className="workflow-message workflow-processing" role="status">
              <LoaderCircle size={17} className="spin" />
              <span>YOLO is processing the uploaded image…</span>
            </div>
          )}
          {phase === "complete" && (
            <div className="workflow-message workflow-complete" role="status">
              <CheckCircle2 size={17} />
              <span>Detection complete. Results were returned by the backend.</span>
            </div>
          )}
          {phase === "error" && errorMessage && (
            <div className="workflow-message workflow-error" role="alert">
              <AlertCircle size={17} />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="upload-actions">
            {file && !metadata && (
              <button
                type="button"
                className="workbench-primary-button"
                onClick={() => void uploadAndAnalyze()}
                disabled={isBusy}
              >
                {phase === "uploading" ? <LoaderCircle size={16} className="spin" /> : <CloudUpload size={16} />}
                {phase === "uploading" ? "Uploading…" : "Upload and analyze"}
              </button>
            )}
            {metadata && phase === "error" && (
              <button
                type="button"
                className="workbench-primary-button"
                onClick={() => void startDetection(metadata)}
                disabled={isBusy}
              >
                <RefreshCw size={16} /> Retry detection
              </button>
            )}
            {phase === "detecting" && (
              <span className="action-note"><LoaderCircle size={14} className="spin" /> Processing</span>
            )}
          </div>
        </article>

        <aside className="metadata-column">
          <article className="workbench-panel metadata-panel">
            <div className="workbench-panel-heading compact-heading">
              <div>
                <p className="panel-kicker">SOURCE IMAGE</p>
                <h2>Image metadata</h2>
              </div>
            </div>
            {metadata ? (
              <dl className="metadata-list">
                <div><dt>Filename</dt><dd title={metadata.filename}>{metadata.filename}</dd></div>
                <div><dt>Dimensions</dt><dd>{metadata.width && metadata.height ? `${metadata.width} × ${metadata.height} px` : "Not available"}</dd></div>
                <div><dt>Latitude</dt><dd>{formatCoordinate(metadata.latitude)}</dd></div>
                <div><dt>Longitude</dt><dd>{formatCoordinate(metadata.longitude)}</dd></div>
                <div><dt>Altitude</dt><dd>{metadata.altitude === null ? "Not available" : `${metadata.altitude.toFixed(2)} m`}</dd></div>
                <div><dt>Capture time</dt><dd>{formatDateTime(metadata.capture_time ?? metadata.captured_at ?? null)}</dd></div>
                <div><dt>Camera make</dt><dd>{metadata.camera_make ?? "Not available"}</dd></div>
                <div><dt>Camera model</dt><dd>{metadata.camera_model ?? "Not available"}</dd></div>
                <div><dt>EXIF available</dt><dd>{metadata.exif_available ? "Yes" : "No"}</dd></div>
              </dl>
            ) : (
              <p className="panel-empty-note">Metadata appears after the image is uploaded.</p>
            )}
          </article>

          <article className="workbench-panel geo-panel">
            <div className="workbench-panel-heading compact-heading">
              <div>
                <p className="panel-kicker">LOCATION CONTEXT</p>
                <h2><MapPin size={17} /> Geospatial Analysis</h2>
              </div>
            </div>
            {metadata && hasGps ? (
              <div className="gps-coordinate-block">
                <span>IMAGE GPS</span>
                <strong>{formatCoordinate(metadata.latitude)}, {formatCoordinate(metadata.longitude)}</strong>
                {metadata.altitude !== null && <small>Altitude {metadata.altitude.toFixed(2)} m</small>}
              </div>
            ) : (
              <div className="gps-unavailable"><MapPin size={17} /><span>GPS data unavailable.</span></div>
            )}
            <p className="geo-disclaimer">Object boxes are associated with the source image only. No ground coordinates are inferred.</p>
          </article>
        </aside>
      </div>

      {metadata && (
        <section className="workbench-panel results-panel" aria-labelledby="detection-results-heading">
          <div className="results-heading-row">
            <div className="workbench-panel-heading compact-heading">
              <div>
                <p className="panel-kicker">MODEL OUTPUT</p>
                <h2 id="detection-results-heading">Detection results</h2>
              </div>
            </div>
            <div className="results-quick-stats">
              <span><strong>{detections.length}</strong> objects</span>
              <span><strong>{formatConfidence(averageConfidence)}</strong> average confidence</span>
            </div>
          </div>

          <div className="detection-legend" aria-label="Detection class colors">
            <span><i className="legend-person" /> Person</span>
            <span><i className="legend-vehicle" /> Vehicle</span>
          </div>

          {phase !== "complete" && detections.length === 0 ? (
            <div className="results-empty">
              <ScanLine size={22} />
              <strong>{phase === "detecting" ? "Detection is processing" : "No completed detections yet"}</strong>
              <span>Upload and analyze this image to populate real model results.</span>
            </div>
          ) : detections.length === 0 ? (
            <div className="results-empty">
              <ScanLine size={22} />
              <strong>No objects detected</strong>
              <span>The backend completed inference and returned zero detections for this image.</span>
            </div>
          ) : (
            <div className="detection-table-scroll">
              <table className="detection-table">
                <thead>
                  <tr><th>ID</th><th>Class</th><th>Confidence</th><th>X1</th><th>Y1</th><th>X2</th><th>Y2</th></tr>
                </thead>
                <tbody>
                  {detections.map((detection) => (
                    <tr key={detection.id}>
                      <td className="detection-id-cell">{detection.id}</td>
                      <td><span className={`class-pill ${boxClass(detection.class_name)}`}>{detection.class_name}</span></td>
                      <td className="confidence-cell">{formatConfidence(detection.confidence)}</td>
                      <td>{detection.bbox.x1.toFixed(2)}</td>
                      <td>{detection.bbox.y1.toFixed(2)}</td>
                      <td>{detection.bbox.x2.toFixed(2)}</td>
                      <td>{detection.bbox.y2.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </section>
  );
}