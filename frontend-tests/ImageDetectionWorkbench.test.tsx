// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import ImageDetectionWorkbench from "../src/components/dashboard/ImageDetectionWorkbench";
import {
  runDetection,
  uploadImage,
  getAvailableModels,
  getImage,
  getImageIntelligence,
  getImagePreviewUrl,
  getStoredDetections,
  listImages,
  listSurveys,
  processImageIntelligence,
  type DetectionResponse,
  type ImageMetadata,
  type ImageIntelligenceResponse,
} from "../src/services/api";

vi.mock("../src/services/api", () => ({
  API_BASE_URL: "http://127.0.0.1:8000",
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  runDetection: vi.fn(),
  uploadImage: vi.fn(),
  getAvailableModels: vi.fn(),
  getImage: vi.fn(),
  getImageIntelligence: vi.fn(),
  getImagePreviewUrl: vi.fn(),
  getStoredDetections: vi.fn(),
  listImages: vi.fn(),
  listSurveys: vi.fn(),
  processImageIntelligence: vi.fn(),
}));

const uploadedImage: ImageMetadata = {
  image_id: 42,
  id: 42,
  filename: "drone.png",
  latitude: null,
  longitude: null,
  gps_available: false,
  altitude: null,
  capture_time: null,
  camera_make: null,
  camera_model: null,
  width: 640,
  height: 480,
  orientation: null,
  focal_length: null,
  survey_id: null,
  exif_available: false,
};

const baselineResponse: DetectionResponse = {
  image_id: 42,
  model_name: "YOLO11n",
  model_version: "drone_person_vehicle",
  classes: ["person", "vehicle"],
  coordinate_system: "pixel_xyxy",
  detection_count: 1,
  detections: [
    {
      id: 1,
      class_id: 1,
      class_name: "vehicle",
      confidence: 0.91,
      bbox: { x1: 20, y1: 30, x2: 120, y2: 130 },
    },
  ],
};

const visdrone10Response: DetectionResponse = {
  image_id: 42,
  model_name: "YOLO11n VisDrone10",
  model_version: "visdrone10_yolo11n",
  classes: [
    "pedestrian",
    "people",
    "bicycle",
    "car",
    "van",
    "truck",
    "tricycle",
    "awning-tricycle",
    "bus",
    "motor",
  ],
  coordinate_system: "pixel_xyxy",
  detection_count: 1,
  detections: [
    {
      id: 9,
      class_id: 7,
      class_name: "awning-tricycle",
      confidence: 0.875,
      bbox: { x1: 30.5, y1: 40, x2: 180, y2: 210 },
    },
  ],
};

const intelligenceResponse: ImageIntelligenceResponse = {
  image: {
    image_id: 42, original_filename: "drone.png", file_format: "PNG", file_size_bytes: 200,
    width: 640, height: 480, exif_available: false, camera_make: null, camera_model: null,
    focal_length_mm: null, orientation: null, capture_time: null,
    exif_gps: { available: false, latitude: null, longitude: null, altitude_m: null, coordinate_source: null, coordinate_reference_system: null },
    survey_id: null,
  },
  dataset_identity: { status: "not_matched", method: null, confidence: null, flight_sequence: null, dataset_relative_path: null, metadata_source_csv: null },
  dataset_metadata: null,
  geospatial: {
    exif_coordinate: { available: false, latitude: null, longitude: null, altitude_m: null, coordinate_source: null, coordinate_reference_system: null },
    dataset_ground_truth: { available: false, latitude: null, longitude: null, coordinate_reference_system: null, coordinate_source: null },
    predicted_uav_coordinate: { available: false, latitude: null, longitude: null, coordinate_source: null, reason: "Candidate only" },
    satellite_candidate_region_rank_for_ground_truth_map: null,
    satellite_candidate_center_offsets_from_ground_truth: [], candidate_offsets_are_predictions: false,
    coordinate_reference_system: "EPSG:4326",
  },
  detection: { status: "completed", count: 1, per_class_counts: [{ class_name: "awning-tricycle", count: 1 }], coordinate_system: "source_image_pixel_xyxy", annotated_image_url: "/api/images/42/annotated", original_image_url: "/api/images/42/preview", detections: visdrone10Response.detections, note: "Image coordinates only" },
  localization: { status: "not_applicable", message: "Not a dataset image", candidates: [] },
  processing: { runs: [] },
  detection_run_response: visdrone10Response,
};

function chooseImage() {
  const file = new File(["fake image"], "drone.png", { type: "image/png" });
  fireEvent.change(screen.getByLabelText("Choose a drone image"), {
    target: { files: [file] },
  });
  return file;
}

