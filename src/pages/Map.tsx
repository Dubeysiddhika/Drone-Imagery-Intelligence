import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import {
  getApiErrorMessage,
  listImages,
  type ImageMetadata,
} from "../services/api";

const imageMarkerIcon = L.divIcon({
  className: "image-map-marker",
  html: "<span></span>",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

type LocatedImage = ImageMetadata & { latitude: number; longitude: number };

function hasValidGps(image: ImageMetadata): image is LocatedImage {
  return image.latitude !== null &&
    image.longitude !== null &&
    Number.isFinite(image.latitude) &&
    Number.isFinite(image.longitude) &&
    image.latitude >= -90 &&
    image.latitude <= 90 &&
    image.longitude >= -180 &&
    image.longitude <= 180;
}

function FitImageMarkers({ images }: { images: LocatedImage[] }) {
  const map = useMap();

  useEffect(() => {
    if (images.length === 1) {
      map.setView([images[0].latitude, images[0].longitude], 12);
      return;
    }
    map.fitBounds(
      L.latLngBounds(images.map((image) => [image.latitude, image.longitude])),
      { padding: [36, 36], maxZoom: 12 },
    );
  }, [images, map]);

  return null;
}

function formatCaptureTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function MapPage() {
  const [images, setImages] = useState<ImageMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    listImages()
      .then((result) => {
        if (active) setImages(result);
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

  const locatedImages = useMemo(() => images.filter(hasValidGps), [images]);
  const imagesWithoutGps = useMemo(
    () => images.filter((image) => !hasValidGps(image)),
    [images],
  );
  const mapCenter = useMemo<[number, number] | null>(() => {
    if (locatedImages.length === 0) return null;
    const coordinates = locatedImages.reduce(
      (total, image) => [
        total[0] + (image.latitude ?? 0),
        total[1] + (image.longitude ?? 0),
      ],
      [0, 0],
    );
    return [
      coordinates[0] / locatedImages.length,
      coordinates[1] / locatedImages.length,
    ];
  }, [locatedImages]);

  return (
    <div className="map-workspace">
      <header className="dashboard-heading">
        <div>
          <p className="dashboard-eyebrow">GEOSPATIAL INTELLIGENCE / IMAGE LOCATIONS</p>
          <h1>Image Capture Map</h1>
          <p>
            Markers show image capture coordinates from EXIF metadata. Object
            boxes are not geographic positions.
          </p>
        </div>
        <div className="map-record-count">
          {locatedImages.length} located · {imagesWithoutGps.length} without GPS
        </div>
      </header>

      {error && <div className="dashboard-inline-error" role="alert">{error}</div>}

      {loading ? (
        <div className="map-empty-state" role="status">Loading image locations…</div>
      ) : locatedImages.length > 0 && mapCenter ? (
        <div className="image-location-map" aria-label="Map of image capture locations">
          <MapContainer
            center={mapCenter}
            zoom={10}
            scrollWheelZoom
            className="leaflet-map"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitImageMarkers images={locatedImages} />
            {locatedImages.map((image) => (
              <Marker
                key={image.image_id}
                position={[image.latitude, image.longitude]}
                icon={imageMarkerIcon}
              >
                <Popup>
                  <div className="map-image-popup">
                    <strong>{image.filename}</strong>
                    <span>Captured: {formatCaptureTime(image.capture_time ?? image.captured_at)}</span>
                    <span>Stored detections: {image.detection_count ?? 0}</span>
                    <Link to={`/analysis?image_id=${image.image_id}`}>
                      Open image analysis
                    </Link>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      ) : (
        <div className="map-empty-state">
          <strong>No images have valid GPS coordinates.</strong>
          <span>Images without GPS are listed below; no locations are inferred.</span>
        </div>
      )}

      <section className="workbench-panel map-unlocated-panel">
        <div className="dashboard-section-heading">
          <div>
            <p className="panel-kicker">METADATA STATUS</p>
            <h2>Images without GPS</h2>
          </div>
          <span className="map-record-count">{imagesWithoutGps.length} images</span>
        </div>
        {imagesWithoutGps.length ? (
          <div className="map-unlocated-list">
            {imagesWithoutGps.map((image) => (
              <div key={image.image_id}>
                <span>{image.filename}</span>
                <small>Capture coordinates unavailable</small>
                <Link to={`/analysis?image_id=${image.image_id}`}>Review image</Link>
              </div>
            ))}
          </div>
        ) : (
          <p className="dashboard-empty-note">
            {images.length === 0 ? "No images have been uploaded." : "All uploaded images have valid GPS coordinates."}
          </p>
        )}
      </section>
      <p className="map-attribution-note">
        Map tiles are provided by OpenStreetMap. Image locations indicate capture
        positions only, not the locations of detected objects.
      </p>
    </div>
  );
}
