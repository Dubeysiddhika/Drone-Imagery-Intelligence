import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({ get, post }),
    isAxiosError: () => false,
  },
}));

import { getStoredDetections, listImages, runDetection } from "../src/services/api";

describe("runDetection", () => {
  beforeEach(() => {
    post.mockReset();
    get.mockReset();
    post.mockResolvedValue({
      data: { image_id: 42, detection_count: 0, detections: [] },
    });
    get.mockResolvedValue({ data: [] });
  });

  it("requests the existing baseline mode by default", async () => {
    await runDetection(42);

    expect(post).toHaveBeenCalledWith(
      "/api/analysis/detect/42",
      undefined,
      { params: { model_version: "baseline" } },
    );
  });

  it("sends the selected ten-class mode as the backend query parameter", async () => {
    await runDetection(42, "visdrone10_yolo11n");

    expect(post).toHaveBeenCalledWith(
      "/api/analysis/detect/42",
      undefined,
      { params: { model_version: "visdrone10_yolo11n" } },
    );
  });

  it("requests stored detections with the selected confidence threshold", async () => {
    await getStoredDetections(42, 0.75);

    expect(get).toHaveBeenCalledWith(
      "/api/analysis/detections/42",
      { params: { min_confidence: 0.75 } },
    );
  });

  it("deduplicates concurrent image-list requests", async () => {
    const first = listImages();
    const second = listImages();

    expect(get).toHaveBeenCalledTimes(1);
    await expect(Promise.all([first, second])).resolves.toEqual([[], []]);
  });
});
