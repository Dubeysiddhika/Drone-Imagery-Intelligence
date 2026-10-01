import axios, { type AxiosProgressEvent } from "axios";

export const API_BASE_URL = (
	import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8020"
).replace(/\/$/, "");

const api = axios.create({
	baseURL: API_BASE_URL,
	timeout: 30_000,
});

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
}

export interface Detection {
	id: number;
	class_id: number;
	class_name: string;
	confidence: number;
	bbox: {
		x1: number;
		y1: number;
		x2: number;
		y2: number;
	};
}

export interface DetectionResponse {
	image_id: number;
	detection_count: number;
	detections: Detection[];
}

interface UploadResponse {
	success: boolean;
	image: ImageMetadata;
}

interface HealthResponse {
	status: string;
}

interface ImageRecord {
	id: number;
	image_id?: number;
}

export interface WorkspaceSummary {
	totalImages: number;
	totalDetections: number;
	persons: number;
	vehicles: number;
	averageConfidence: number;
}

export async function checkBackendHealth(): Promise<boolean> {
	const response = await api.get<HealthResponse>("/api/health");
	return response.data.status === "healthy";
}

export async function listImages(): Promise<ImageRecord[]> {
	const response = await api.get<ImageRecord[]>("/api/images/");
	return response.data;
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

export async function runDetection(imageId: number): Promise<DetectionResponse> {
	const response = await api.post<DetectionResponse>(
		`/api/analysis/detect/${imageId}`,
	);
	return response.data;
}

export async function getStoredDetections(
	imageId: number,
): Promise<DetectionResponse> {
	const response = await api.get<DetectionResponse>(
		`/api/analysis/detections/${imageId}`,
	);
	return response.data;
}

export async function getWorkspaceSummary(): Promise<WorkspaceSummary> {
	const images = await listImages();
	const results = await Promise.all(
		images.map((image) => getStoredDetections(image.image_id ?? image.id)),
	);
	const detections = results.flatMap((result) => result.detections);
	const persons = detections.filter(
		(detection) => detection.class_name.toLowerCase() === "person",
	).length;
	const vehicles = detections.filter(
		(detection) => detection.class_name.toLowerCase() === "vehicle",
	).length;

	return {
		totalImages: images.length,
		totalDetections: detections.length,
		persons,
		vehicles,
		averageConfidence: detections.length
			? detections.reduce((total, detection) => total + detection.confidence, 0) /
				detections.length
			: 0,
	};
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