describe("ImageDetectionWorkbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:drone-image"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.mocked(uploadImage).mockResolvedValue(uploadedImage);
    vi.mocked(runDetection).mockResolvedValue(baselineResponse);
    vi.mocked(getStoredDetections).mockResolvedValue(baselineResponse);
    vi.mocked(listImages).mockResolvedValue([]);
    vi.mocked(listSurveys).mockResolvedValue([]);
    vi.mocked(getAvailableModels).mockResolvedValue([
      {
        model_id: "baseline",
        model_name: "YOLO11n",
        model_version: "drone_person_vehicle",
        framework: "Ultralytics YOLO",
        class_count: 2,
        weights_available: true,
      },
      {
        model_id: "visdrone10_yolo11n",
        model_name: "YOLO11n VisDrone10",
        model_version: "visdrone10_yolo11n",
        framework: "Ultralytics YOLO",
        class_count: 10,
        weights_available: true,
      },
    ]);
    vi.mocked(getImage).mockResolvedValue(uploadedImage);
    vi.mocked(getImageIntelligence).mockResolvedValue(intelligenceResponse);
    vi.mocked(processImageIntelligence).mockResolvedValue(intelligenceResponse);
    vi.mocked(getImagePreviewUrl).mockReturnValue(
      "http://127.0.0.1:8000/api/images/42/preview",
    );
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("defaults to VisDrone10, uploads and renders its detections and original-pixel boxes", async () => {
    const { container } = render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);

    expect(
      (screen.getByLabelText("Detection model") as HTMLSelectElement).value,
    ).toBe("visdrone10_yolo11n");
    const file = chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    await screen.findByText("Detection complete. Results were returned by the backend.");
    expect(uploadImage).toHaveBeenCalledWith(file, expect.any(Function), undefined);
    expect(processImageIntelligence).toHaveBeenCalledWith(42, "visdrone10_yolo11n", true);
    expect(screen.getAllByText("awning-tricycle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("87.5%").length).toBeGreaterThan(0);

    const overlay = container.querySelector("svg.detection-overlay");
    expect(overlay?.getAttribute("viewBox")).toBe("0 0 640 480");
    const box = container.querySelector(".detection-box");
    expect(box?.getAttribute("x")).toBe("30.5");
    expect(box?.getAttribute("y")).toBe("40");
    expect(box?.getAttribute("width")).toBe("149.5");
    expect(box?.getAttribute("height")).toBe("170");
    expect(container.querySelector(".detection-class-7")).toBeTruthy();
  });

  it("sends the ten-class selection, shows its status and renders all class labels", async () => {
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Detection model"), {
      target: { value: "visdrone10_yolo11n" },
    });
    expect(screen.getByText(/mAP50 32.9%/)).toBeTruthy();
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    await screen.findByText("Detection complete. Results were returned by the backend.");
    expect(processImageIntelligence).toHaveBeenCalledWith(42, "visdrone10_yolo11n", true);
    expect(screen.getAllByText("awning-tricycle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("87.5%").length).toBeGreaterThan(0);
    for (const className of visdrone10Response.classes ?? []) {
      expect(screen.getAllByText(className).length).toBeGreaterThan(0);
    }
  });

  it("allows switching models after upload and offers an explicit rerun", async () => {
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);
    await screen.findByRole("option", { name: /Baseline/ });
    fireEvent.change(screen.getByLabelText("Detection model"), { target: { value: "baseline" } });
    vi.mocked(processImageIntelligence).mockResolvedValueOnce({
      ...intelligenceResponse,
      detection: { ...intelligenceResponse.detection, count: 1, detections: baselineResponse.detections },
      detection_run_response: baselineResponse,
    });
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));
    await screen.findByText("Detection complete. Results were returned by the backend.");

    fireEvent.change(screen.getByLabelText("Detection model"), {
      target: { value: "visdrone10_yolo11n" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run selected model" }));

    await waitFor(() => {
      expect(runDetection).toHaveBeenLastCalledWith(42, "visdrone10_yolo11n");
    });
  });

  it("shows a clear message when the model returns no detections", async () => {
    const emptyResult = {
      ...baselineResponse,
      detection_count: 0,
      detections: [],
    };
    vi.mocked(runDetection).mockResolvedValue(emptyResult);
    vi.mocked(getStoredDetections).mockResolvedValue(emptyResult);
    vi.mocked(processImageIntelligence).mockResolvedValue({
      ...intelligenceResponse,
      detection: { ...intelligenceResponse.detection, status: "completed", count: 0, per_class_counts: [], detections: [] },
      detection_run_response: emptyResult,
    });
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect(await screen.findByText("No objects detected")).toBeTruthy();
  });

  it("shows API failures and provides a retry action", async () => {
    vi.mocked(processImageIntelligence).mockRejectedValue(new Error("Backend unavailable"));
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Backend unavailable",
    );
    expect(screen.getByRole("button", { name: "Retry detection" })).toBeTruthy();
  });

  it("rejects unsupported image files before making API requests", () => {
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Choose a drone image"), {
      target: {
        files: [new File(["not an image"], "map.gif", { type: "image/gif" })],
      },
    });

    expect(screen.getByRole("alert").textContent).toContain(
      "Unsupported image format",
    );
    expect(uploadImage).not.toHaveBeenCalled();
    expect(runDetection).not.toHaveBeenCalled();
  });

  it("shows a loading state during detection", async () => {
    let resolveDetection!: (response: ImageIntelligenceResponse) => void;
    vi.mocked(processImageIntelligence).mockReturnValue(
      new Promise((resolve) => {
        resolveDetection = resolve;
      }),
    );
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect(await screen.findByText("Running image detection and eligible GPS-free localization…")).toBeTruthy();
    resolveDetection(intelligenceResponse);
    await screen.findByText("Detection complete. Results were returned by the backend.");
  });

  it("reopens a stored image and retrieves its persisted detections", async () => {
    vi.mocked(listImages).mockResolvedValue([uploadedImage]);
    vi.mocked(getStoredDetections).mockResolvedValue(visdrone10Response);
    render(<MemoryRouter><ImageDetectionWorkbench /></MemoryRouter>);

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /#42 · drone.png/ })).toBeTruthy();
    });
    fireEvent.change(screen.getByLabelText("Or reopen an uploaded image"), {
      target: { value: "42" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Load results" }));

    await waitFor(() => {
      expect(getImage).toHaveBeenCalledWith(42);
      expect(getStoredDetections).toHaveBeenCalledWith(42);
    });
    expect(screen.getAllByText("awning-tricycle").length).toBeGreaterThan(0);
    expect(
      (screen.getByRole("img", { name: /Preview of drone.png/ }) as HTMLImageElement).src,
    ).toContain("/api/images/42/preview");
  });
});
