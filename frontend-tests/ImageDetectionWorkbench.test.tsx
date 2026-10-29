// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImageDetectionWorkbench from "../src/components/dashboard/ImageDetectionWorkbench";
import {
  runDetection,
  uploadImage,
  type DetectionResponse,
  type ImageMetadata,
} from "../src/services/api";

vi.mock("../src/services/api", () => ({
  getApiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  runDetection: vi.fn(),
  uploadImage: vi.fn(),
}));

const uploadedImage: ImageMetadata = {
  image_id: 42,
  id: 42,
  filename: "drone.png",
  latitude: null,
  longitude: null,
  altitude: null,
  capture_time: null,
  camera_make: null,
  camera_model: null,
  width: 640,
  height: 480,
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
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("defaults to baseline, uploads and renders its detections and original-pixel boxes", async () => {
    const { container } = render(<ImageDetectionWorkbench />);

    expect(
      (screen.getByLabelText("Detection model") as HTMLSelectElement).value,
    ).toBe("baseline");
    const file = chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    await screen.findByText("Detection complete. Results were returned by the backend.");
    expect(uploadImage).toHaveBeenCalledWith(file, expect.any(Function));
    expect(runDetection).toHaveBeenCalledWith(42, "baseline");
    expect(screen.getAllByText("vehicle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("91%").length).toBeGreaterThan(0);

    const overlay = container.querySelector("svg.detection-overlay");
    expect(overlay?.getAttribute("viewBox")).toBe("0 0 640 480");
    const box = container.querySelector(".detection-box");
    expect(box?.getAttribute("x")).toBe("20");
    expect(box?.getAttribute("y")).toBe("30");
    expect(box?.getAttribute("width")).toBe("100");
    expect(box?.getAttribute("height")).toBe("100");
    expect(container.querySelector(".detection-vehicle")).toBeTruthy();
  });

  it("sends the ten-class selection, shows its status and renders all class labels", async () => {
    vi.mocked(runDetection).mockResolvedValue(visdrone10Response);
    render(<ImageDetectionWorkbench />);

    fireEvent.change(screen.getByLabelText("Detection model"), {
      target: { value: "visdrone10_yolo11n" },
    });
    expect(screen.getByText(/epoch 5 of a planned 100/)).toBeTruthy();
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    await screen.findByText("Detection complete. Results were returned by the backend.");
    expect(runDetection).toHaveBeenCalledWith(42, "visdrone10_yolo11n");
    expect(screen.getAllByText("awning-tricycle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("87.5%").length).toBeGreaterThan(0);
    for (const className of visdrone10Response.classes ?? []) {
      expect(screen.getAllByText(className).length).toBeGreaterThan(0);
    }
  });

  it("allows switching models after upload and offers an explicit rerun", async () => {
    render(<ImageDetectionWorkbench />);
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
    vi.mocked(runDetection).mockResolvedValue({
      ...baselineResponse,
      detection_count: 0,
      detections: [],
    });
    render(<ImageDetectionWorkbench />);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect(await screen.findByText("No objects detected")).toBeTruthy();
  });

  it("shows API failures and provides a retry action", async () => {
    vi.mocked(runDetection).mockRejectedValue(new Error("Backend unavailable"));
    render(<ImageDetectionWorkbench />);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Backend unavailable",
    );
    expect(screen.getByRole("button", { name: "Retry detection" })).toBeTruthy();
  });

  it("rejects unsupported image files before making API requests", () => {
    render(<ImageDetectionWorkbench />);
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
    let resolveDetection!: (response: DetectionResponse) => void;
    vi.mocked(runDetection).mockReturnValue(
      new Promise((resolve) => {
        resolveDetection = resolve;
      }),
    );
    render(<ImageDetectionWorkbench />);
    chooseImage();
    fireEvent.click(screen.getByRole("button", { name: "Upload and analyze" }));

    expect(await screen.findByText("YOLO is processing the uploaded image…")).toBeTruthy();
    resolveDetection(baselineResponse);
    await screen.findByText("Detection complete. Results were returned by the backend.");
  });
});
