import {
  AlertCircle,
  CheckCircle2,
  CloudUpload,
  FileDown,
  Image as ImageIcon,
  LoaderCircle,
  MapPin,
  Info,
  Eye,
  EyeOff,
  RefreshCw,
  ScanLine,
  Trash2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  API_BASE_URL,
  getAvailableModels,
  getApiErrorMessage,
  getImage,
  getImageIntelligence,
  getImagePreviewUrl,
  getStoredDetections,
  listImages,
  listSurveys,
  processImageIntelligence,
  runDetection,
  uploadImage,
  type Detection,
  type DetectionModelVersion,
  type DetectionResponse,
  type ImageMetadata,
  type ImageIntelligenceResponse,
  type SurveyRecord,
} from "../../services/api";

type WorkflowPhase = "idle" | "uploading" | "detecting" | "complete" | "error";

const supportedImageExtensions = new Set([".jpg", ".jpeg", ".png", ".tif", ".tiff"]);
const fallbackModelOptions: {
  value: DetectionModelVersion;
  label: string;
}[] = [
  { value: "baseline", label: "Baseline · Person / vehicle" },
  { value: "visdrone10_yolo11n", label: "VisDrone10 · 10 classes" },
];

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

function boxClass(className: string, classId: number | null): string {
  if (className.toLowerCase() === "person") return "detection-person";
  if (className.toLowerCase() === "vehicle") return "detection-vehicle";
  return `detection-class-${classId ?? 0}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function ImageDetectionWorkbench({
  onDetectionComplete,
}: {
  onDetectionComplete?: () => void;
}) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [metadata, setMetadata] = useState<ImageMetadata | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [detectionResponse, setDetectionResponse] = useState<DetectionResponse | null>(null);
  const [modelVersion, setModelVersion] = useState<DetectionModelVersion>("visdrone10_yolo11n");
  const [phase, setPhase] = useState<WorkflowPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.35);
  const [storedImages, setStoredImages] = useState<ImageMetadata[]>([]);
  const [surveys, setSurveys] = useState<SurveyRecord[]>([]);
  const [selectedSurveyId, setSelectedSurveyId] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [selectedStoredImage, setSelectedStoredImage] = useState("");
  const [availableModelOptions, setAvailableModelOptions] = useState(fallbackModelOptions);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [imageMode, setImageMode] = useState<"annotated" | "original">("annotated");
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | null>(null);
  const [classSearch, setClassSearch] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [sortByConfidence, setSortByConfidence] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [autoLocalize, setAutoLocalize] = useState(true);
  const [intelligence, setIntelligence] = useState<ImageIntelligenceResponse | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    let active = true;
    setHistoryLoading(true);
    Promise.allSettled([listImages(), getAvailableModels(), listSurveys()])
      .then(([imageResult, modelResult, surveyResult]) => {
        if (!active) return;
        if (imageResult.status === "fulfilled") {
          setStoredImages(imageResult.value);
        } else {
          setHistoryError(getApiErrorMessage(imageResult.reason));
        }
        if (modelResult.status === "fulfilled") {
          const options = modelResult.value
            .filter((model) => model.weights_available)
            .map((model) => ({
              value: model.model_id,
              label: `${model.model_name} · ${model.class_count} classes`,
            }));
          if (options.length) setAvailableModelOptions(options);
        } else if (active) {
          setHistoryError(getApiErrorMessage(modelResult.reason));
        }
        if (surveyResult.status === "fulfilled") setSurveys(surveyResult.value);
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const refreshStoredImages = async () => {
    try {
      setStoredImages(await listImages());
      setHistoryError("");
    } catch (error) {
      setHistoryError(getApiErrorMessage(error));
    }
  };

  const selectFile = (nextFile?: File) => {
    if (!nextFile) return;
    const extension = `.${nextFile.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!supportedImageExtensions.has(extension)) {
      setFile(null);
      setPreviewUrl("");
      setMetadata(null);
      setDetections([]);
      setDetectionResponse(null);
      setIntelligence(null);
      setSelectedDetectionId(null);
      setImageMode("annotated");
      setZoom(1);
      setSelectedStoredImage("");
      if (inputRef.current) inputRef.current.value = "";
      setErrorMessage("Unsupported image format. Choose JPG, PNG, or TIFF.");
      setPhase("error");
      return;
    }

    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
    setMetadata(null);
    setDetections([]);
    setDetectionResponse(null);
    setIntelligence(null);
    setSelectedDetectionId(null);
    setImageMode("annotated");
    setZoom(1);
    setSelectedStoredImage("");
    setImageSize({ width: 0, height: 0 });
    setProgress(0);
    setErrorMessage("");
    setPhase("idle");
  };

  const startDetection = async (
    image: ImageMetadata,
    selectedModel: DetectionModelVersion = modelVersion,
  ) => {
    setPhase("detecting");
    setErrorMessage("");
    try {
      const imageId = image.image_id || image.id;
      const result = await runDetection(imageId, selectedModel);
      const storedResult = await getStoredDetections(imageId);
      setDetections(storedResult.detections);
      setDetectionResponse({
        ...storedResult,
        model_name: result.model_name,
        model_version: result.model_version,
        classes: result.classes,
        coordinate_system: result.coordinate_system,
        annotated_image_url: result.annotated_image_url,
      });
      setIntelligence(await getImageIntelligence(imageId).catch(() => null));
      setPhase("complete");
      onDetectionComplete?.();
    } catch (error) {
      setPhase("error");
      setErrorMessage(getApiErrorMessage(error));
    }
  };

  const startFullImageIntelligence = async (image: ImageMetadata) => {
    setPhase("detecting");
    setErrorMessage("");
    try {
      const result = await processImageIntelligence(
        image.image_id || image.id,
        modelVersion,
        autoLocalize,
      );
      setIntelligence(result);
      setDetections(result.detection.detections);
      setDetectionResponse(result.detection_run_response ?? {
        image_id: result.image.image_id,
        model_name: result.detection.detections[0]?.model_name ?? null,
        model_version: result.detection.detections[0]?.model_version ?? null,
        detection_count: result.detection.count,
        detections: result.detection.detections,
        annotated_image_url: result.detection.annotated_image_url ?? undefined,
      });
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
      const uploadedImage = await uploadImage(
        file,
        setProgress,
        selectedSurveyId ? Number(selectedSurveyId) : undefined,
      );
      setMetadata(uploadedImage);
      setPreviewUrl(getImagePreviewUrl(uploadedImage.image_id || uploadedImage.id));
      await refreshStoredImages();
      await startFullImageIntelligence(uploadedImage);
    } catch (error) {
      setPhase("error");
      setErrorMessage(getApiErrorMessage(error));
    }
  };

  const loadStoredImage = async (requestedImageId?: number) => {
    const imageId = requestedImageId ?? Number(selectedStoredImage);
    if (!Number.isInteger(imageId) || imageId <= 0) return;

    setHistoryLoading(true);
    setHistoryError("");
    setErrorMessage("");
    try {
      const [storedImage, storedResult, storedIntelligence] = await Promise.all([
        getImage(imageId),
        getStoredDetections(imageId),
        getImageIntelligence(imageId).catch(() => null),
      ]);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setMetadata(storedImage);
      setPreviewUrl(getImagePreviewUrl(imageId));
      setDetections(storedResult.detections);
      setDetectionResponse(
        storedResult.model_version
          ? {
              ...storedResult,
              classes: storedResult.model_version === "visdrone10_yolo11n"
                ? [
                    "pedestrian", "people", "bicycle", "car", "van",
                    "truck", "tricycle", "awning-tricycle", "bus", "motor",
                  ]
                : ["person", "vehicle"],
            }
          : null,
      );
      setIntelligence(storedIntelligence);
      setModelVersion(
        storedResult.model_version === "visdrone10_yolo11n"
          ? "visdrone10_yolo11n"
          : "baseline",
      );
      setImageSize({ width: storedImage.width ?? 0, height: storedImage.height ?? 0 });
      setSelectedDetectionId(null);
      setImageMode("annotated");
      setPhase(storedResult.model_version ? "complete" : "idle");
    } catch (error) {
      setHistoryError(getApiErrorMessage(error));
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    const imageId = Number(new URLSearchParams(window.location.search).get("image_id"));
    if (Number.isInteger(imageId) && imageId > 0) {
      setSelectedStoredImage(String(imageId));
      void loadStoredImage(imageId);
    }
  }, []);

  const clearSelection = () => {
    setFile(null);
    setPreviewUrl("");
    setMetadata(null);
    setDetections([]);
    setDetectionResponse(null);
    setIntelligence(null);
    setProgress(0);
    setErrorMessage("");
    setSelectedDetectionId(null);
    setImageSize({ width: 0, height: 0 });
    setSelectedStoredImage("");
    setImageMode("annotated");
    setZoom(1);
    setPhase("idle");
    if (inputRef.current) inputRef.current.value = "";
  };

  const hasGps = metadata?.latitude !== null &&
    metadata?.latitude !== undefined &&
    metadata?.longitude !== null &&
    metadata?.longitude !== undefined;
  const width = imageSize.width || metadata?.width || 0;
  const height = imageSize.height || metadata?.height || 0;
  const visibleDetections = detections
    .filter((detection) => detection.confidence >= confidenceThreshold)
    .filter((detection) => (
      classFilter === "all" || detection.class_name === classFilter
    ))
    .filter((detection) => (
      detection.class_name.toLowerCase().includes(classSearch.trim().toLowerCase())
    ))
    .sort((left, right) => (
      sortByConfidence ? right.confidence - left.confidence : left.id - right.id
    ));
  const averageConfidence = visibleDetections.length
    ? visibleDetections.reduce((total, detection) => total + detection.confidence, 0) /
      visibleDetections.length
    : 0;
  const isBusy = phase === "uploading" || phase === "detecting";
  const modelName = detectionResponse?.model_name ?? (
    modelVersion === "visdrone10_yolo11n" ? "YOLO11n VisDrone10" : "YOLO11n"
  );
  const selectedModelVersion = modelVersion === "baseline" ? "drone_person_vehicle" : modelVersion;
  const reportedModelVersion = detectionResponse?.model_version ?? (
    modelVersion === "baseline" ? "drone_person_vehicle" : modelVersion
  );
  const resultClasses = detectionResponse?.classes ?? (
    modelVersion === "visdrone10_yolo11n"
      ? ["pedestrian", "people", "bicycle", "car", "van", "truck", "tricycle", "awning-tricycle", "bus", "motor"]
      : ["person", "vehicle"]
  );
  const needsServerPreview = Boolean(
    file && /\.(tif|tiff)$/i.test(file.name) && !metadata,
  );

  const exportCsv = () => {
    if (!metadata || visibleDetections.length === 0) return;
    const columns = [
      "detection_id", "image_id", "class_id", "class_name", "confidence",
      "x1", "y1", "x2", "y2", "model_name", "model_version",
    ];
    const rows = visibleDetections.map((detection) => [
      detection.id,
      metadata.image_id || metadata.id,
      detection.class_id,
      detection.class_name,
      detection.confidence,
      detection.bbox.x1,
      detection.bbox.y1,
      detection.bbox.x2,
      detection.bbox.y2,
      detection.model_name ?? detectionResponse?.model_name ?? "",
      detection.model_version ?? detectionResponse?.model_version ?? "",
    ]);
    const csv = [columns, ...rows]
      .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `image-${metadata.image_id || metadata.id}-detections.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

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

          <div className="model-selector-block">
            <label htmlFor="detection-model">Detection model</label>
            <select
              id="detection-model"
              value={modelVersion}
              onChange={(event) => {
                const selectedModel = availableModelOptions.find(
                  (option) => option.value === event.currentTarget.value,
                );
                if (selectedModel) setModelVersion(selectedModel.value);
                setErrorMessage("");
              }}
              disabled={isBusy}
            >
              {availableModelOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            {modelVersion === "visdrone10_yolo11n" && (
              <p className="model-development-note">
                <Info size={14} />
                <span>Supplied checkpoint metrics report mAP50 32.9% and mAP50–95 18.3%; these have not been independently reproduced.</span>
              </p>
            )}
          </div>

          <div className="model-selector-block">
            <label htmlFor="upload-survey">Associate with survey</label>
            <select
              id="upload-survey"
              value={selectedSurveyId}
              onChange={(event) => setSelectedSurveyId(event.currentTarget.value)}
              disabled={isBusy}
            >
              <option value="">No survey</option>
              {surveys.map((survey) => (
                <option key={survey.id} value={survey.id}>{survey.name}</option>
              ))}
            </select>
          </div>

          <div className="stored-image-picker">
            <label htmlFor="stored-image-select">Or reopen an uploaded image</label>
            <div className="stored-image-controls">
              <select
                id="stored-image-select"
                value={selectedStoredImage}
                onChange={(event) => setSelectedStoredImage(event.target.value)}
                disabled={isBusy || historyLoading || storedImages.length === 0}
              >
                <option value="">
                  {historyLoading ? "Loading uploaded images…" : "Select an image"}
                </option>
                {storedImages.map((image) => (
                  <option key={image.image_id} value={image.image_id}>
                    #{image.image_id} · {image.filename}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void loadStoredImage()}
                disabled={!selectedStoredImage || historyLoading || isBusy}
              >
                Load results
              </button>
            </div>
            {historyError && <p className="history-error" role="alert">{historyError}</p>}
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
                  {file && <small>{formatFileSize(file.size)}</small>}
                </div>
                <div className="preview-toolbar-actions">
                  <button
                    type="button"
                    className={imageMode === "original" ? "subtle-toggle-button is-active" : "subtle-toggle-button"}
                    onClick={() => setImageMode("original")}
                    aria-pressed={imageMode === "original"}
                  >
                    Original
                  </button>
                  <button
                    type="button"
                    className={imageMode === "annotated" ? "subtle-toggle-button is-active" : "subtle-toggle-button"}
                    onClick={() => setImageMode("annotated")}
                    aria-pressed={imageMode === "annotated"}
                  >
                    Annotated
                  </button>
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
              </div>
              <div className="detection-image-scroll">
                <figure
                  className="detection-image-frame"
                  style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
                >
                  {needsServerPreview ? (
                    <div className="server-preview-pending">
                      TIFF preview will be available after upload.
                    </div>
                  ) : (
                    <img
                      src={imageMode === "annotated" && detectionResponse?.annotated_image_url
                        ? `${API_BASE_URL}${detectionResponse.annotated_image_url}`
                        : previewUrl}
                      alt={`Preview of ${file?.name ?? metadata?.filename ?? "uploaded drone image"}`}
                      onLoad={(event) => {
                        if (!metadata?.width || !metadata?.height) {
                          setImageSize({
                            width: event.currentTarget.naturalWidth,
                            height: event.currentTarget.naturalHeight,
                          });
                        }
                      }}
                      onError={() => {
                        setErrorMessage("The selected file could not be decoded as an image.");
                        setPhase("error");
                      }}
                    />
                  )}
                {imageMode === "annotated" && !detectionResponse?.annotated_image_url && visibleDetections.length > 0 && width > 0 && height > 0 && (
                  <svg
                    className="detection-overlay"
                    viewBox={`0 0 ${width} ${height}`}
                    preserveAspectRatio="none"
                    role="img"
                    aria-label={`${visibleDetections.length} detected object bounding boxes`}
                  >
                    {visibleDetections.map((detection) => {
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
                        <g
                          key={detection.id}
                          className={`${boxClass(detection.class_name, detection.class_id)} ${selectedDetectionId === detection.id ? "is-selected" : ""}`}
                        >
                          {showBoxes && (
                            <rect
                              className="detection-box"
                              x={x1}
                              y={y1}
                              width={Math.max(0, x2 - x1)}
                              height={Math.max(0, y2 - y1)}
                              vectorEffect="non-scaling-stroke"
                            />
                          )}
                          {showLabels && (
                            <>
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
                            </>
                          )}
                        </g>
                      );
                    })}
                  </svg>
                )}
                </figure>
              </div>
              <div className="annotation-controls" aria-label="Image annotation controls">
                <button
                  type="button"
                  className="subtle-toggle-button"
                  onClick={() => setShowBoxes((visible) => !visible)}
                  aria-pressed={showBoxes}
                >
                  {showBoxes ? <Eye size={14} /> : <EyeOff size={14} />}
                  Boxes
                </button>
                <button
                  type="button"
                  className="subtle-toggle-button"
                  onClick={() => setShowLabels((visible) => !visible)}
                  aria-pressed={showLabels}
                >
                  {showLabels ? <Eye size={14} /> : <EyeOff size={14} />}
                  Labels
                </button>
                <span className="annotation-control-spacer" />
                <button
                  type="button"
                  className="subtle-icon-button"
                  onClick={() => setZoom((current) => Math.max(1, current - 0.25))}
                  disabled={zoom <= 1}
                  aria-label="Zoom out"
                >
                  <ZoomOut size={15} />
                </button>
                <span className="zoom-level">{Math.round(zoom * 100)}%</span>
                <button
                  type="button"
                  className="subtle-icon-button"
                  onClick={() => setZoom((current) => Math.min(3, current + 0.25))}
                  disabled={zoom >= 3}
                  aria-label="Zoom in"
                >
                  <ZoomIn size={15} />
                </button>
                <button
                  type="button"
                  className="subtle-toggle-button"
                  onClick={() => setZoom(1)}
                  disabled={zoom === 1}
                >
                  Fit
                </button>
              </div>
              <div className="preview-dimensions">
                {width > 0 && height > 0 ? `${width} × ${height} px` : "Reading image dimensions…"}
                {file && <span>{formatFileSize(file.size)}</span>}
                {!file && metadata?.detection_count !== undefined && (
                  <span>{metadata.detection_count} saved detections</span>
                )}
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
              <span>Running image detection and eligible GPS-free localization…</span>
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
                onClick={() => void startFullImageIntelligence(metadata)}
                disabled={isBusy}
              >
                <RefreshCw size={16} /> Retry detection
              </button>
            )}
            {metadata && phase === "complete" && detectionResponse?.model_version !== selectedModelVersion && (
              <button
                type="button"
                className="workbench-primary-button"
                onClick={() => void startDetection(metadata, modelVersion)}
                disabled={isBusy}
              >
                <RefreshCw size={16} /> Run selected model
              </button>
            )}
            {phase === "detecting" && (
              <span className="action-note"><LoaderCircle size={14} className="spin" /> Processing</span>
            )}
            {file && !metadata && (
              <label className="intelligence-localization-toggle">
                <input type="checkbox" checked={autoLocalize} onChange={(event) => setAutoLocalize(event.currentTarget.checked)} />
                Run GPS-free UAV-VisLoc for verified dataset images
              </label>
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
                <div><dt>GPS available</dt><dd>{metadata.gps_available ? "Yes" : "No"}</dd></div>
                <div><dt>Altitude</dt><dd>{metadata.altitude === null ? "Not available" : `${metadata.altitude.toFixed(2)} m`}</dd></div>
                <div><dt>Capture time</dt><dd>{formatDateTime(metadata.capture_time ?? metadata.captured_at ?? null)}</dd></div>
                <div><dt>Camera make</dt><dd>{metadata.camera_make ?? "Not available"}</dd></div>
                <div><dt>Camera model</dt><dd>{metadata.camera_model ?? "Not available"}</dd></div>
                <div><dt>Orientation</dt><dd>{metadata.orientation === null ? "Not available" : `EXIF ${metadata.orientation}`}</dd></div>
                <div><dt>Focal length</dt><dd>{metadata.focal_length === null ? "Not available" : `${metadata.focal_length.toFixed(2)} mm`}</dd></div>
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
            {intelligence && (
              <div className="intelligence-coordinate-sources">
                <h3>Coordinate sources</h3>
                <p><strong>EXIF GPS:</strong> {intelligence.geospatial.exif_coordinate.available
                  ? `${formatCoordinate(intelligence.geospatial.exif_coordinate.latitude)}, ${formatCoordinate(intelligence.geospatial.exif_coordinate.longitude)} · embedded image metadata`
                  : "Unavailable"}</p>
                <p><strong>Dataset ground truth:</strong> {intelligence.geospatial.dataset_ground_truth.available
                  ? `${formatCoordinate(intelligence.geospatial.dataset_ground_truth.latitude)}, ${formatCoordinate(intelligence.geospatial.dataset_ground_truth.longitude)} · UAV-VisLoc dataset, EPSG:4326`
                  : "Unavailable"}</p>
                <p><strong>Predicted UAV position:</strong> Not available; this pipeline returns satellite candidates only.</p>
              </div>
            )}
          </article>

          {intelligence && (
            <article className="workbench-panel dataset-metadata-panel">
              <div className="workbench-panel-heading compact-heading">
                <div><p className="panel-kicker">VERIFIED DATASET RECORD</p><h2>UAV-VisLoc metadata</h2></div>
              </div>
              {intelligence.dataset_identity.status === "matched" && intelligence.dataset_metadata ? (
                <>
                  <p>Flight {intelligence.dataset_identity.flight_sequence} · {intelligence.dataset_identity.dataset_relative_path}</p>
                  <p>Match: {intelligence.dataset_identity.method} ({Math.round((intelligence.dataset_identity.confidence ?? 0) * 100)}%); source {intelligence.dataset_identity.metadata_source_csv}</p>
                  <dl className="metadata-list dataset-source-fields">
                    {Object.entries(intelligence.dataset_metadata).map(([key, value]) => (
                      <div key={key}><dt>{key}</dt><dd>{value === null || value === undefined || value === "" ? "Not available" : String(value)}</dd></div>
                    ))}
                  </dl>
                </>
              ) : (
                <p className="panel-empty-note">No verified UAV-VisLoc dataset match ({intelligence.dataset_identity.status}). No dataset coordinates were assigned.</p>
              )}
            </article>
          )}
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
              <span><strong>{visibleDetections.length}</strong> objects</span>
              <span><strong>{formatConfidence(averageConfidence)}</strong> average confidence</span>
            </div>
          </div>

          <div className="model-info-strip">
            <strong>Model:</strong> {modelName} ({reportedModelVersion})
            <span>·</span>
            <strong>Classes:</strong> {resultClasses.join(", ")}
            <span>·</span>
            <strong>Confidence threshold:</strong> {formatConfidence(confidenceThreshold)}
          </div>
          <p className="coordinate-system-note">
            Bounding boxes use original-image pixel coordinates in top-left-origin xyxy order.
          </p>

          <div className="confidence-filter-block">
            <label htmlFor="confidence-threshold">Minimum confidence</label>
            <input
              id="confidence-threshold"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={confidenceThreshold}
              onChange={(event) => setConfidenceThreshold(Number(event.target.value))}
            />
            <span>{formatConfidence(confidenceThreshold)}</span>
          </div>

          <div className="detection-table-controls">
            <label>
              <span>Search class</span>
              <input
                type="search"
                value={classSearch}
                onChange={(event) => setClassSearch(event.target.value)}
                placeholder="e.g. pedestrian"
                aria-label="Search detections by class"
              />
            </label>
            <label>
              <span>Filter class</span>
              <select
                value={classFilter}
                onChange={(event) => setClassFilter(event.target.value)}
                aria-label="Filter detections by class"
              >
                <option value="all">All classes</option>
                {Array.from(new Set(detections.map((detection) => detection.class_name))).map((className) => (
                  <option key={className} value={className}>{className}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="subtle-toggle-button"
              onClick={() => setSortByConfidence((sorted) => !sorted)}
              aria-pressed={sortByConfidence}
            >
              {sortByConfidence ? "Sort by ID" : "Sort by confidence"}
            </button>
            <button
              type="button"
              className="subtle-toggle-button"
              onClick={exportCsv}
              disabled={visibleDetections.length === 0}
            >
              <FileDown size={14} /> Export CSV
            </button>
          </div>

          <div className="detection-legend" aria-label="Detection class colors">
            {resultClasses.map((className, classId) => (
              <span key={className}>
                <i className={`legend-class-${classId}`} />
                {className}
              </span>
            ))}
          </div>

          {phase !== "complete" && detections.length === 0 ? (
            <div className="results-empty">
              <ScanLine size={22} />
              <strong>{phase === "detecting" ? "Detection is processing" : "No completed detections yet"}</strong>
              <span>Upload and analyze this image to populate real model results.</span>
            </div>
          ) : visibleDetections.length === 0 ? (
            <div className="results-empty">
              <ScanLine size={22} />
              <strong>
                {detections.length === 0
                  ? "No objects detected"
                  : "No objects at the selected confidence threshold"}
              </strong>
              <span>
                {detections.length === 0
                  ? "The selected model returned no detections for this image."
                  : "Lower the threshold to review detections that were still stored by the model."}
              </span>
            </div>
          ) : (
            <div className="detection-table-scroll">
              <table className="detection-table">
                <thead>
                  <tr>
                    <th>Detection ID</th><th>Class ID</th><th>Class</th>
                    <th>Confidence</th><th>X1</th><th>Y1</th><th>X2</th><th>Y2</th>
                    <th>Model</th><th>Version</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleDetections.map((detection) => (
                    <tr
                      key={detection.id}
                      className={selectedDetectionId === detection.id ? "is-selected" : ""}
                      tabIndex={0}
                      aria-selected={selectedDetectionId === detection.id}
                      onClick={() => setSelectedDetectionId(detection.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedDetectionId(detection.id);
                        }
                      }}
                    >
                      <td className="detection-id-cell">{detection.id}</td>
                      <td>{detection.class_id}</td>
                      <td><span className={`class-pill ${boxClass(detection.class_name, detection.class_id)}`}>{detection.class_name}</span></td>
                      <td className="confidence-cell">{formatConfidence(detection.confidence)}</td>
                      <td>{detection.bbox.x1.toFixed(2)}</td>
                      <td>{detection.bbox.y1.toFixed(2)}</td>
                      <td>{detection.bbox.x2.toFixed(2)}</td>
                      <td>{detection.bbox.y2.toFixed(2)}</td>
                      <td>{detection.model_name ?? modelName}</td>
                      <td>{detection.model_version ?? reportedModelVersion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {intelligence && metadata && (
        <>
          <section className="workbench-panel intelligence-localization-panel" aria-labelledby="intelligence-localization-heading">
            <div className="results-heading-row">
              <div className="workbench-panel-heading compact-heading"><div><p className="panel-kicker">GPS-FREE VISUAL RETRIEVAL</p><h2 id="intelligence-localization-heading">UAV-VisLoc results</h2></div></div>
              <span>{intelligence.localization.status.replaceAll("_", " ")}</span>
            </div>
            {intelligence.localization.message && <p>{intelligence.localization.message}</p>}
            <div className="localization-estimate-summary" role="status">
              <strong>Geometric localization: {intelligence.geospatial.predicted_uav_coordinate.status?.replaceAll("_", " ") ?? "not available"}</strong>
              {intelligence.geospatial.predicted_uav_coordinate.available
                ? <span>Estimated image center: {intelligence.geospatial.predicted_uav_coordinate.latitude?.toFixed(6)}, {intelligence.geospatial.predicted_uav_coordinate.longitude?.toFixed(6)} · EPSG:4326</span>
                : <span>{intelligence.geospatial.predicted_uav_coordinate.reason ?? intelligence.localization.localization_estimate?.reason ?? "No candidate passed geometric quality control; no predicted coordinates are reported."}</span>}
              {intelligence.geospatial.localization_evaluation?.available && <span>Ground-truth error: {intelligence.geospatial.localization_evaluation.error_m?.toFixed(2)} m · within 5/10/25/50 m: {[
                intelligence.geospatial.localization_evaluation.within_5m,
                intelligence.geospatial.localization_evaluation.within_10m,
                intelligence.geospatial.localization_evaluation.within_25m,
                intelligence.geospatial.localization_evaluation.within_50m,
              ].map((value) => value ? "yes" : "no").join(" / ")}</span>}
              {intelligence.geospatial.localization_evaluation?.reason && <span>{intelligence.geospatial.localization_evaluation.reason}</span>}
              {intelligence.geospatial.localization_evaluation?.note && <small>{intelligence.geospatial.localization_evaluation.note}</small>}
            </div>
            {intelligence.localization.candidates.length > 0 ? (
              <>
                <p>{intelligence.localization.candidates.length} ranked satellite candidates · {intelligence.localization.processing_time_seconds?.toFixed(1) ?? "—"} sec. Retrieval similarity is ranking evidence, not a localization fix.</p>
                <div className="intelligence-candidates-grid">
                  {intelligence.localization.candidates.slice(0, 5).map((candidate) => (
                    <article key={candidate.satellite_tile_id} className="intelligence-candidate-card">
                      <img src={`${API_BASE_URL}${candidate.preview_url}`} alt={`Satellite patch ${candidate.satellite_tile_id}`} loading="lazy" />
                      <strong>#{candidate.rank} · {candidate.satellite_tile_id}</strong>
                      <span>Similarity {candidate.similarity_score.toFixed(4)}</span>
                      <span>{candidate.local_feature_match_count ?? "—"} matches · {candidate.ransac_inlier_count ?? "—"} inliers</span>
                      <span>{candidate.verification_status.replaceAll("_", " ")}</span>
                      {candidate.estimated_image_center?.status === "geometrically_verified" && <span>Image-center projection · {candidate.estimated_image_center.quality} quality · {candidate.estimated_image_center.median_reprojection_error_px?.toFixed(2)} px median error</span>}
                      {candidate.estimated_image_center?.reason && <small>Projection rejected: {candidate.estimated_image_center.reason}</small>}
                      <small>Satellite patch center: {candidate.latitude.toFixed(6)}, {candidate.longitude.toFixed(6)} · EPSG:4326</small>
                    </article>
                  ))}
                </div>
                <details className="intelligence-candidate-details">
                  <summary>View all {intelligence.localization.candidates.length} ranked candidates</summary>
                  <div className="detection-table-scroll">
                    <table className="detection-table">
                      <thead><tr><th>Rank</th><th>Satellite patch</th><th>Similarity</th><th>Matches</th><th>RANSAC inliers</th><th>Inlier ratio</th><th>Reprojection error</th><th>Estimated image center</th><th>Patch center (WGS84)</th><th>Verification</th></tr></thead>
                      <tbody>{intelligence.localization.candidates.map((candidate) => (
                        <tr key={candidate.satellite_tile_id}>
                          <td>{candidate.rank}</td><td>{candidate.satellite_tile_id}</td>
                          <td>{candidate.similarity_score.toFixed(4)}</td>
                          <td>{candidate.local_feature_match_count ?? "—"}</td>
                          <td>{candidate.ransac_inlier_count ?? "—"}</td>
                          <td>{candidate.inlier_ratio === null ? "—" : candidate.inlier_ratio.toFixed(3)}</td>
                          <td>{candidate.estimated_image_center?.median_reprojection_error_px == null ? "—" : `${candidate.estimated_image_center.median_reprojection_error_px.toFixed(2)} px`}</td>
                          <td>{candidate.estimated_image_center?.status === "geometrically_verified" ? `${candidate.estimated_image_center.latitude?.toFixed(6)}, ${candidate.estimated_image_center.longitude?.toFixed(6)}` : candidate.estimated_image_center?.reason ?? "Not verified"}</td>
                          <td>{candidate.latitude.toFixed(6)}, {candidate.longitude.toFixed(6)}</td>
                          <td>{candidate.verification_status.replaceAll("_", " ")}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                </details>
                {intelligence.geospatial.satellite_candidate_region_rank_for_ground_truth_map !== null && (
                  <p>Dataset ground-truth satellite region appears at candidate rank {intelligence.geospatial.satellite_candidate_region_rank_for_ground_truth_map} (evaluation only; ground truth was not used for retrieval).</p>
                )}
              </>
            ) : <p className="panel-empty-note">No satellite candidates are stored for this image.</p>}
            {(intelligence.localization.candidates.length > 0 || intelligence.geospatial.dataset_ground_truth.available || intelligence.geospatial.predicted_uav_coordinate.available) && (
              <button type="button" className="subtle-toggle-button" onClick={() => navigate("/map", { state: {
                localizationCandidates: intelligence.localization.candidates,
                localizationMode: "gps_free",
                datasetGroundTruth: intelligence.geospatial.dataset_ground_truth.available ? intelligence.geospatial.dataset_ground_truth : null,
                localizationEstimate: intelligence.geospatial.predicted_uav_coordinate.available ? {
                  ...intelligence.geospatial.predicted_uav_coordinate,
                  error_m: intelligence.geospatial.localization_evaluation?.error_m ?? null,
                } : null,
                datasetImageId: metadata.image_id || metadata.id,
              } })}>
                View geospatial results on map
              </button>
            )}
            <p className="geo-disclaimer">{intelligence.localization.note ?? "A predicted center is shown only when geometric checks pass. Candidate patch centers are not UAV positions."}</p>
          </section>
          <section className="workbench-panel intelligence-download-panel" aria-label="Image intelligence exports">
            <strong>Processing summary:</strong> {intelligence.processing.runs.map((run) => `${run.pipeline} ${run.status}${run.processing_seconds === null ? "" : ` (${run.processing_seconds.toFixed(1)} sec)`}`).join(" · ") || "No processing runs recorded"}
            <div className="intelligence-export-actions">
              <a href={`${API_BASE_URL}/api/intelligence/images/${metadata.image_id || metadata.id}/export.json`}>Download JSON</a>
              <a href={`${API_BASE_URL}/api/intelligence/images/${metadata.image_id || metadata.id}/export.csv`}>Download CSV</a>
              <a href={`${API_BASE_URL}/api/intelligence/images/${metadata.image_id || metadata.id}/report.pdf`}>Download PDF report</a>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
