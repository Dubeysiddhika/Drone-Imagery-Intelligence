import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  responseErrorHandler: null as null | ((error: unknown) => Promise<never>),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({
      get: mocks.get,
      post: mocks.post,
      interceptors: {
        response: {
          use: (_fulfilled: unknown, rejected: (error: unknown) => Promise<never>) => {
            mocks.responseErrorHandler = rejected;
          },
        },
      },
    }),
    isAxiosError: (error: unknown) =>
      Boolean(error && typeof error === "object" && "isAxiosError" in error && (error as { isAxiosError?: boolean }).isAxiosError),
  },
}));

import { getAuthErrorMessage, getStoredDetections, listImages, resolveApiBaseUrl, runDetection } from "../src/services/api";

const { get, post } = mocks;

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


describe("authentication API URL configuration", () => {
  it("uses the Vite same-origin proxy when no API origin is configured", () => {
    expect(resolveApiBaseUrl(undefined, "localhost")).toBe("");
    expect(resolveApiBaseUrl("", "127.0.0.1")).toBe("");
  });

  it("aligns local API host with the browser host for session cookies", () => {
    expect(resolveApiBaseUrl("http://127.0.0.1:8000", "localhost")).toBe("http://localhost:8000");
    expect(resolveApiBaseUrl("http://localhost:8000", "127.0.0.1")).toBe("http://127.0.0.1:8000");
  });

  it("does not rewrite a non-local API hostname", () => {
    expect(resolveApiBaseUrl("https://api.example.com", "localhost")).toBe("https://api.example.com");
  });
});


describe("authentication response handling", () => {
  it("does not treat invalid login credentials as an expired session", async () => {
    const handler = mocks.responseErrorHandler;
    if (!handler) throw new Error("Axios response interceptor was not registered");
    const error = {
      isAxiosError: true,
      response: { status: 401 },
      config: { url: "/api/auth/login" },
    };
    const dispatch = vi.spyOn(window, "dispatchEvent");
    await expect(handler(error)).rejects.toBe(error);
    expect(dispatch).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "aerovision:unauthorized" }),
    );
    dispatch.mockRestore();
  });

  it("clears the session after a 401 from a protected endpoint", async () => {
    const handler = mocks.responseErrorHandler;
    if (!handler) throw new Error("Axios response interceptor was not registered");
    const error = {
      isAxiosError: true,
      response: { status: 401 },
      config: { url: "/api/images/" },
    };
    const dispatch = vi.spyOn(window, "dispatchEvent");
    await expect(handler(error)).rejects.toBe(error);
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: "aerovision:unauthorized" }),
    );
    dispatch.mockRestore();
  });

  it("returns a useful message when the backend cannot be reached", () => {
    expect(getAuthErrorMessage({ isAxiosError: true, response: undefined }))
      .toContain("Cannot reach the backend");
  });

  it("keeps invalid-credential feedback generic", () => {
    expect(getAuthErrorMessage({
      isAxiosError: true,
      response: { status: 401 },
    })).toBe("Invalid email or password.");
  });
});
