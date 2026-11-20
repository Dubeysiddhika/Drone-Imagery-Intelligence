import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import {
  API_BASE_URL,
  getApiErrorMessage,
  getGeospatialImageCollections,
  listImages,
  listSurveys,
  type GeospatialImage,
  type ImageMetadata,
  type SurveyRecord,
  type UAVVisLocCandidate,
  type UnlocatedGeospatialImage,
} from "../services/api";

const imageMarkerIcon = L.divIcon({
  className: "image-map-marker",
  html: "<span></span>",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});
const candidateMarkerIcon = L.divIcon({
  className: "visloc-candidate-marker",
  html: "<span></span>",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});
const datasetGroundTruthIcon = L.divIcon({
  className: "dataset-ground-truth-marker",
  html: "<span></span>",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});
const predictedEstimateIcon = L.divIcon({
  className: "visloc-predicted-marker",
  html: "<span></span>",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});
function candidateClusterIcon(count: number) {
  return L.divIcon({
    className: "visloc-candidate-cluster",
    html: `<span>${count}</span>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  });
}

function clusterIcon(count: number) {
  return L.divIcon({
    className: "image-map-cluster",
    html: `<span>${count}</span>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
  });
}

function formatCaptureTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

type MapImage = GeospatialImage | UnlocatedGeospatialImage;

function ImageDetails({ image }: { image: MapImage }) {
  const coordinateLabel = image.gps_available && image.latitude !== null && image.longitude !== null
    ? `${image.latitude.toFixed(6)}, ${image.longitude.toFixed(6)}`
    : "Unavailable — no map coordinate assigned";
  return (
    <div className="map-image-popup">
      <strong>{image.filename}</strong>
      <span>GPS: {coordinateLabel}</span>
      <span>Altitude: {image.altitude === null ? "Not available" : `${image.altitude} m`}</span>
      <span>Captured: {formatCaptureTime(image.captured_at)}</span>
      <span>Survey: {image.survey_name ?? (image.survey_id === null ? "Unassigned" : `Survey ${image.survey_id}`)}</span>
      <span>Detections: {image.detection_count}</span>
      <span>
        Classes: {image.detected_classes.length
          ? image.detected_classes.map((item) => `${item.class_name} (${item.count})`).join(", ")
          : "No saved detections"}
      </span>
      <div className="map-image-preview-pair">
        <figure><img src={`${API_BASE_URL}${image.original_image_url}`} alt={`Original preview of ${image.filename}`} loading="lazy" /><figcaption>Original image</figcaption></figure>
        <figure><img src={`${API_BASE_URL}${image.annotated_image_url}`} alt={`Annotated preview of ${image.filename}`} loading="lazy" /><figcaption>YOLO boxes in image pixels</figcaption></figure>
      </div>
      <small>Bounding boxes are image-space annotations, not geographic object positions.</small>
      <Link to={`/analysis?image_id=${image.image_id}`}>Open image analysis</Link>
    </div>
  );
}

function ImagePopup({ image }: { image: GeospatialImage }) {
  return <ImageDetails image={image} />;
}

function FitMapPoints({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 1) {
      map.setView(points[0], 12);
    } else if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 12 });
    }
  }, [points, map]);
  return null;
}

function CandidatePopup({ candidate }: { candidate: UAVVisLocCandidate }) {
  return <div className="map-image-popup">
    <strong>Satellite candidate #{candidate.rank}</strong>
    <span>Satellite tile ID: {candidate.satellite_tile_id}</span>
    <span>Patch center, EPSG:4326: {candidate.latitude.toFixed(6)}, {candidate.longitude.toFixed(6)}</span>
    <span>Cosine similarity: {candidate.similarity_score.toFixed(4)} (ranking only)</span>
    <span>Local matches: {candidate.local_feature_match_count ?? "Not run"} · RANSAC inliers: {candidate.ransac_inlier_count ?? "Not run"}</span>
    <span>Status: {candidate.verification_status.replaceAll("_", " ")}</span>
    <img src={`${API_BASE_URL}${candidate.preview_url}`} alt={`Candidate patch ${candidate.candidate_patch_id}`} loading="lazy" />
    <small>This is a candidate patch center, not a precise drone or object location.</small>
  </div>;
}

