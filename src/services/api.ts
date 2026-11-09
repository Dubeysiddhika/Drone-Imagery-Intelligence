import axios, { type AxiosProgressEvent } from "axios";

export const API_BASE_URL = (
	import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const api = axios.create({
	baseURL: API_BASE_URL,
	timeout: 30_000,
});

const inFlightGets = new Map<string, Promise<unknown>>();

function getOnce<T>(url: string, params?: Record<string, string | number>): Promise<T> {
	const key = `${url}?${new URLSearchParams(
		Object.entries(params ?? {}).map(([name, value]) => [name, String(value)]),
	).toString()}`;
	const existing = inFlightGets.get(key);
	if (existing) return existing as Promise<T>;

	const request = api.get<T>(url, { params }).then((response) => response.data);
	inFlightGets.set(key, request);
	void request.then(
		() => {
			if (inFlightGets.get(key) === request) inFlightGets.delete(key);
		},
		() => {
			if (inFlightGets.get(key) === request) inFlightGets.delete(key);
		},
	);
	return request;
}

export interface ImageMetadata {
	image_id: number;
	id: number;
	filename: string;
	latitude: number | null;
	longitude: number | null;
	altitude: number | null;
	capture_time: string | null;
	captured_at?: string | null;
	camera_make: string | null;
	camera_model: string | null;
	width: number | null;
	height: number | null;
	exif_available: boolean;
	uploaded_at?: string | null;
	detection_count?: number;
}

export interface Detection {
	id: number;
	class_id: number | null;
	class_name: string;
	confidence: number;
	model_name?: string | null;
	model_version?: string | null;
	bbox: {
		x1: number;
		y1: number;
		x2: number;
		y2: number;
	};
}

export interface DetectionResponse {
	image_id: number;
	model_name?: string | null;
	model_version?: string | null;
	classes?: string[];
	coordinate_system?: "pixel_xyxy";
	detection_count: number;
	detections: Detection[];
}

export type DetectionModelVersion = "baseline" | "visdrone10_yolo11n";

interface UploadResponse {
	success: boolean;
	image: ImageMetadata;
}

interface HealthResponse {
	status: string;
}

export interface DashboardSummary {
	total_images: number;
	total_surveys: number;
	total_detections: number;
	pedestrian_count: number;
	vehicle_count: number;
	average_confidence: number | null;
	class_counts: { class_name: string; count: number }[];
	category_definitions: {
		pedestrians: string[];
		vehicles: string[];
	};
	model_name: string | null;
	model_version: string | null;
	recent_images: ImageMetadata[];
	recent_activity: {
		id: number;
		image_id: number;
		filename: string;
		class_name: string;
		confidence: number;
		created_at: string | null;
		model_name: string | null;
		model_version: string | null;
	}[];
}

export interface AvailableModel {
	model_id: DetectionModelVersion;
	model_name: string;
	model_version: string;
	framework: string;
	class_count: number;
	weights_available: boolean;
}

export interface SurveyRecord {
	id: number;
	name: string;
	description: string | null;
	created_at: string;
}

export interface UAVVisLocStats {
  dataset: string;
  total_records: number;
  records_with_complete_orientation: number;
  records_without_complete_orientation: number;
}

export interface UAVVisLocRecord {
  id: number;
  relative_path: string;
  filename: string;
  capture_time_raw: string | null;
  latitude: number;
  longitude: number;
  height: number | null;
  omega: number | null;
  kappa: number | null;
  phi1: number | null;
  phi2: number | null;
  metadata_csv: string;
}

export interface UAVVisLocRecordsResponse {
  total: number;
  skip: number;
  limit: number;
  records: UAVVisLocRecord[];
}

export async function checkBackendHealth(): Promise<boolean> {
	const response = await getOnce<HealthResponse>("/api/health");
	return response.status === "healthy";
}

export async function listImages(): Promise<ImageMetadata[]> {
	return getOnce<ImageMetadata[]>("/api/images/");
}

export async function getImage(imageId: number): Promise<ImageMetadata> {
	return getOnce<ImageMetadata>(`/api/images/${imageId}`);
}

export function getImagePreviewUrl(imageId: number): string {
	return `${API_BASE_URL}/api/images/${imageId}/preview`;
}

export async function uploadImage(
	file: File,
	onProgress?: (percentage: number) => void,
): Promise<ImageMetadata> {
	const formData = new FormData();
	formData.append("file", file);

	const response = await api.post<UploadResponse>("/api/images/upload", formData, {
		onUploadProgress: (event: AxiosProgressEvent) => {
			if (event.total) {
				onProgress?.(Math.round((event.loaded / event.total) * 100));
			}
		},
	});

	if (!response.data.success || !response.data.image) {
		throw new Error("The backend did not return the uploaded image record.");
	}

	return response.data.image;
}

export async function runDetection(
	imageId: number,
	modelVersion: DetectionModelVersion = "baseline",
): Promise<DetectionResponse> {
	const response = await api.post<DetectionResponse>(
		`/api/analysis/detect/${imageId}`,
		undefined,
		{ params: { model_version: modelVersion } },
	);
	return response.data;
}

export async function getStoredDetections(
	imageId: number,
	minConfidence = 0,
): Promise<DetectionResponse> {
	return getOnce<DetectionResponse>(
		`/api/analysis/detections/${imageId}`,
		{ min_confidence: minConfidence },
	);
}

export async function getAvailableModels(): Promise<AvailableModel[]> {
	const response = await getOnce<{ models: AvailableModel[] }>(
		"/api/analysis/models",
	);
	return response.models;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
	return getOnce<DashboardSummary>("/api/dashboard/summary");
}

export async function listSurveys(): Promise<SurveyRecord[]> {
	return getOnce<SurveyRecord[]>("/api/surveys/");
}

export async function createSurvey(
	name: string,
	description: string,
): Promise<SurveyRecord> {
	const response = await api.post<SurveyRecord>("/api/surveys/", undefined, {
		params: { name, description },
	});
	return response.data;
}

export async function getUAVVisLocStats(): Promise<UAVVisLocStats> {
  return getOnce<UAVVisLocStats>("/api/uav-visloc/stats");
}

export async function listUAVVisLocRecords(
  skip = 0,
  limit = 25,
): Promise<UAVVisLocRecordsResponse> {
  return getOnce<UAVVisLocRecordsResponse>(
    "/api/uav-visloc/records",
    { skip, limit },
  );
}

export async function getUAVVisLocRecord(
  recordId: number,
): Promise<UAVVisLocRecord> {
  return getOnce<UAVVisLocRecord>(`/api/uav-visloc/records/${recordId}`);
}

export function getApiErrorMessage(error: unknown): string {
	if (axios.isAxiosError<{ detail?: string; message?: string }>(error)) {
		if (!error.response) {
			return `Cannot reach the backend at ${API_BASE_URL}. Check that FastAPI is running.`;
		}
		return (
			error.response.data?.detail ||
			error.response.data?.message ||
			`The backend returned HTTP ${error.response.status}.`
		);
	}
	return error instanceof Error ? error.message : "An unexpected error occurred.";
}
