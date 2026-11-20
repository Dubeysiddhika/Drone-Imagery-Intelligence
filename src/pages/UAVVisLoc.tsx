import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  FileImage,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import {
  API_BASE_URL,
  getApiErrorMessage,
  runUAVVisLocLocalization,
  uploadImage,
  getUAVVisLocRecord,
  getUAVVisLocStats,
  listImages,
  listUAVVisLocRecords,
  type UAVVisLocRecord,
  type UAVVisLocRecordsResponse,
  type UAVVisLocStats,
  type ImageMetadata,
  type UAVVisLocLocalizationResponse,
  type UAVVisLocMode,
} from "../services/api";

const PAGE_SIZE = 25;

function formatValue(
  value: number | null,
  decimals = 2,
): string {
  return value === null || value === undefined
    ? "—"
    : value.toFixed(decimals);
}

export default function UAVVisLocPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<UAVVisLocStats | null>(null);
  const [recordPage, setRecordPage] =
    useState<UAVVisLocRecordsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedRecord, setSelectedRecord] =
    useState<UAVVisLocRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [queryFile, setQueryFile] = useState<File | null>(null);
  const [queryPreview, setQueryPreview] = useState("");
  const [storedImages, setStoredImages] = useState<ImageMetadata[]>([]);
  const [selectedImageId, setSelectedImageId] = useState("");
  const [imageListLoading, setImageListLoading] = useState(true);
  const [imageListError, setImageListError] = useState("");
  const [localizationMode, setLocalizationMode] = useState<UAVVisLocMode>("gps_free");
  const [uploadedQuery, setUploadedQuery] = useState<ImageMetadata | null>(null);
  const [localization, setLocalization] = useState<UAVVisLocLocalizationResponse | null>(null);
  const [localizationPhase, setLocalizationPhase] = useState<"idle" | "uploading" | "localizing" | "complete" | "error">("idle");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [localizationError, setLocalizationError] = useState("");
  const selectedImage = useMemo(
    () => storedImages.find((image) => String(image.image_id || image.id) === selectedImageId) ?? null,
    [storedImages, selectedImageId],
  );

  useEffect(() => {
    let active = true;
    listImages().then((images) => {
      if (active) {
        setStoredImages(images);
        setImageListError("");
      }
    }).catch((error: unknown) => {
      if (active) setImageListError(getApiErrorMessage(error));
    }).finally(() => {
      if (active) setImageListLoading(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => () => {
    if (queryPreview.startsWith("blob:")) URL.revokeObjectURL(queryPreview);
  }, [queryPreview]);

  function chooseQuery(file?: File) {
    if (!file) return;
    if (!/\.(jpe?g|png|tiff?)$/i.test(file.name)) {
      setLocalizationError("Choose a JPG, PNG, or TIFF drone image.");
      return;
    }
    setQueryFile(file);
    setQueryPreview(URL.createObjectURL(file));
    setSelectedImageId("");
    setUploadedQuery(null);
    setLocalization(null);
    setLocalizationError("");
    setLocalizationPhase("idle");
  }

  function selectStoredImage(imageId: string) {
    setSelectedImageId(imageId);
    setQueryFile(null);
    setQueryPreview("");
    setUploadedQuery(storedImages.find((image) => String(image.image_id || image.id) === imageId) ?? null);
    setLocalization(null);
    setLocalizationError("");
    setLocalizationPhase("idle");
  }

  async function startLocalization() {
    if (!queryFile && !selectedImage) return;
    setLocalizationError("");
    try {
      let image = selectedImage;
      if (queryFile) {
        setLocalizationPhase("uploading");
        setUploadProgress(0);
        image = await uploadImage(queryFile, setUploadProgress);
        const imageId = image.image_id || image.id;
        setStoredImages((current) => [image!, ...current.filter((existing) => (existing.image_id || existing.id) !== imageId)]);
        setSelectedImageId(String(imageId));
      }
      if (!image) throw new Error("Choose an uploaded image or select a drone image file first.");
      if (localizationMode === "gps_assisted" && !image.gps_available) {
        throw new Error("GPS-assisted localization requires valid latitude and longitude in this image's stored EXIF metadata. Select GPS-free mode or choose a GPS-tagged image.");
      }
      setUploadedQuery(image);
      setLocalizationPhase("localizing");
      const result = await runUAVVisLocLocalization(image.image_id || image.id, localizationMode);
      setLocalization(result);
      setLocalizationPhase("complete");
    } catch (error) {
      setLocalizationError(getApiErrorMessage(error));
      setLocalizationPhase("error");
    }
  }

  useEffect(() => {
    let active = true;

    async function loadData() {
      setLoading(true);
      setError("");

      try {
        const [nextStats, nextRecords] = await Promise.all([
          getUAVVisLocStats(),
          listUAVVisLocRecords((page - 1) * PAGE_SIZE, PAGE_SIZE),
        ]);

        if (active) {
          setStats(nextStats);
          setRecordPage(nextRecords);
        }
      } catch (err) {
        if (active) {
          setError(getApiErrorMessage(err));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadData();

    return () => {
      active = false;
    };
  }, [page]);

  const displayedRecords = useMemo(() => {
    const records = recordPage?.records ?? [];
    const term = search.trim().toLowerCase();

    if (!term) {
      return records;
    }

    // Search the records currently loaded on this page.
    return records.filter((record) =>
      [
        record.filename,
        record.relative_path,
        record.capture_time_raw ?? "",
        record.metadata_csv,
        String(record.latitude),
        String(record.longitude),
      ]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [recordPage, search]);

  const totalRecords = recordPage?.total ?? stats?.total_records ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRecords / PAGE_SIZE));
  const firstRecord =
    totalRecords === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRecord = Math.min(page * PAGE_SIZE, totalRecords);

  async function openRecord(recordId: number) {
    setDetailLoading(true);
    setDetailError("");

    try {
      const record = await getUAVVisLocRecord(recordId);
      setSelectedRecord(record);
    } catch (err) {
      setDetailError(getApiErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  }

  function refreshPage() {
    setPage((current) => current);
    setLoading(true);
    setError("");

    Promise.all([
      getUAVVisLocStats(),
      listUAVVisLocRecords((page - 1) * PAGE_SIZE, PAGE_SIZE),
    ])
      .then(([nextStats, nextRecords]) => {
        setStats(nextStats);
        setRecordPage(nextRecords);
      })
      .catch((err: unknown) => {
        setError(getApiErrorMessage(err));
      })
      .finally(() => {
        setLoading(false);
      });
  }

  return (
    <div className="uav-page">
      <header className="uav-page-header">
        <div>
          <p className="dashboard-eyebrow">
            GEOSPATIAL INTELLIGENCE / RESEARCH DATA
          </p>
          <h1>UAV-VisLoc Dataset</h1>
          <p className="page-description">
            Browse image capture coordinates, recorded heights, capture
            times, and available camera-orientation metadata.
          </p>
        </div>

        <button
          type="button"
          className="uav-refresh-button"
          onClick={refreshPage}
          disabled={loading}
        >
          <RefreshCw size={16} aria-hidden="true" />
          Refresh data
        </button>
      </header>

      <section className="uav-localization-panel" aria-labelledby="localization-heading">
        <div className="uav-localization-heading">
          <div>
            <p className="dashboard-eyebrow">VISUAL RETRIEVAL / CPU INFERENCE</p>
            <h2 id="localization-heading">Satellite candidate localization</h2>
              <p>Choose GPS-free visual retrieval or explicitly restrict retrieval using this image’s valid EXIF GPS.</p>
          </div>
          <span className="uav-visual-mode">DINOv2 + SuperPoint / LightGlue</span>
        </div>
        <div className="uav-localization-controls">
          <label className="uav-image-select" htmlFor="uav-existing-image">
            Uploaded image
            <select
              id="uav-existing-image"
              aria-label="Select uploaded drone image"
              value={selectedImageId}
              onChange={(event) => selectStoredImage(event.currentTarget.value)}
              disabled={imageListLoading || localizationPhase === "uploading" || localizationPhase === "localizing"}
            >
              <option value="">{imageListLoading ? "Loading uploaded images…" : "Select an uploaded image"}</option>
              {storedImages.map((image) => <option key={image.image_id || image.id} value={image.image_id || image.id}>{image.filename}{image.gps_available ? " · GPS available" : " · GPS unavailable"}</option>)}
            </select>
          </label>
          <label className="uav-query-file" htmlFor="uav-query-image">
            <FileImage size={17} aria-hidden="true" />
            <span>{queryFile?.name ?? "Or upload a new drone image"}</span>
          </label>
          <input
            id="uav-query-image"
            type="file"
            accept=".jpg,.jpeg,.png,.tif,.tiff,image/jpeg,image/png,image/tiff"
            onChange={(event) => chooseQuery(event.currentTarget.files?.[0])}
            disabled={localizationPhase === "uploading" || localizationPhase === "localizing"}
          />
          <label className="uav-mode-select" htmlFor="uav-localization-mode">
            Localization mode
            <select
              id="uav-localization-mode"
              aria-label="Localization mode"
              value={localizationMode}
              onChange={(event) => setLocalizationMode(event.currentTarget.value as UAVVisLocMode)}
              disabled={localizationPhase === "uploading" || localizationPhase === "localizing"}
            >
              <option value="gps_free">GPS-free visual retrieval</option>
              <option value="gps_assisted">GPS-assisted satellite-footprint filter</option>
            </select>
          </label>
          <button
            type="button"
            className="uav-run-localization"
            onClick={() => void startLocalization()}
            disabled={(!queryFile && !selectedImageId) || localizationPhase === "uploading" || localizationPhase === "localizing"}
          >
            {localizationPhase === "uploading" || localizationPhase === "localizing"
              ? <LoaderCircle size={15} className="uav-spin" />
              : <Search size={15} />}
            {localizationPhase === "uploading" ? "Uploading…" : localizationPhase === "localizing" ? "Searching candidates…" : "Start localization"}
          </button>
        </div>
        {localizationPhase === "uploading" && (
          <div className="uav-upload-progress">
            <span>Uploading query image: {uploadProgress}%</span>
            <progress value={uploadProgress} max={100} />
          </div>
        )}
        {localizationPhase === "localizing" && (
          <div className="uav-localization-progress" role="status" aria-live="polite">
            <LoaderCircle size={16} className="uav-spin" />
            <span>{localizationMode === "gps_assisted"
              ? "GPS-assisted mode is filtering to indexed satellite-map footprints containing the selected image’s stored EXIF coordinate, then running DINOv2 retrieval and bounded matching. This CPU-only step can take a while."
              : "GPS-free mode does not read EXIF coordinates for retrieval. Encoding at 280 px, retrieving Top-50, expanding one ring to a 75-patch budget, then matching the top five on CPU."}</span>
          </div>
        )}
        {imageListError && <div className="uav-inline-error" role="alert">{imageListError}</div>}
        {selectedImage && <p className="uav-selected-image-status">Selected: {selectedImage.filename} · {selectedImage.gps_available ? `GPS ${selectedImage.latitude?.toFixed(6)}, ${selectedImage.longitude?.toFixed(6)}` : "No valid GPS metadata"}</p>}
        {localizationMode === "gps_assisted" && queryFile && <p className="uav-selected-image-status">GPS-assisted mode will require valid GPS after upload; it will not fall back to GPS-free search.</p>}
        {localizationError && <div className="uav-inline-error" role="alert">{localizationError}</div>}

        {localization && (
          <div className="uav-localization-results">
            <div className="uav-localization-result-header">
              <div>
                <h3>{localization.localization_estimate?.available ? "Geometrically verified image-center estimate" : "Ranked retrieval candidates"}</h3>
                <p>{localization.note}</p>
                <small>Query image #{localization.query_image_id} · {localization.processing_time_seconds.toFixed(1)} sec · Mode: {localization.mode.replaceAll("_", " ")}{localization.gps_assisted_filter ? ` · ${localization.gps_assisted_filter}` : " · EXIF GPS filtering off"}</small>
              </div>
              <button
                type="button"
                className="uav-view-map-button"
                onClick={() => navigate("/map", { state: {
                  localizationCandidates: localization.candidates,
                  localizationMode: localization.mode,
                  localizationEstimate: localization.localization_estimate?.available ? {
                    ...localization.localization_estimate,
                    error_m: localization.evaluation?.error_m ?? null,
                  } : null,
                  datasetGroundTruth: localization.evaluation?.ground_truth_latitude != null && localization.evaluation.ground_truth_longitude != null ? {
                    available: true,
                    latitude: localization.evaluation.ground_truth_latitude,
                    longitude: localization.evaluation.ground_truth_longitude,
                    coordinate_reference_system: "EPSG:4326",
                    coordinate_source: localization.evaluation.ground_truth_source ?? "uav_visloc_dataset_ground_truth",
                  } : null,
                } })}
              >
                <MapPin size={15} /> View candidates on map
              </button>
            </div>
            <div className="localization-estimate-summary" role="status">
              <strong>{localization.localization_estimate?.status?.replaceAll("_", " ") ?? "No reliable image-center estimate"}</strong>
              {localization.localization_estimate?.available
                ? <span>Estimated image center: {localization.localization_estimate.latitude?.toFixed(6)}, {localization.localization_estimate.longitude?.toFixed(6)} · {localization.localization_estimate.selected_candidate_rank ? `selected candidate #${localization.localization_estimate.selected_candidate_rank}` : "candidate consensus"}</span>
                : <span>{localization.localization_estimate?.reason ?? "No candidate passed the geometric quality checks; no predicted coordinate is reported."}</span>}
              {localization.evaluation?.available && <span>Haversine error: {localization.evaluation.error_m?.toFixed(2)} m against dataset ground truth (evaluation only).</span>}
              {localization.evaluation?.reason && <span>{localization.evaluation.reason}</span>}
            </div>
            <div className="uav-localization-query">
              <img src={`${API_BASE_URL}${localization.query_image_url}`} alt="Uploaded drone query" />
              <span>{uploadedQuery?.filename ?? queryFile?.name}</span>
            </div>
            <div className="uav-candidate-grid">
              {localization.candidates.slice(0, 10).map((candidate) => (
                <article className="uav-candidate-card" key={candidate.candidate_patch_id}>
                  <img src={`${API_BASE_URL}${candidate.preview_url}`} alt={`Satellite patch ${candidate.candidate_patch_id}`} loading="lazy" />
                  <div className="uav-candidate-body">
                    <div className="uav-candidate-title"><strong>#{candidate.rank} {candidate.candidate_patch_id}</strong><span>{candidate.parent_satellite_map_id}</span></div>
                    <dl>
                      <div><dt>Cosine similarity</dt><dd>{candidate.similarity_score.toFixed(4)} <small>(ranking score)</small></dd></div>
                      <div><dt>Local matches</dt><dd>{candidate.local_feature_match_count ?? "Not run"}</dd></div>
                      <div><dt>RANSAC inliers</dt><dd>{candidate.ransac_inlier_count ?? "Not run"}</dd></div>
                      <div><dt>Inlier ratio</dt><dd>{candidate.inlier_ratio === null ? "Not available" : `${(candidate.inlier_ratio * 100).toFixed(1)}%`}</dd></div>
                      <div><dt>Median reprojection error</dt><dd>{candidate.estimated_image_center?.median_reprojection_error_px == null ? "Not verified" : `${candidate.estimated_image_center.median_reprojection_error_px.toFixed(2)} px`}</dd></div>
                      <div><dt>Projected image center</dt><dd>{candidate.estimated_image_center?.status === "geometrically_verified" ? `${candidate.estimated_image_center.latitude?.toFixed(6)}, ${candidate.estimated_image_center.longitude?.toFixed(6)}` : candidate.estimated_image_center?.reason ?? "Not verified"}</dd></div>
                      <div><dt>Candidate center (WGS84)</dt><dd>{candidate.latitude.toFixed(6)}, {candidate.longitude.toFixed(6)}</dd></div>
                    </dl>
                    <span className={`uav-verification-status ${candidate.verification_status === "geometric_consistency_passed" ? "is-verified" : ""}`}>
                      {candidate.verification_status.replaceAll("_", " ")}
                    </span>
                  </div>
                </article>
              ))}
            </div>
            <p className="uav-localization-caveat">A projected image-center coordinate is returned only after spatial-coverage, RANSAC, reprojection-error and satellite-coverage checks. Homography assumes a locally planar scene; perspective, terrain relief and scene changes can still reduce accuracy. Only the top five selected candidates receive local-feature matching.</p>
          </div>
        )}
      </section>

      {error && (
        <div className="uav-error" role="alert">
          <strong>Unable to load the dataset</strong>
          <p>{error}</p>
          <p>
            Check that FastAPI is running and that the frontend is
            configured to use the correct API address.
          </p>
        </div>
      )}

      <section className="uav-stats-grid" aria-label="Dataset statistics">
        <article className="uav-stat-card">
          <span className="uav-stat-icon">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">Total records</span>
            <strong>
              {stats ? stats.total_records.toLocaleString() : "—"}
            </strong>
            <small>Imported metadata records</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-green">
            <MapPin size={19} />
          </span>
          <div>
            <span className="uav-stat-label">GPS coordinates</span>
            <strong>
              {stats ? stats.total_records.toLocaleString() : "—"}
            </strong>
            <small>Records with coordinates</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-purple">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">
              Complete orientation
            </span>
            <strong>
              {stats
                ? stats.records_with_complete_orientation.toLocaleString()
                : "—"}
            </strong>
            <small>All four fields available</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-orange">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">
              Incomplete orientation
            </span>
            <strong>
              {stats
                ? stats.records_without_complete_orientation.toLocaleString()
                : "—"}
            </strong>
            <small>One or more fields unavailable</small>
          </div>
        </article>
      </section>

      <section className="uav-data-panel">
        <div className="uav-table-header">
          <div>
            <h2>Image metadata</h2>
            <p>
              Showing up to {PAGE_SIZE} records per page. GPS values
              represent recorded image capture locations.
            </p>
          </div>

          <label className="uav-search">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              placeholder="Filter displayed records..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Filter records on this page"
            />
          </label>
        </div>

        {loading ? (
          <div className="uav-table-state" role="status">
            Loading UAV-VisLoc metadata...
          </div>
        ) : !error && displayedRecords.length === 0 ? (
          <div className="uav-table-state">
            {recordPage?.records.length
              ? "No displayed records match your filter."
              : "No records were returned by the API."}
          </div>
        ) : !error ? (
          <div className="uav-table-scroll">
            <table className="uav-table">
              <thead>
                <tr>
                  <th>Image</th>
                  <th>Capture time</th>
                  <th>Latitude</th>
                  <th>Longitude</th>
                  <th>Height</th>
                  <th>Orientation</th>
                  <th>Details</th>
                </tr>
              </thead>

              <tbody>
                {displayedRecords.map((record) => {
                  const completeOrientation = [
                    record.omega,
                    record.kappa,
                    record.phi1,
                    record.phi2,
                  ].every((value) => value !== null);

                  return (
                    <tr key={record.id}>
                      <td>
                        <div className="uav-filename">
                          {record.filename}
                        </div>
                        <div className="uav-subpath">
                          {record.relative_path}
                        </div>
                      </td>

                      <td>{record.capture_time_raw || "—"}</td>

                      <td className="uav-number">
                        {formatValue(record.latitude, 6)}
                      </td>

                      <td className="uav-number">
                        {formatValue(record.longitude, 6)}
                      </td>

                      <td>{formatValue(record.height)}</td>

                      <td>
                        <span
                          className={
                            completeOrientation
                              ? "uav-status uav-status-complete"
                              : "uav-status uav-status-partial"
                          }
                        >
                          {completeOrientation
                            ? "Complete"
                            : "Partial"}
                        </span>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="uav-view-button"
                          onClick={() => void openRecord(record.id)}
                          disabled={detailLoading}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {detailError && (
          <div className="uav-inline-error" role="alert">
            {detailError}
          </div>
        )}

        <footer className="uav-pagination">
          <span>
            {totalRecords
              ? `Showing ${firstRecord}–${lastRecord} of ${totalRecords.toLocaleString()} records`
              : "No records"}
          </span>

          <div className="uav-pagination-controls">
            <button
              type="button"
              onClick={() => setPage((current) => current - 1)}
              disabled={loading || page <= 1}
              aria-label="Previous page"
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            <span>
              Page {page} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() => setPage((current) => current + 1)}
              disabled={loading || page >= totalPages}
              aria-label="Next page"
            >
              Next
              <ChevronRight size={16} />
            </button>
          </div>
        </footer>
      </section>

      {selectedRecord && (
        <section className="uav-detail-panel">
          <header className="uav-detail-header">
            <div>
              <h2>Record details</h2>
              <p>{selectedRecord.relative_path}</p>
            </div>

            <button
              type="button"
              className="uav-close-button"
              onClick={() => setSelectedRecord(null)}
              aria-label="Close record details"
            >
              <X size={18} />
            </button>
          </header>

          <dl className="uav-detail-grid">
            <div>
              <dt>Filename</dt>
              <dd>{selectedRecord.filename}</dd>
            </div>
            <div>
              <dt>Capture time (source)</dt>
              <dd>{selectedRecord.capture_time_raw || "—"}</dd>
            </div>
            <div>
              <dt>Latitude</dt>
              <dd>{formatValue(selectedRecord.latitude, 6)}</dd>
            </div>
            <div>
              <dt>Longitude</dt>
              <dd>{formatValue(selectedRecord.longitude, 6)}</dd>
            </div>
            <div>
              <dt>Recorded height</dt>
              <dd>{formatValue(selectedRecord.height)}</dd>
            </div>
            <div>
              <dt>Metadata CSV</dt>
              <dd>{selectedRecord.metadata_csv}</dd>
            </div>
            <div>
              <dt>Omega</dt>
              <dd>{formatValue(selectedRecord.omega, 6)}</dd>
            </div>
            <div>
              <dt>Kappa</dt>
              <dd>{formatValue(selectedRecord.kappa, 6)}</dd>
            </div>
            <div>
              <dt>Phi1</dt>
              <dd>{formatValue(selectedRecord.phi1, 6)}</dd>
            </div>
            <div>
              <dt>Phi2</dt>
              <dd>{formatValue(selectedRecord.phi2, 6)}</dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  );
}