function CandidateMarkers({ candidates }: { candidates: UAVVisLocCandidate[] }) {
  const map = useMap();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const update = () => setRevision((value) => value + 1);
    map.on("zoomend moveend", update);
    return () => { map.off("zoomend moveend", update); };
  }, [map]);
  const groups = useMemo(() => {
    const buckets = new Map<string, UAVVisLocCandidate[]>();
    for (const candidate of candidates) {
      const point = map.project([candidate.latitude, candidate.longitude], map.getZoom());
      const key = `${Math.floor(point.x / 64)}:${Math.floor(point.y / 64)}`;
      buckets.set(key, [...(buckets.get(key) ?? []), candidate]);
    }
    return [...buckets.values()];
    // Leaflet zoom/pan events update screen-space cluster membership.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidates, map, revision]);
  return <>
    {groups.map((group) => {
      if (group.length === 1) {
        const candidate = group[0];
        return <Marker key={candidate.candidate_patch_id} position={[candidate.latitude, candidate.longitude]} icon={candidateMarkerIcon}>
          <Popup><CandidatePopup candidate={candidate} /></Popup>
        </Marker>;
      }
      const center: [number, number] = [
        group.reduce((sum, candidate) => sum + candidate.latitude, 0) / group.length,
        group.reduce((sum, candidate) => sum + candidate.longitude, 0) / group.length,
      ];
      return <Marker key={group.map((candidate) => candidate.candidate_patch_id).join("-")} position={center} icon={candidateClusterIcon(group.length)}>
        <Popup><div className="map-cluster-popup">
          <strong>{group.length} nearby candidate patch centers</strong>
          {group.map((candidate) => <CandidatePopup key={candidate.candidate_patch_id} candidate={candidate} />)}
        </div></Popup>
      </Marker>;
    })}
  </>;
}

function ClusteredImageMarkers({ images }: { images: GeospatialImage[] }) {
  const map = useMap();
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const update = () => setRevision((value) => value + 1);
    map.on("zoomend moveend", update);
    return () => { map.off("zoomend moveend", update); };
  }, [map]);

  const groups = useMemo(() => {
    const buckets = new Map<string, GeospatialImage[]>();
    const zoom = map.getZoom();
    for (const image of images) {
      const point = map.project([image.latitude, image.longitude], zoom);
      const key = `${Math.floor(point.x / 64)}:${Math.floor(point.y / 64)}`;
      buckets.set(key, [...(buckets.get(key) ?? []), image]);
    }
    return [...buckets.values()];
  // revision tracks Leaflet zoom and pan changes which alter screen-space clusters.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [images, map, revision]);

  return <>
    {groups.map((group) => {
      if (group.length === 1) {
        const image = group[0];
        return (
          <Marker key={image.image_id} position={[image.latitude, image.longitude]} icon={imageMarkerIcon}>
            <Popup><ImagePopup image={image} /></Popup>
          </Marker>
        );
      }
      const center: [number, number] = [
        group.reduce((sum, image) => sum + image.latitude, 0) / group.length,
        group.reduce((sum, image) => sum + image.longitude, 0) / group.length,
      ];
      return (
        <Marker key={group.map((image) => image.image_id).join("-")} position={center} icon={clusterIcon(group.length)}>
          <Popup>
            <div className="map-cluster-popup">
              <strong>{group.length} image capture points in this cluster</strong>
              {group.map((image) => <ImagePopup key={image.image_id} image={image} />)}
            </div>
          </Popup>
        </Marker>
      );
    })}
  </>;
}

export default function MapPage() {
  const location = useLocation();
  const localizationCandidates = (
    (location.state as { localizationCandidates?: UAVVisLocCandidate[] } | null)
      ?.localizationCandidates ?? []
  );
  const localizationMode = (
    location.state as { localizationMode?: string } | null
  )?.localizationMode ?? "gps_free";
  const datasetGroundTruth = (
    location.state as { datasetGroundTruth?: { available: boolean; latitude: number | null; longitude: number | null; coordinate_source: string | null } | null } | null
  )?.datasetGroundTruth;
  const localizationEstimate = (
    location.state as { localizationEstimate?: { available: boolean; latitude: number | null; longitude: number | null; status: string; coordinate_source?: string | null; error_m?: number | null } | null } | null
  )?.localizationEstimate;
  const hasLocalizationEstimate = Boolean(localizationEstimate?.available
    && typeof localizationEstimate.latitude === "number"
    && typeof localizationEstimate.longitude === "number");
  const hasDatasetGroundTruth = Boolean(
    datasetGroundTruth?.available
    && typeof datasetGroundTruth.latitude === "number"
    && typeof datasetGroundTruth.longitude === "number",
  );
  const [mapImages, setMapImages] = useState<GeospatialImage[]>([]);
  const [allImages, setAllImages] = useState<ImageMetadata[]>([]);
  const [unlocatedImages, setUnlocatedImages] = useState<UnlocatedGeospatialImage[]>([]);
  const [surveys, setSurveys] = useState<SurveyRecord[]>([]);
  const [classOptions, setClassOptions] = useState<string[]>([]);
  const [surveyFilter, setSurveyFilter] = useState("");
  const [imageFilter, setImageFilter] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [referenceLoading, setReferenceLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([listImages(), listSurveys()])
      .then(([images, surveyRecords]) => {
        if (!active) return;
        setAllImages(images);
        setSurveys(surveyRecords);
      })
      .catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError));
      }).finally(() => {
        if (active) setReferenceLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    const loadLocations = (showLoading: boolean) => {
      if (showLoading) setLoading(true);
      setError("");
      void getGeospatialImageCollections({
        ...(surveyFilter && surveyFilter !== "unassigned" ? { survey_id: Number(surveyFilter) } : {}),
        ...(imageFilter ? { image_id: Number(imageFilter) } : {}),
        ...(classFilter ? { class_name: classFilter } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      }).then((response) => {
        if (!active) return;
        const located = surveyFilter === "unassigned"
          ? response.located_images.filter((image) => image.survey_id === null)
          : response.located_images;
        const unlocated = surveyFilter === "unassigned"
          ? response.unlocated_images.filter((image) => image.survey_id === null)
          : response.unlocated_images;
        setMapImages(located);
        setUnlocatedImages(unlocated);
        setClassOptions(response.available_classes);
      }).catch((requestError: unknown) => {
        if (active) setError(getApiErrorMessage(requestError));
      }).finally(() => {
        if (active) {
          setLoading(false);
          setHasLoaded(true);
        }
      });
    };
    loadLocations(!hasLoaded);
    const timer = window.setInterval(() => loadLocations(false), 30_000);
    const refreshOnFocus = () => loadLocations(false);
    window.addEventListener("focus", refreshOnFocus);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshOnFocus);
    };
  }, [surveyFilter, imageFilter, classFilter, dateFrom, dateTo, refreshKey]);

  const filteredLocated = mapImages;
  const withoutGps = unlocatedImages;
  const refreshMap = () => setRefreshKey((value) => value + 1);

  return (
    <div className="map-workspace">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">GEOSPATIAL INTELLIGENCE / IMAGE LOCATIONS</p>
          <h1>Image Capture Map</h1>
          <p>Markers show capture positions from image GPS. Detection boxes remain pixel coordinates; individual object locations are not inferred.</p>
        </div>
        <div className="map-record-count">{filteredLocated.length} located · {withoutGps.length} without GPS</div>
      </header>
      <div className="map-refresh-row"><button type="button" onClick={refreshMap}>Refresh locations</button></div>

      <section className="workbench-panel map-filter-panel" aria-label="Map filters">
        <label>Survey
          <select aria-label="Filter by survey" value={surveyFilter} onChange={(event) => setSurveyFilter(event.currentTarget.value)}>
            <option value="">All surveys</option>
            {surveys.map((survey) => <option key={survey.id} value={survey.id}>{survey.name}</option>)}
            <option value="unassigned">Unassigned</option>
          </select>
        </label>
        <label>Image
          <select aria-label="Filter by image" value={imageFilter} onChange={(event) => setImageFilter(event.currentTarget.value)}>
            <option value="">All images</option>
            {allImages.map((image) => <option key={image.image_id} value={image.image_id}>{image.filename}</option>)}
          </select>
        </label>
        <label>Detected class
          <select aria-label="Filter by detected class" value={classFilter} onChange={(event) => setClassFilter(event.currentTarget.value)}>
            <option value="">All classes</option>
            {classOptions.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label>Uploaded from<input aria-label="Map uploaded from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.currentTarget.value)} /></label>
        <label>Uploaded through<input aria-label="Map uploaded through" type="date" value={dateTo} onChange={(event) => setDateTo(event.currentTarget.value)} /></label>
      </section>

      {error && <div className="dashboard-inline-error" role="alert">{error}<button type="button" onClick={refreshMap}>Retry</button></div>}

      {loading || referenceLoading ? (
        <div className="map-empty-state" role="status">Loading image locations…</div>
      ) : filteredLocated.length || localizationCandidates.length || hasDatasetGroundTruth || hasLocalizationEstimate ? (
        <div className="image-location-map" aria-label="Map of image capture locations">
          <MapContainer
            center={filteredLocated.length
              ? [filteredLocated[0].latitude, filteredLocated[0].longitude]
              : localizationCandidates.length
                ? [localizationCandidates[0].latitude, localizationCandidates[0].longitude]
                : hasLocalizationEstimate
                  ? [localizationEstimate!.latitude!, localizationEstimate!.longitude!]
                : [datasetGroundTruth!.latitude!, datasetGroundTruth!.longitude!]}
            zoom={10}
            scrollWheelZoom
            className="leaflet-map"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitMapPoints points={[
              ...filteredLocated.map((image) => [image.latitude, image.longitude] as [number, number]),
              ...localizationCandidates.map((candidate) => [candidate.latitude, candidate.longitude] as [number, number]),
              ...(hasLocalizationEstimate ? [[localizationEstimate!.latitude!, localizationEstimate!.longitude!] as [number, number]] : []),
              ...(hasDatasetGroundTruth ? [[datasetGroundTruth!.latitude!, datasetGroundTruth!.longitude!] as [number, number]] : []),
            ]} />
            <ClusteredImageMarkers images={filteredLocated} />
            <CandidateMarkers candidates={localizationCandidates} />
            {hasLocalizationEstimate && <Marker position={[localizationEstimate!.latitude!, localizationEstimate!.longitude!]} icon={predictedEstimateIcon}>
              <Popup><strong>Geometrically estimated UAV image center</strong><br />Latitude {localizationEstimate!.latitude!.toFixed(6)} · longitude {localizationEstimate!.longitude!.toFixed(6)}<br />{localizationEstimate!.status.replaceAll("_", " ")} · {localizationEstimate!.coordinate_source}</Popup>
            </Marker>}
            {hasDatasetGroundTruth && <Marker position={[datasetGroundTruth!.latitude!, datasetGroundTruth!.longitude!]} icon={datasetGroundTruthIcon}>
              <Popup><strong>UAV-VisLoc dataset ground truth</strong><br />Latitude {datasetGroundTruth!.latitude!.toFixed(6)} · longitude {datasetGroundTruth!.longitude!.toFixed(6)}<br />EPSG:4326 · {datasetGroundTruth!.coordinate_source}</Popup>
            </Marker>}
          </MapContainer>
        </div>
      ) : (
        <div className="map-empty-state">
          <strong>{withoutGps.length > 0 && !surveyFilter && !imageFilter && !classFilter && !dateFrom && !dateTo
            ? "No images have valid GPS coordinates."
            : "No located images match these filters."}</strong>
          <span>{allImages.length === 0
            ? "Upload drone imagery to begin."
            : "Images without valid GPS remain listed below and are never assigned map coordinates."}</span>
        </div>
      )}

      <section className="workbench-panel map-legend-panel" aria-label="Map legend">
        <strong>Map legend</strong>
        <span><i className="map-legend-image" /> Image capture point (EXIF GPS)</span>
        <span><i className="map-legend-cluster">3</i> Cluster of nearby image points</span>
        {localizationCandidates.length > 0 && <span><i className="map-legend-candidate" /> UAV-VisLoc satellite candidate patch center</span>}
        {hasLocalizationEstimate && <span><i className="map-legend-predicted" /> Geometrically estimated UAV image center</span>}
        {hasDatasetGroundTruth && <span><i className="map-legend-ground-truth" /> UAV-VisLoc dataset ground truth (evaluation)</span>}
        <span>Detected objects are summarized in popups; no object-coordinate markers are available.</span>
      </section>
      {localizationCandidates.length > 0 && (
        <p className="map-candidate-notice" role="status">
          Showing {localizationCandidates.length} satellite candidate patch centers from the last {localizationMode.replaceAll("_", " ")} UAV-VisLoc run. Candidate centers are separate from the geometrically estimated image-center marker and dataset ground truth.
        </p>
      )}

      <section className="workbench-panel map-unlocated-panel">
        <div className="dashboard-section-heading">
          <div><p className="panel-kicker">METADATA STATUS</p><h2>Images without GPS</h2></div>
          <span className="map-record-count">{withoutGps.length} images</span>
        </div>
        {withoutGps.length ? (
          <div className="map-unlocated-list">
            {withoutGps.map((image) => (
              <div className="map-unlocated-card" key={image.image_id}>
                <div className="map-unlocated-heading">
                  <span>{image.filename}</span>
                  <small>Capture coordinates unavailable</small>
                  <Link to={`/analysis?image_id=${image.image_id}`}>Open analysis</Link>
                </div>
                <details>
                  <summary>Image details and previews</summary>
                  <ImageDetails image={image} />
                </details>
              </div>
            ))}
          </div>
        ) : (
          <p className="dashboard-empty-note">{allImages.length === 0 ? "No images have been uploaded." : "No unlocated images match the current filters."}</p>
        )}
      </section>
      <p className="map-attribution-note">Map tiles are provided by OpenStreetMap. Image locations indicate capture positions only, not detected object locations.</p>
    </div>
  );
}
