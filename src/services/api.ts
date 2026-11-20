import axios, { type AxiosProgressEvent } from "axios";

export const API_BASE_URL = (
	import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const api = axios.create({
	baseURL: API_BASE_URL,
	timeout: 30_000,
	withCredentials: true,
});

api.interceptors.response.use((response) => response, (error: unknown) => {
	if (axios.isAxiosError(error) && error.response?.status === 401 && typeof window !== "undefined") {
		window.dispatchEvent(new Event("aerovision:unauthorized"));
	}
	return Promise.reject(error);
});

const inFlightGets = new Map<string, Promise<unknown>>();

function getOnce<T>(url: string, params?: Record<string, string | number | undefined>): Promise<T> {
	const key = `${url}?${new URLSearchParams(
		Object.entries(params ?? {})
			.filter(([, value]) => value !== undefined && value !== "")
			.map(([name, value]) => [name, String(value)]),
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
	gps_available: boolean;
	altitude: number | null;
	capture_time: string | null;
	captured_at?: string | null;
	camera_make: string | null;
	camera_model: string | null;
	width: number | null;
	height: number | null;
	orientation: number | null;
	focal_length: number | null;
	survey_id: number | null;
	exif_available: boolean;
	uploaded_at?: string | null;
	detection_count?: number;
	dataset_match?: {
		status: "matched" | "not_matched" | "ambiguous" | "error" | "not_checked";
		method: string | null;
		confidence: number | null;
		flight_sequence: string | null;
		dataset_relative_path: string | null;
		metadata: Record<string, unknown> | null;
	};
}

export interface AuthUser {
	id: number;
	full_name: string;
	email: string;
}

export interface AuthResponse {
	user: AuthUser;
	expires_in?: number;
}

export async function registerAccount(input: { full_name: string; email: string; password: string }): Promise<{ user: AuthUser; message: string }> {
	const response = await api.post<{ user: AuthUser; message: string }>("/api/auth/register", input);
	return response.data;
}

export async function signIn(email: string, password: string): Promise<AuthResponse> {
	const response = await api.post<AuthResponse>("/api/auth/login", { email, password });
	return response.data;
}

export async function signOut(): Promise<void> {
	await api.post("/api/auth/logout");
}

export async function getCurrentUser(): Promise<AuthUser> {
	const response = await api.get<{ user: AuthUser }>("/api/auth/me");
	return response.data.user;
}

export async function requestPasswordReset(email: string): Promise<{ message: string; email_delivery_configured: boolean }> {
	const response = await api.post<{ message: string; email_delivery_configured: boolean }>("/api/auth/password-reset/request", { email });
	return response.data;
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<{ message: string }> {
	const response = await api.post<{ message: string }>("/api/auth/password-reset/confirm", { token, new_password: newPassword });
	return response.data;
}

export interface GeospatialImage {
	image_id: number;
	survey_id: number | null;
	survey_name: string | null;
	gps_available: true;
	latitude: number;
	longitude: number;
	altitude: number | null;
	filename: string;
	captured_at: string | null;
	uploaded_at: string | null;
	detection_count: number;
	detected_classes: { class_name: string; count: number }[];
	original_image_url: string;
	annotated_image_url: string;
	coordinate_meaning: "image_capture_point";
	coordinate_reference_system: "EPSG:4326";
}

export interface UnlocatedGeospatialImage extends Omit<GeospatialImage, "latitude" | "longitude" | "gps_available"> {
	latitude: number | null;
	longitude: number | null;
	gps_available: false;
}

export interface GeospatialImageCollections {
	total: number;
	images: GeospatialImage[];
	located_images: GeospatialImage[];
	unlocated_images: UnlocatedGeospatialImage[];
	unlocated_total: number;
	available_classes: string[];
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
	annotated_image_url?: string;
}

export type DetectionModelVersion = "baseline" | "visdrone10_yolo11n";

interface UploadResponse {
	success: boolean;
	image: ImageMetadata;
	dataset_match?: ImageMetadata["dataset_match"];
}

export interface ImageIntelligenceResponse {
	image: {
		image_id: number;
		original_filename: string;
		file_format: string | null;
		file_size_bytes: number | null;
		width: number | null;
		height: number | null;
		exif_available: boolean;
		camera_make: string | null;
		camera_model: string | null;
		focal_length_mm: number | null;
		orientation: number | null;
		capture_time: string | null;
		exif_gps: { available: boolean; latitude: number | null; longitude: number | null; altitude_m: number | null; coordinate_source: string | null; coordinate_reference_system: string | null };
		survey_id: number | null;
	};
	dataset_identity: { status: string; method: string | null; confidence: number | null; flight_sequence: string | null; dataset_relative_path: string | null; metadata_source_csv: string | null };
	dataset_metadata: Record<string, unknown> | null;
	geospatial: {
		exif_coordinate: ImageIntelligenceResponse["image"]["exif_gps"];
		dataset_ground_truth: { available: boolean; latitude: number | null; longitude: number | null; coordinate_reference_system: string | null; coordinate_source: string | null };
		predicted_uav_coordinate: { available: boolean; latitude: number | null; longitude: number | null; coordinate_source: string | null; status?: string; reason?: string | null };
		localization_evaluation?: { available: boolean; error_m?: number; within_5m?: boolean; within_10m?: boolean; within_25m?: boolean; within_50m?: boolean; ground_truth_latitude?: number; ground_truth_longitude?: number; reason?: string; note?: string };
		satellite_candidate_region_rank_for_ground_truth_map: number | null;
		satellite_candidate_center_offsets_from_ground_truth: { rank: number; satellite_tile_id: string; satellite_candidate_center_distance_m: number }[];
		candidate_offsets_are_predictions: false;
		coordinate_reference_system: string;
	};
	detection: {
		status: string;
		count: number;
		per_class_counts: { class_name: string; count: number }[];
		coordinate_system: string;
		annotated_image_url: string | null;
		original_image_url: string;
		detections: Detection[];
		note: string;
	};
	localization: Partial<UAVVisLocLocalizationResponse> & { status: string; message?: string; candidates: UAVVisLocCandidate[] };
	processing: { runs: { id: number; pipeline: string; mode: string | null; status: string; processing_seconds: number | null; result_count: number | null; verified_count: number | null; error: string | null; started_at: string | null; completed_at: string | null }[] };
	detection_run_response?: DetectionResponse;
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
	confidence_distribution: { range: string; count: number }[];
	gps_statistics: { available_images: number; missing_images: number; availability_rate: number | null };
	detection_processing: { processed_images: number; pending_images: number };
	processing_time: Record<string, {
		completed_runs: number;
		mean_seconds: number | null;
		min_seconds: number | null;
		max_seconds: number | null;
	}>;
	localization_statistics: {
		total_runs: number;
		completed_runs: number;
		failed_or_incomplete_runs: number;
		candidate_patches_returned: number;
		verified_candidates: number;
		estimated_images?: number;
		unestimated_runs?: number;
		evaluated_images?: number;
		estimate_success_rate?: number | null;
		mean_error_m?: number | null;
		median_error_m?: number | null;
		within_5m_percent?: number | null;
		within_10m_percent?: number | null;
		within_25m_percent?: number | null;
		within_50m_percent?: number | null;
		sample_size?: number;
		per_flight?: { flight_sequence: string; localization_runs: number; estimated_images: number; failed_or_unestimated_images: number; evaluated_images: number; mean_error_m: number | null; median_error_m: number | null; within_5m_percent: number | null; within_10m_percent: number | null; within_25m_percent: number | null; within_50m_percent: number | null }[];
	};
	survey_statistics: {
		survey_id: number;
		survey_name: string;
		image_count: number;
		detection_count: number;
		gps_image_count: number;
	}[];
	recent_processing_activity: {
		id: number;
		image_id: number;
		filename: string;
		pipeline: string;
		mode: string | null;
		status: string;
		processing_seconds: number | null;
		result_count: number | null;
		verified_count: number | null;
		error_message: string | null;
		started_at: string | null;
		completed_at: string | null;
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

export interface UAVVisLocCandidate {
	rank: number;
	candidate_patch_id: string;
	satellite_tile_id: string;
	parent_satellite_map_id: string;
	similarity_score: number;
	local_feature_match_count: number | null;
	ransac_inlier_count: number | null;
	inlier_ratio: number | null;
	verification_status: string;
	latitude: number;
	longitude: number;
	coordinate_reference_system: "EPSG:4326";
	satellite_footprint: { type: "Polygon"; coordinates: number[][][] };
	preview_url: string;
	estimated_image_center?: {
		status: string;
		latitude: number | null;
		longitude: number | null;
		satellite_pixel_x?: number;
		satellite_pixel_y?: number;
		inlier_ratio?: number;
		median_reprojection_error_px?: number;
		query_inlier_hull_fraction?: number;
		satellite_inlier_hull_fraction?: number;
		quality?: "high" | "moderate";
		reason?: string;
	};
	geometric_verification?: {
		status: string;
		reason?: string | null;
		median_reprojection_error_px?: number | null;
		query_inlier_hull_fraction?: number | null;
		satellite_inlier_hull_fraction?: number | null;
	};
}

export type UAVVisLocMode = "gps_free" | "gps_assisted";

export interface UAVVisLocLocalizationResponse {
	query_image_id: number;
	query_image_url: string;
	mode: UAVVisLocMode;
	gps_assisted_filter: string | null;
	localization_status: string;
	localization_estimate?: {
		available: boolean;
		status: string;
		latitude: number | null;
		longitude: number | null;
		coordinate_reference_system?: string;
		coordinate_source?: string;
		supporting_candidate_ranks?: number[];
		selected_candidate_rank?: number;
		reason?: string | null;
	};
	evaluation?: {
		available: boolean;
		error_m?: number;
		within_5m?: boolean;
		within_10m?: boolean;
		within_25m?: boolean;
		within_50m?: boolean;
		ground_truth_latitude?: number;
		ground_truth_longitude?: number;
		ground_truth_source?: string;
		reason?: string;
		note?: string;
	};
	precise_localization_claimed: boolean;
	note: string;
	processing_time_seconds: number;
	retrieval_configuration: {
		query_preprocessing_px: number;
		initial_retrieval_top_k: number;
		one_ring_seed_count: number;
		candidate_budget: number;
		local_matching_shortlist: number;
	};
	candidates: UAVVisLocCandidate[];
}

export interface UAVVisLocStatus {
	available: boolean;
	index_manifest_available: boolean;
	descriptor_index_available: boolean;
	device: string;
	supported_modes: UAVVisLocMode[];
	gps_assisted_policy: string;
	note: string;
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

export async function listGeospatialImages(filters: {
	survey_id?: number;
	image_id?: number;
	class_name?: string;
	date_from?: string;
	date_to?: string;
} = {}): Promise<GeospatialImage[]> {
	const response = await getGeospatialImageCollections(filters);
	return response.located_images;
}

export async function getGeospatialImageCollections(filters: {
	survey_id?: number;
	image_id?: number;
	class_name?: string;
	date_from?: string;
	date_to?: string;
} = {}): Promise<GeospatialImageCollections> {
	return getOnce<GeospatialImageCollections>("/api/images/geospatial", filters);
}

export function getImagePreviewUrl(imageId: number): string {
	return `${API_BASE_URL}/api/images/${imageId}/preview`;
}

export async function uploadImage(
	file: File,
	onProgress?: (percentage: number) => void,
	surveyId?: number,
): Promise<ImageMetadata> {
	const formData = new FormData();
	formData.append("file", file);
	if (surveyId !== undefined) formData.append("survey_id", String(surveyId));

	const response = await api.post<UploadResponse>("/api/images/upload", formData, {
		timeout: 300_000,
		onUploadProgress: (event: AxiosProgressEvent) => {
			if (event.total) {
				onProgress?.(Math.round((event.loaded / event.total) * 100));
			}
		},
	});

	if (!response.data.success || !response.data.image) {
		throw new Error("The backend did not return the uploaded image record.");
	}

	return { ...response.data.image, dataset_match: response.data.dataset_match };
}

export async function processImageIntelligence(
	imageId: number,
	modelVersion: DetectionModelVersion = "visdrone10_yolo11n",
	runLocalization = true,
): Promise<ImageIntelligenceResponse> {
	const response = await api.post<ImageIntelligenceResponse>(
		`/api/intelligence/images/${imageId}/process`,
		undefined,
		{ params: { model_version: modelVersion, run_localization: runLocalization }, timeout: 240_000 },
	);
	return response.data;
}

export async function getImageIntelligence(imageId: number): Promise<ImageIntelligenceResponse> {
	return getOnce<ImageIntelligenceResponse>(`/api/intelligence/images/${imageId}`);
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

export async function getDashboardSummary(filters: {
	survey_id?: number;
	date_from?: string;
	date_to?: string;
} = {}): Promise<DashboardSummary> {
	return getOnce<DashboardSummary>("/api/dashboard/summary", filters);
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

export async function runUAVVisLocLocalization(
	imageId: number,
	mode: UAVVisLocMode = "gps_free",
): Promise<UAVVisLocLocalizationResponse> {
	const response = await api.post<UAVVisLocLocalizationResponse>(
		`/api/uav-visloc/localize/${imageId}`,
		undefined,
		{ params: { mode }, timeout: 180_000 },
	);
	return response.data;
}

export async function getUAVVisLocStatus(): Promise<UAVVisLocStatus> {
	return getOnce<UAVVisLocStatus>("/api/uav-visloc/localization/status");
}

export function getApiErrorMessage(error: unknown): string {
	if (axios.isAxiosError<{ detail?: unknown; message?: string }>(error)) {
		if (!error.response) {
			return `Cannot reach the backend at ${API_BASE_URL}. Check that FastAPI is running.`;
		}
		const detail = error.response.data?.detail;
		if (typeof detail === "string") return detail;
		if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
		return error.response.data?.message ?? `The backend returned HTTP ${error.response.status}.`;
	}
	return error instanceof Error ? error.message : "An unexpected error occurred.";
}
