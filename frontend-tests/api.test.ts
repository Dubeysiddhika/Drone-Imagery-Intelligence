import { beforeEach, describe, expect, it, vi } from "vitest";

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({ get: vi.fn(), post }),
    isAxiosError: () => false,
  },
}));

import { runDetection } from "../src/services/api";

describe("runDetection", () => {
  beforeEach(() => {
    post.mockReset();
    post.mockResolvedValue({
      data: { image_id: 42, detection_count: 0, detections: [] },
    });
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
});
