// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Analytics from "../src/pages/Analytics";
import Dashboard from "../src/pages/Dashboard";
import MapPage from "../src/pages/Map";
import Reports from "../src/pages/Reports";
import Surveys from "../src/pages/Surveys";
import UAVVisLocPage from "../src/pages/UAVVisLoc";
import {
  createSurvey,
  getGeospatialImageCollections,
  getDashboardSummary,
  getImage,
  getImagePreviewUrl,
  getStoredDetections,
  getUAVVisLocStats,
  listGeospatialImages,
  listImages,
  listSurveys,
  listUAVVisLocRecords,
  runUAVVisLocLocalization,
  uploadImage,
  type DashboardSummary,
  type DetectionResponse,
  type ImageMetadata,
  type GeospatialImage,
  type GeospatialImageCollections,
  type UnlocatedGeospatialImage,
  type UAVVisLocLocalizationResponse,
} from "../src/services/api";

vi.mock("react-leaflet", async () => {
  const React = await import("react");
  const fakeMap = {
    on: vi.fn(),
    off: vi.fn(),
    getZoom: () => 10,
    project: ([lat, lng]: [number, number]) => ({ x: lng * 100, y: lat * 100 }),
    setView: vi.fn(),
    fitBounds: vi.fn(),
  };
  return {
    MapContainer: ({ children }: { children: React.ReactNode }) => React.createElement("div", { className: "leaflet-map" }, children),
    Marker: ({ children }: { children: React.ReactNode }) => React.createElement("div", { "data-testid": "map-marker" }, children),
    Popup: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
    TileLayer: () => null,
    useMap: () => fakeMap,
  };
});

vi.mock("../src/services/api", () => ({
  API_BASE_URL: "http://127.0.0.1:8000",
  createSurvey: vi.fn(),
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  getDashboardSummary: vi.fn(),
  getGeospatialImageCollections: vi.fn(),
  getAvailableModels: vi.fn().mockResolvedValue([]),
  getImage: vi.fn(),
  getImagePreviewUrl: vi.fn(() => "http://127.0.0.1:8000/api/images/7/preview"),
  getStoredDetections: vi.fn(),
  getUAVVisLocStats: vi.fn(),
  listImages: vi.fn(),
  listGeospatialImages: vi.fn(),
  listSurveys: vi.fn(),
  listUAVVisLocRecords: vi.fn(),
  runUAVVisLocLocalization: vi.fn(),
  uploadImage: vi.fn(),
}));

const image: ImageMetadata = {
  id: 7,
  image_id: 7,
  filename: "field.jpg",
  latitude: null,
  longitude: null,
  gps_available: false,
  altitude: null,
  capture_time: null,
  camera_make: null,
  camera_model: null,
  width: 1200,
  height: 800,
  orientation: null,
  focal_length: null,
  survey_id: null,
  exif_available: false,
  detection_count: 1,
  uploaded_at: "2026-11-09T12:00:00",
};

const unlocatedMapImage: UnlocatedGeospatialImage = {
  image_id: image.image_id,
  survey_id: image.survey_id,
  survey_name: null,
  gps_available: false,
  latitude: null,
  longitude: null,
  altitude: null,
  filename: image.filename,
  captured_at: null,
  uploaded_at: image.uploaded_at ?? null,
  detection_count: 1,
  detected_classes: [{ class_name: "car", count: 1 }],
  original_image_url: `/api/images/${image.image_id}/preview`,
  annotated_image_url: `/api/images/${image.image_id}/annotated`,
  coordinate_meaning: "image_capture_point",
  coordinate_reference_system: "EPSG:4326",
};

const emptyGeospatialCollections: GeospatialImageCollections = {
  total: 0,
  located_total: 0,
  images: [],
  located_images: [],
  unlocated_images: [unlocatedMapImage],
  unlocated_total: 1,
  available_classes: ["car"],
};

const detectionResponse: DetectionResponse = {
  image_id: 7,
  model_name: "YOLO11n VisDrone10",
  model_version: "visdrone10_yolo11n",
  detection_count: 1,
  detections: [{
    id: 11,
    class_id: 3,
    class_name: "car",
    confidence: 0.9,
    model_name: "YOLO11n VisDrone10",
    model_version: "visdrone10_yolo11n",
    bbox: { x1: 10, y1: 20, x2: 100, y2: 200 },
  }],
};

