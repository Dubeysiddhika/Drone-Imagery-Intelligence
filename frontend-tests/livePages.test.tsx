// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Analytics from "../src/pages/Analytics";
import MapPage from "../src/pages/Map";
import Reports from "../src/pages/Reports";
import Surveys from "../src/pages/Surveys";
import {
  createSurvey,
  getDashboardSummary,
  getImage,
  getImagePreviewUrl,
  getStoredDetections,
  listImages,
  listSurveys,
  type DashboardSummary,
  type DetectionResponse,
  type ImageMetadata,
} from "../src/services/api";

vi.mock("../src/services/api", () => ({
  createSurvey: vi.fn(),
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  getDashboardSummary: vi.fn(),
  getImage: vi.fn(),
  getImagePreviewUrl: vi.fn(() => "http://127.0.0.1:8000/api/images/7/preview"),
  getStoredDetections: vi.fn(),
  listImages: vi.fn(),
  listSurveys: vi.fn(),
}));

const image: ImageMetadata = {
  id: 7,
  image_id: 7,
  filename: "field.jpg",
  latitude: null,
  longitude: null,
  altitude: null,
  capture_time: null,
  camera_make: null,
  camera_model: null,
  width: 1200,
  height: 800,
  exif_available: false,
  detection_count: 1,
  uploaded_at: "2026-11-09T12:00:00",
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
};

describe("live data pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listImages).mockResolvedValue([image]);
    vi.mocked(getDashboardSummary).mockResolvedValue(summary);
    vi.mocked(getImage).mockResolvedValue(image);
    vi.mocked(getStoredDetections).mockResolvedValue(detectionResponse);
    vi.mocked(getImagePreviewUrl).mockReturnValue(
      "http://127.0.0.1:8000/api/images/7/preview",
    );
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
    expect(screen.getByText("field.jpg")).toBeTruthy();
    expect(screen.getByText("Capture coordinates unavailable")).toBeTruthy();
    expect(document.querySelector(".leaflet-map")).toBeNull();
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