const summary: DashboardSummary = {
  total_images: 1,
  total_surveys: 1,
  total_detections: 1,
  pedestrian_count: 0,
  vehicle_count: 1,
  average_confidence: 0.9,
  class_counts: [{ class_name: "car", count: 1 }],
  category_definitions: {
    pedestrians: ["pedestrian", "people"],
    vehicles: ["car", "van", "truck", "tricycle", "awning-tricycle", "bus", "motor", "vehicle"],
  },
  model_name: "YOLO11n VisDrone10",
  model_version: "visdrone10_yolo11n",
  recent_images: [image],
  recent_activity: [],
  confidence_distribution: [{ range: "90-100%", count: 1 }],
  gps_statistics: { available_images: 0, missing_images: 1, availability_rate: 0 },
  detection_processing: { processed_images: 1, pending_images: 0 },
  processing_time: {
    detection: { completed_runs: 1, mean_seconds: 1.2, min_seconds: 1.2, max_seconds: 1.2 },
    localization: { completed_runs: 0, mean_seconds: null, min_seconds: null, max_seconds: null },
  },
  localization_statistics: {
    total_runs: 0, completed_runs: 0, failed_or_incomplete_runs: 0,
    candidate_patches_returned: 0, verified_candidates: 0,
  },
  survey_statistics: [{ survey_id: 2, survey_name: "Field survey", image_count: 1, detection_count: 1, gps_image_count: 0 }],
  recent_processing_activity: [],
};

describe("live data pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:visloc-query") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.mocked(listImages).mockResolvedValue([image]);
    vi.mocked(getUAVVisLocStats).mockResolvedValue({
      dataset: "UAV-VisLoc",
      total_records: 0,
      records_with_complete_orientation: 0,
      records_without_complete_orientation: 0,
    });
    vi.mocked(listUAVVisLocRecords).mockResolvedValue({ total: 0, skip: 0, limit: 25, records: [] });
    vi.mocked(listGeospatialImages).mockResolvedValue([]);
    vi.mocked(getGeospatialImageCollections).mockResolvedValue(emptyGeospatialCollections);
    vi.mocked(getDashboardSummary).mockResolvedValue(summary);
    vi.mocked(getImage).mockResolvedValue(image);
    vi.mocked(getStoredDetections).mockResolvedValue(detectionResponse);
    vi.mocked(getImagePreviewUrl).mockReturnValue(
      "http://127.0.0.1:8000/api/images/7/preview",
    );
    vi.mocked(uploadImage).mockResolvedValue(image);
    vi.mocked(runUAVVisLocLocalization).mockResolvedValue({
      query_image_id: 7,
      query_image_url: "/api/images/7/preview",
      mode: "gps_free",
      gps_assisted_filter: null,
      localization_status: "candidate_retrieval_only",
      precise_localization_claimed: false,
      note: "Similarity ranks are not a localization fix.",
      processing_time_seconds: 12.3,
      retrieval_configuration: {
        query_preprocessing_px: 280,
        initial_retrieval_top_k: 50,
        one_ring_seed_count: 5,
        candidate_budget: 75,
        local_matching_shortlist: 5,
      },
      candidates: [{
        rank: 1,
        candidate_patch_id: "01_patch_a",
        satellite_tile_id: "01_patch_a",
        parent_satellite_map_id: "satellite01",
        similarity_score: 0.8,
        local_feature_match_count: 8,
        ransac_inlier_count: 4,
        inlier_ratio: 0.5,
        verification_status: "geometric_consistency_passed",
        latitude: 29.7,
        longitude: 115.97,
        coordinate_reference_system: "EPSG:4326",
        satellite_footprint: { type: "Polygon", coordinates: [[[115.9, 29.7], [116, 29.7], [116, 29.8], [115.9, 29.7]]] },
        preview_url: "/api/uav-visloc/candidates/01_patch_a/preview",
      }],
    } satisfies UAVVisLocLocalizationResponse);
    vi.mocked(listSurveys).mockResolvedValue([{
      id: 2,
      name: "Field survey",
      description: "North field",
      created_at: "2026-11-09T12:00:00",
    }]);
    vi.mocked(createSurvey).mockResolvedValue({
      id: 3,
      name: "New survey",
      description: "",
      created_at: "2026-11-09T12:00:00",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows database-backed dashboard summaries, processing status, and survey filters", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText("Drone Imagery Intelligence")).toBeTruthy();
    expect(screen.getByText("GPS-tagged Images")).toBeTruthy();
    expect(screen.getByText(/1 processed/)).toBeTruthy();
    expect(screen.getByText(/UAV-VISLOC/i)).toBeTruthy();
    expect(screen.getAllByRole("option", { name: "Field survey" }).length).toBeGreaterThan(0);
    expect(vi.mocked(getDashboardSummary)).toHaveBeenCalledWith({});
  });

  it("renders persisted analytics instead of demo statistics", async () => {
    render(<Analytics />);

    await screen.findByText("Objects by class");
    expect(screen.getAllByText("1", { selector: "strong" }).length).toBeGreaterThan(0);
    expect(screen.getByText("YOLO11n VisDrone10 · visdrone10_yolo11n")).toBeTruthy();
    expect(screen.queryByText("91.8%")).toBeNull();
  });

  it("shows GPS-missing images separately and does not invent map markers", async () => {
    render(
      <MemoryRouter>
        <MapPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("No images have valid GPS coordinates.")).toBeTruthy();
    expect(screen.getAllByText("field.jpg").length).toBeGreaterThan(0);
    expect(screen.getByText("Capture coordinates unavailable")).toBeTruthy();
    expect(document.querySelector(".leaflet-map")).toBeNull();
    fireEvent.click(screen.getByText("Image details and previews"));
    expect(screen.getByText("GPS: Unavailable — no map coordinate assigned")).toBeTruthy();
    expect(screen.getByAltText("Original preview of field.jpg")).toBeTruthy();
    expect(screen.getByAltText("Annotated preview of field.jpg")).toBeTruthy();
  });

  it("plots GPS image points, summarizes object classes, filters, and previews annotations", async () => {
    const located: GeospatialImage[] = [
      {
        image_id: 21, survey_id: 2, survey_name: "North field", gps_available: true,
        latitude: 37.5, longitude: -122.25, altitude: 82.4,
        filename: "north-a.jpg", captured_at: "2026-11-10T10:00:00", uploaded_at: "2026-11-10T10:05:00",
        detection_count: 2,
        detected_classes: [{ class_name: "car", count: 1 }, { class_name: "pedestrian", count: 1 }],
        original_image_url: "/api/images/21/preview",
        annotated_image_url: "/api/images/21/annotated", coordinate_meaning: "image_capture_point",
        coordinate_reference_system: "EPSG:4326",
      },
      {
        image_id: 22, survey_id: 2, survey_name: "North field", gps_available: true,
        latitude: 37.5001, longitude: -122.2501, altitude: null,
        filename: "north-b.jpg", captured_at: null, uploaded_at: "2026-11-11T10:05:00", detection_count: 1,
        detected_classes: [{ class_name: "car", count: 1 }],
        original_image_url: "/api/images/22/preview",
        annotated_image_url: "/api/images/22/annotated", coordinate_meaning: "image_capture_point",
        coordinate_reference_system: "EPSG:4326",
      },
    ];
    const missingImage: UnlocatedGeospatialImage = {
      ...unlocatedMapImage, image_id: 23, survey_id: 2, survey_name: "North field",
      filename: "no-gps.jpg", original_image_url: "/api/images/23/preview",
      annotated_image_url: "/api/images/23/annotated",
    };
    vi.mocked(getGeospatialImageCollections).mockImplementation(async (filters = {}) => {
      const filteredLocated = filters.class_name
        ? located.filter((item) => item.detected_classes.some((entry) => entry.class_name === filters.class_name))
        : located;
      const unlocated = filters.class_name === "pedestrian" ? [] : [missingImage];
      return {
        total: filteredLocated.length, located_total: filteredLocated.length,
        images: filteredLocated, located_images: filteredLocated,
        unlocated_images: unlocated, unlocated_total: unlocated.length,
        available_classes: ["car", "pedestrian"],
      };
    });
    vi.mocked(listImages).mockResolvedValue([
      image, { ...image, image_id: 23, id: 23, filename: "no-gps.jpg" },
    ]);

    render(<MemoryRouter><MapPage /></MemoryRouter>);

    expect(await screen.findByText("2 located · 1 without GPS")).toBeTruthy();
    expect(screen.getAllByText("no-gps.jpg").length).toBeGreaterThan(0);
    expect(screen.getByText((text) => text.includes("car (1), pedestrian (1)"))).toBeTruthy();
    expect(screen.getByText(/GPS: 37\.500000, -122\.250000/)).toBeTruthy();
    expect(screen.getByText("Altitude: 82.4 m")).toBeTruthy();
    expect(screen.getAllByText("Survey: North field").length).toBeGreaterThan(0);
    expect(screen.getByAltText("Original preview of north-a.jpg").getAttribute("src"))
      .toBe("http://127.0.0.1:8000/api/images/21/preview");
    expect(screen.getByAltText("Annotated preview of north-a.jpg").getAttribute("src"))
      .toBe("http://127.0.0.1:8000/api/images/21/annotated");
    expect(screen.getAllByTestId("map-marker")).toHaveLength(1); // nearby points cluster

    fireEvent.change(screen.getByLabelText("Filter by detected class"), { target: { value: "pedestrian" } });
    await waitFor(() => expect(screen.getAllByTestId("map-marker")).toHaveLength(1));
    expect(screen.getByText("1 located · 0 without GPS")).toBeTruthy();
    expect(getGeospatialImageCollections).toHaveBeenLastCalledWith({ class_name: "pedestrian" });
    expect(screen.getByText(/no object-coordinate markers are available/i)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Map uploaded from"), { target: { value: "2026-11-10" } });
    await waitFor(() => expect(getGeospatialImageCollections).toHaveBeenLastCalledWith({
      class_name: "pedestrian", date_from: "2026-11-10",
    }));
    fireEvent.change(screen.getByLabelText("Filter by survey"), { target: { value: "2" } });
    await waitFor(() => expect(getGeospatialImageCollections).toHaveBeenLastCalledWith({
      survey_id: 2, class_name: "pedestrian", date_from: "2026-11-10",
    }));
  });

  it("maps dataset ground truth and predicted estimates with separate markers", async () => {
    vi.mocked(listImages).mockResolvedValue([]);
    vi.mocked(getGeospatialImageCollections).mockResolvedValue({
      total: 0, located_total: 0, images: [], located_images: [],
      unlocated_images: [], unlocated_total: 0, available_classes: [],
    });
    render(<MemoryRouter initialEntries={[{
      pathname: "/map",
      state: {
        localizationCandidates: [],
        datasetGroundTruth: {
          available: true, latitude: 29.7, longitude: 115.97,
          coordinate_reference_system: "EPSG:4326",
          coordinate_source: "uav_visloc_dataset_ground_truth",
        },
        localizationEstimate: {
          available: true, latitude: 29.7001, longitude: 115.9701,
          status: "single_verified_candidate",
          coordinate_source: "ransac_verified_query_to_satellite_homography",
        },
      },
    }]}><MapPage /></MemoryRouter>);

    expect(await screen.findByText("UAV-VisLoc dataset ground truth")).toBeTruthy();
    expect(screen.getAllByTestId("map-marker")).toHaveLength(2);
    expect(screen.getByText(/UAV-VisLoc dataset ground truth \(evaluation\)/)).toBeTruthy();
    expect(screen.getAllByText(/Geometrically estimated UAV image center/).length).toBeGreaterThan(0);
  });

  it("uploads one drone query and displays ranked localization evidence", async () => {
    render(<MemoryRouter><UAVVisLocPage /></MemoryRouter>);
    await screen.findByRole("option", { name: /field.jpg/ });
    const query = new File(["drone image"], "query.jpg", { type: "image/jpeg" });
    fireEvent.change(document.getElementById("uav-query-image") as HTMLInputElement, { target: { files: [query] } });
    fireEvent.click(screen.getByRole("button", { name: "Start localization" }));

    expect(await screen.findByText(/Ranked retrieval candidates/)).toBeTruthy();
    expect(screen.getByText(/01_patch_a/)).toBeTruthy();
    expect(screen.getByText("0.8000", { exact: false })).toBeTruthy();
    expect(screen.getByText("geometric consistency passed")).toBeTruthy();
    expect(screen.getByRole("button", { name: /View candidates on map/ })).toBeTruthy();
    expect(runUAVVisLocLocalization).toHaveBeenCalledWith(7, "gps_free");
  });

  it("offers existing-image selection and refuses GPS-assisted mode without valid image GPS", async () => {
    render(<MemoryRouter><UAVVisLocPage /></MemoryRouter>);
    const imageSelect = await screen.findByLabelText("Select uploaded drone image");
    fireEvent.change(imageSelect, { target: { value: "7" } });
    expect(screen.getByText(/No valid GPS metadata/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Localization mode"), { target: { value: "gps_assisted" } });
    fireEvent.click(screen.getByRole("button", { name: "Start localization" }));
    expect(await screen.findByText(/requires valid latitude and longitude/i)).toBeTruthy();
    expect(runUAVVisLocLocalization).not.toHaveBeenCalled();
  });

  it("builds an image report from stored metadata and detections", async () => {
    render(<Reports />);

    fireEvent.change(await screen.findByLabelText("Analyzed image"), {
      target: { value: "7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Build report" }));

    expect(await screen.findByText("Image Detection Report")).toBeTruthy();
    expect(screen.getAllByText("YOLO11n VisDrone10").length).toBeGreaterThan(0);
    expect(screen.getAllByText("car").length).toBeGreaterThan(0);
    expect(screen.getByText("10.00")).toBeTruthy();
    expect(getStoredDetections).toHaveBeenCalledWith(7);
  });

  it("lists stored surveys and submits a real create request", async () => {
    render(<Surveys />);

    expect(await screen.findByText("Field survey")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Survey name"), {
      target: { value: "New survey" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create survey" }));

    await waitFor(() => {
      expect(createSurvey).toHaveBeenCalledWith("New survey", "");
    });
    expect(await screen.findByText("Survey created.")).toBeTruthy();
  });
});
