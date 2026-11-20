"""CPU retrieval and bounded local verification over the preserved UAV-VisLoc index."""

from __future__ import annotations

import csv
import gc
import importlib
import json
import logging
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import psutil
import torch
from PIL import Image
from pyproj import Transformer
from rasterio.transform import Affine


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PHASE3C_DIR = (
    PROJECT_ROOT
    / "backend/training/uav_visloc/phase3_pretrained_setup/phase3c"
).resolve()
PHASE3H_DIR = (
    PROJECT_ROOT
    / "backend/training/uav_visloc/phase3_pretrained_setup/phase3h"
).resolve()
logger = logging.getLogger(__name__)
_inference_lock = threading.Lock()
_phase_modules: tuple[Any, Any] | None = None


def _env_number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and minimum <= value <= maximum else default


QUALITY_THRESHOLDS = {
    "minimum_tentative_matches": int(_env_number("UAV_VISLOC_MIN_MATCHES", 8, 4, 2000)),
    "minimum_ransac_inliers": int(_env_number("UAV_VISLOC_MIN_INLIERS", 8, 4, 2000)),
    "minimum_inlier_ratio": _env_number("UAV_VISLOC_MIN_INLIER_RATIO", 0.25, 0.05, 1.0),
    "minimum_inlier_hull_fraction_per_image": _env_number("UAV_VISLOC_MIN_HULL_FRACTION", 0.015, 0.001, 0.5),
    "minimum_inlier_span_fraction": _env_number("UAV_VISLOC_MIN_SPAN_FRACTION", 0.12, 0.02, 0.9),
    "maximum_median_reprojection_error_px": _env_number("UAV_VISLOC_MAX_REPROJECTION_ERROR_PX", 3.0, 0.5, 50),
    "maximum_consensus_separation_m": _env_number("UAV_VISLOC_CONSENSUS_DISTANCE_M", 25, 1, 10000),
    "superpoint_max_keypoints": int(_env_number("UAV_VISLOC_MAX_KEYPOINTS", 512, 64, 2048)),
}


class LocalizationUnavailableError(RuntimeError):
    """The configured research artifacts or inference stack are unavailable."""


def _phase3c_modules() -> tuple[Any, Any]:
    """Load the established preprocessing and candidate-selector functions."""
    global _phase_modules
    if _phase_modules is not None:
        return _phase_modules
    phase_path = str(PHASE3C_DIR)
    inserted = phase_path not in sys.path
    if inserted:
        sys.path.insert(0, phase_path)
    try:
        common = importlib.import_module("phase3c_common")
        selector = importlib.import_module("evaluate_candidate_selection")
        _phase_modules = (common, selector)
        return _phase_modules
    finally:
        if inserted:
            try:
                sys.path.remove(phase_path)
            except ValueError:
                pass


def _available_ram_gb() -> float:
    return psutil.virtual_memory().available / 1024**3


def _gps_matching_parent_ids(
    tile_rows: list[dict[str, str]],
    latitude: float,
    longitude: float,
) -> set[str]:
    """Return only indexed parent maps whose source bounds contain the EXIF point."""
    return {
        row["parent_satellite_map_id"]
        for row in tile_rows
        if float(row["parent_min_lon"]) <= longitude <= float(row["parent_max_lon"])
        and float(row["parent_min_lat"]) <= latitude <= float(row["parent_max_lat"])
    }


def _load_index_and_candidates(
    query_path: Path,
    gps_coordinates: tuple[float, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    common, selector = _phase3c_modules()
    config_path = PHASE3C_DIR / "index_config.yaml"
    config, paths = common.load_config(config_path)
    manifest_path = paths["index_metadata"] / "satellite_index_manifest.json"
    if not manifest_path.is_file():
        raise LocalizationUnavailableError("The satellite index manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise LocalizationUnavailableError("The satellite descriptor index is not complete.")

    index_path = paths["global_features"] / "satellite_index.npz"
    if not index_path.is_file():
        raise LocalizationUnavailableError("The existing satellite descriptor index is missing.")
    with np.load(index_path, allow_pickle=False) as payload:
        tile_ids = payload["tile_ids"].astype(str)
        descriptors = payload["descriptors"].astype(np.float32, copy=True)
    if descriptors.ndim != 2 or descriptors.shape != (len(tile_ids), 384):
        raise LocalizationUnavailableError("The satellite index has an unexpected descriptor shape.")
    if len(tile_ids) != int(manifest.get("descriptor_count", -1)):
        raise LocalizationUnavailableError("The satellite index does not match its manifest.")

    with paths["tile_metadata"].open("r", encoding="utf-8-sig", newline="") as handle:
        tile_rows = list(csv.DictReader(handle))
    metadata_ids = {row["tile_id"] for row in tile_rows}
    if len(metadata_ids) != len(tile_rows) or metadata_ids != set(tile_ids.tolist()):
        raise LocalizationUnavailableError("Satellite metadata and descriptor IDs do not match.")
    metadata_by_id = {row["tile_id"]: row for row in tile_rows}

    # Match the evaluated preprocessing while retaining the satellite index at 224 px.
    query_config = json.loads(json.dumps(config))
    query_config["dinov2"]["input_size_px"] = 280
    torch.set_num_threads(1)
    if _available_ram_gb() < 0.55:
        raise LocalizationUnavailableError(
            "Localization paused because available RAM is below the safe DINOv2 threshold (0.55 GB)."
        )
    device = torch.device("cpu")
    model = common.load_dinov2(query_config, device)
    try:
        query_descriptor = common.dinov2_descriptor(model, query_path, query_config, device)
    finally:
        del model
        gc.collect()

    scores = descriptors @ query_descriptor
    if not np.isfinite(scores).all():
        raise LocalizationUnavailableError("Cosine search returned non-finite scores.")
    id_to_index = {tile_id: index for index, tile_id in enumerate(tile_ids.tolist())}
    metadata_index = {row["tile_id"]: index for index, row in enumerate(tile_rows)}
    if gps_coordinates is None:
        ranked_indices = np.argsort(-scores, kind="stable")[:50]
    else:
        latitude, longitude = gps_coordinates
        eligible_parent_ids = _gps_matching_parent_ids(tile_rows, latitude, longitude)
        if not eligible_parent_ids:
            raise LocalizationUnavailableError(
                "The EXIF GPS point does not overlap any indexed satellite-map footprint. "
                "GPS-assisted localization will not fall back to GPS-free retrieval."
            )
        eligible_indices = np.asarray([
            index for index, tile_id in enumerate(tile_ids)
            if tile_rows[metadata_index[tile_id]]["parent_satellite_map_id"] in eligible_parent_ids
        ], dtype=np.int64)
        if eligible_indices.size == 0:
            raise LocalizationUnavailableError(
                "No indexed satellite patches are available inside the EXIF GPS footprint."
            )
        eligible_order = np.argsort(-scores[eligible_indices], kind="stable")[:50]
        ranked_indices = eligible_indices[eligible_order]
    adjacency = selector.build_adjacency(tile_rows)
    metadata_scores = np.asarray(
        [scores[id_to_index[row["tile_id"]]] for row in tile_rows], dtype=np.float32
    )
    seeds = [metadata_index[tile_ids[index]] for index in ranked_indices]
    selected = selector.adaptive_expansion(
        seeds=seeds,
        adjacency=adjacency,
        scores=metadata_scores,
        anchor_count=5,
        budget=75,
        rings=1,
    )

    candidates: list[dict[str, Any]] = []
    for rank, row_index in enumerate(selected, start=1):
        metadata = tile_rows[row_index]
        tile_id = metadata["tile_id"]
        candidates.append({
            "rank": rank,
            "candidate_patch_id": tile_id,
            "satellite_tile_id": tile_id,
            "parent_satellite_map_id": metadata["parent_satellite_map_id"],
            "similarity_score": float(scores[id_to_index[tile_id]]),
            "local_feature_match_count": None,
            "ransac_inlier_count": None,
            "inlier_ratio": None,
            "verification_status": "not_run_local_shortlist_limit",
            "estimated_image_center": {"status": "not_evaluated", "latitude": None, "longitude": None},
            "latitude": None,
            "longitude": None,
            "coordinate_reference_system": "EPSG:4326",
            "satellite_footprint": _candidate_footprint_wgs84(metadata),
            "preview_url": f"/api/uav-visloc/candidates/{tile_id}/preview",
            "_metadata": metadata,
            "_tile_path": str(paths["satellite_tiles"] / metadata["image_relative_path"]),
        })
    # Drop all full-index arrays and adjacency before loading local feature models.
    del descriptors, tile_ids, scores, adjacency, metadata_scores, query_descriptor
    gc.collect()
    return candidates, paths


def _candidate_center_wgs84(metadata: dict[str, str]) -> tuple[float, float]:
    transform = Affine(*json.loads(metadata["affine_transform"]))
    x, y = transform * (
        int(metadata["tile_width_px"]) / 2,
        int(metadata["tile_height_px"]) / 2,
    )
    transformer = Transformer.from_crs(metadata["crs"], "EPSG:4326", always_xy=True)
    longitude, latitude = transformer.transform(x, y)
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Satellite patch transform returned invalid WGS84 coordinates.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Satellite patch center falls outside WGS84 coordinate bounds.")
    return latitude, longitude


def _candidate_footprint_wgs84(metadata: dict[str, str]) -> dict[str, Any]:
    transform = Affine(*json.loads(metadata["affine_transform"]))
    width = int(metadata["tile_width_px"])
    height = int(metadata["tile_height_px"])
    transformer = Transformer.from_crs(metadata["crs"], "EPSG:4326", always_xy=True)
    corners = [(0, 0), (width, 0), (width, height), (0, height), (0, 0)]
    ring: list[list[float]] = []
    for column, row in corners:
        x, y = transform * (column, row)
        longitude, latitude = transformer.transform(x, y)
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            raise ValueError("Satellite patch transform returned an invalid footprint.")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("Satellite patch footprint falls outside WGS84 bounds.")
        ring.append([float(longitude), float(latitude)])
    return {"type": "Polygon", "coordinates": [ring]}


def _image_tensor(image_path: Path, max_side: int) -> torch.Tensor:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        scale = min(1.0, max_side / max(image.size))
        if scale < 1.0:
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.BILINEAR,
            )
        pixels = np.asarray(image, dtype=np.uint8).copy()
    tensor = torch.from_numpy(pixels).permute(2, 0, 1).unsqueeze(0).float().div_(255.0)
    del pixels
    return tensor


def _extract_local_features(extractor: Any, image_path: Path) -> dict[str, Any]:
    tensor = _image_tensor(image_path, max_side=512)
    try:
        with torch.inference_mode():
            return extractor.extract(tensor)
    finally:
        del tensor


def _resized_image_size(image_path: Path, max_side: int = 512) -> tuple[int, int]:
    """Return the pixel size used by local features without retaining the image."""
    with Image.open(image_path) as source:
        width, height = source.size
    scale = min(1.0, max_side / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def _geometrically_localize(
    points_query: np.ndarray,
    points_satellite: np.ndarray,
    inlier_mask: np.ndarray,
    homography: np.ndarray | None,
    match_count: int,
    query_size: tuple[int, int],
    satellite_size: tuple[int, int],
    metadata: dict[str, str],
) -> dict[str, Any]:
    """Estimate image center only when a well-conditioned planar mapping is supported.

    A homography is a local planar-scene approximation; it is not assumed valid for
    every oblique drone/satellite pair. Every geometric quality gate is explicit.
    """
    rejected = {"status": "rejected_quality_control", "latitude": None, "longitude": None}
    mask = np.asarray(inlier_mask).reshape(-1).astype(bool)
    query = np.asarray(points_query, dtype=np.float64).reshape(-1, 2)
    satellite = np.asarray(points_satellite, dtype=np.float64).reshape(-1, 2)
    if len(query) != len(satellite) or len(mask) != len(query):
        return {**rejected, "reason": "Correspondence and RANSAC mask sizes differ."}
    if match_count < QUALITY_THRESHOLDS["minimum_tentative_matches"] or int(mask.sum()) < QUALITY_THRESHOLDS["minimum_ransac_inliers"]:
        return {**rejected, "reason": f"At least {QUALITY_THRESHOLDS['minimum_tentative_matches']} tentative matches and {QUALITY_THRESHOLDS['minimum_ransac_inliers']} inliers are required."}
    inlier_ratio = float(mask.sum() / match_count)
    if inlier_ratio < QUALITY_THRESHOLDS["minimum_inlier_ratio"]:
        return {**rejected, "reason": f"RANSAC inlier ratio is below {QUALITY_THRESHOLDS['minimum_inlier_ratio']:.3f}."}
    q_in = query[mask]
    s_in = satellite[mask]
    q_width, q_height = query_size
    s_width, s_height = satellite_size
    q_hull_fraction = cv2.contourArea(cv2.convexHull(q_in.astype(np.float32))) / max(1, q_width * q_height)
    s_hull_fraction = cv2.contourArea(cv2.convexHull(s_in.astype(np.float32))) / max(1, s_width * s_height)
    q_span = np.ptp(q_in, axis=0)
    s_span = np.ptp(s_in, axis=0)
    if q_hull_fraction < QUALITY_THRESHOLDS["minimum_inlier_hull_fraction_per_image"] or s_hull_fraction < QUALITY_THRESHOLDS["minimum_inlier_hull_fraction_per_image"] or min(q_span) < min(q_width, q_height) * QUALITY_THRESHOLDS["minimum_inlier_span_fraction"] or min(s_span) < min(s_width, s_height) * QUALITY_THRESHOLDS["minimum_inlier_span_fraction"]:
        return {**rejected, "reason": "Inliers do not cover enough area in both images."}

    if homography is None or not np.isfinite(homography).all() or abs(float(np.linalg.det(homography))) < 1e-12:
        return {**rejected, "reason": "Homography is missing, non-finite, or singular."}
    if not math.isfinite(float(np.linalg.cond(homography))) or float(np.linalg.cond(homography)) > 1e8:
        return {**rejected, "reason": "Homography is numerically ill-conditioned."}
    projected_inliers = cv2.perspectiveTransform(q_in.astype(np.float32).reshape(-1, 1, 2), homography).reshape(-1, 2)
    errors = np.linalg.norm(projected_inliers - s_in.astype(np.float32), axis=1)
    median_error = float(np.median(errors)) if len(errors) else math.inf
    if not math.isfinite(median_error) or median_error > QUALITY_THRESHOLDS["maximum_median_reprojection_error_px"]:
        return {**rejected, "reason": f"Median inlier reprojection error exceeds {QUALITY_THRESHOLDS['maximum_median_reprojection_error_px']:.2f} pixels.", "median_reprojection_error_px": median_error}

    center_query = np.array([[[q_width / 2.0, q_height / 2.0]]], dtype=np.float32)
    center_sat_resized = cv2.perspectiveTransform(center_query, homography).reshape(2)
    tile_width = int(metadata["tile_width_px"])
    tile_height = int(metadata["tile_height_px"])
    pixel_x = float(center_sat_resized[0] * tile_width / s_width)
    pixel_y = float(center_sat_resized[1] * tile_height / s_height)
    if not (math.isfinite(pixel_x) and math.isfinite(pixel_y) and 0 <= pixel_x < tile_width and 0 <= pixel_y < tile_height):
        return {**rejected, "reason": "Projected query center falls outside the satellite patch."}
    transform = Affine(*json.loads(metadata["affine_transform"]))
    map_x, map_y = transform * (pixel_x, pixel_y)
    longitude, latitude = Transformer.from_crs(metadata["crs"], "EPSG:4326", always_xy=True).transform(map_x, map_y)
    if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        return {**rejected, "reason": "Projected center could not be converted to valid EPSG:4326 coordinates."}
    quality = "high" if int(mask.sum()) >= 20 and inlier_ratio >= 0.5 and median_error <= 1.5 else "moderate"
    return {
        "status": "geometrically_verified",
        "latitude": float(latitude),
        "longitude": float(longitude),
        "satellite_pixel_x": pixel_x,
        "satellite_pixel_y": pixel_y,
        "inlier_ratio": inlier_ratio,
        "median_reprojection_error_px": median_error,
        "query_inlier_hull_fraction": float(q_hull_fraction),
        "satellite_inlier_hull_fraction": float(s_hull_fraction),
        "quality": quality,
        "transformation": "query_to_satellite_homography",
    }


def _estimate_candidate_consensus(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Select a spatially consistent group; conflicting candidate fixes are rejected."""
    estimates = [candidate for candidate in candidates if candidate.get("estimated_image_center", {}).get("status") == "geometrically_verified"]
    if not estimates:
        return {"available": False, "status": "no_reliable_estimate", "latitude": None, "longitude": None, "reason": "No candidate passed geometric quality control."}
    estimates.sort(key=lambda item: (item["rank"], -(item.get("ransac_inlier_count") or 0)))
    clusters: list[list[dict[str, Any]]] = []
    for candidate in estimates:
        point = candidate["estimated_image_center"]
        matching = next((cluster for cluster in clusters if all(
            _distance_m(point["latitude"], point["longitude"], other["estimated_image_center"]["latitude"], other["estimated_image_center"]["longitude"]) <= QUALITY_THRESHOLDS["maximum_consensus_separation_m"]
        for other in cluster
        )), None)
        if matching is None:
            clusters.append([candidate])
        else:
            matching.append(candidate)
    clusters.sort(key=lambda cluster: (-len(cluster), cluster[0]["rank"]))
    best = clusters[0]
    if len(clusters) > 1 and len(best) == len(clusters[1]):
        return {"available": False, "status": "conflicting_candidate_estimates", "latitude": None, "longitude": None, "reason": f"Equally supported candidate groups disagree by more than {QUALITY_THRESHOLDS['maximum_consensus_separation_m']:.1f} metres."}
    if len(best) == 1 and len(estimates) > 1:
        return {"available": False, "status": "conflicting_candidate_estimates", "latitude": None, "longitude": None, "reason": f"Only one candidate supports its estimate while another verified candidate conflicts by more than {QUALITY_THRESHOLDS['maximum_consensus_separation_m']:.1f} metres."}
    # Use the strongest-ranked member as the fix; do not average incompatible estimates.
    selected = best[0]
    fix = selected["estimated_image_center"]
    return {
        "available": True,
        "status": "verified_candidate_consensus" if len(best) > 1 else "single_verified_candidate",
        "latitude": fix["latitude"],
        "longitude": fix["longitude"],
        "coordinate_reference_system": "EPSG:4326",
        "coordinate_source": "ransac_verified_query_to_satellite_homography",
        "supporting_candidate_ranks": [item["rank"] for item in best],
        "selected_candidate_rank": selected["rank"],
        "quality": fix.get("quality"),
        "median_reprojection_error_px": fix.get("median_reprojection_error_px"),
        "supporting_inlier_counts": [item.get("ransac_inlier_count") for item in best],
        "reason": None if len(best) > 1 else "Only one candidate passed geometric quality control; treat this estimate cautiously.",
    }


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


def _match_shortlist(query_path: Path, candidates: list[dict[str, Any]], paths: dict[str, Path]) -> None:
    shortlist = candidates[:5]
    for candidate in candidates:
        metadata = candidate["_metadata"]
        candidate["latitude"], candidate["longitude"] = _candidate_center_wgs84(metadata)

    if _available_ram_gb() < 0.45:
        for candidate in shortlist:
            candidate["verification_status"] = "skipped_low_available_memory"
        return

    from lightglue import LightGlue, SuperPoint

    torch.set_num_threads(1)
    extractor = matcher = query_features = None
    try:
        extractor = SuperPoint(max_num_keypoints=QUALITY_THRESHOLDS["superpoint_max_keypoints"]).eval().to(torch.device("cpu"))
        matcher = LightGlue(features="superpoint").eval().to(torch.device("cpu"))
        query_features = _extract_local_features(extractor, query_path)
        query_size = _resized_image_size(query_path)
        for candidate in shortlist:
            if _available_ram_gb() < 0.30:
                candidate["verification_status"] = "stopped_low_available_memory"
                continue
            tile_path = Path(candidate["_tile_path"])
            if not tile_path.is_file():
                candidate["verification_status"] = "candidate_tile_missing"
                continue
            satellite_features = output = None
            try:
                satellite_features = _extract_local_features(extractor, tile_path)
                with torch.inference_mode():
                    output = matcher({"image0": query_features, "image1": satellite_features})
                pairs = output["matches"][0].detach().cpu().numpy()
                if pairs.ndim != 2 or pairs.shape[1] != 2:
                    pairs = np.empty((0, 2), dtype=np.int64)
                inliers = 0
                ratio = 0.0
                homography = None
                mask = None
                points_query = np.empty((0, 2), dtype=np.float32)
                points_satellite = np.empty((0, 2), dtype=np.float32)
                if len(pairs) >= 4:
                    points_query = query_features["keypoints"][0].detach().cpu().numpy()[pairs[:, 0]]
                    points_satellite = satellite_features["keypoints"][0].detach().cpu().numpy()[pairs[:, 1]]
                    homography, mask = cv2.findHomography(
                        points_query.astype(np.float32),
                        points_satellite.astype(np.float32),
                        cv2.RANSAC,
                        4.0,
                        maxIters=1000,
                        confidence=0.99,
                    )
                    if homography is not None and mask is not None:
                        inliers = int(mask.ravel().sum())
                        ratio = inliers / len(pairs)
                candidate["local_feature_match_count"] = int(len(pairs))
                candidate["ransac_inlier_count"] = inliers
                candidate["inlier_ratio"] = round(ratio, 5)
                estimate = _geometrically_localize(
                    points_query, points_satellite,
                    mask if mask is not None else np.zeros((len(pairs), 1), dtype=np.uint8),
                    homography, len(pairs), query_size, _resized_image_size(tile_path),
                    candidate["_metadata"],
                )
                candidate["estimated_image_center"] = estimate
                candidate["geometric_verification"] = {
                    "status": estimate["status"],
                    "reason": estimate.get("reason"),
                    "median_reprojection_error_px": estimate.get("median_reprojection_error_px"),
                    "query_inlier_hull_fraction": estimate.get("query_inlier_hull_fraction"),
                    "satellite_inlier_hull_fraction": estimate.get("satellite_inlier_hull_fraction"),
                }
                candidate["verification_status"] = (
                    "geometric_consistency_passed" if estimate["status"] == "geometrically_verified"
                    else "no_geometric_verification"
                )
            except (cv2.error, RuntimeError, ValueError) as error:
                logger.info("Local match failed for %s: %s", candidate["candidate_patch_id"], error)
                candidate["verification_status"] = "local_matching_failed"
            finally:
                del satellite_features, output
                gc.collect()
    finally:
        del extractor, matcher, query_features
        gc.collect()


def localize_image(
    query_image_id: int,
    query_path: str | Path,
    mode: str = "gps_free",
    gps_coordinates: tuple[float, float] | None = None,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    """Run bounded retrieval, optionally restricting it by explicit EXIF GPS mode."""
    started = time.perf_counter()
    image_path = Path(query_path)
    if not image_path.is_file():
        raise FileNotFoundError("The uploaded query image is no longer available.")
    if mode not in {"gps_free", "gps_assisted"}:
        raise ValueError("mode must be gps_free or gps_assisted")
    if (mode == "gps_assisted") != (gps_coordinates is not None):
        raise ValueError("GPS coordinates must be supplied only for GPS-assisted mode.")
    if not lock_acquired and not _inference_lock.acquire(blocking=False):
        raise LocalizationUnavailableError("Another localization request is already running.")
    try:
        candidates, paths = _load_index_and_candidates(image_path, gps_coordinates)
        if not candidates:
            raise LocalizationUnavailableError("The existing index returned no candidates.")
        _match_shortlist(image_path, candidates, paths)
        estimate = _estimate_candidate_consensus(candidates)
        verified = sum(candidate["estimated_image_center"].get("status") == "geometrically_verified" for candidate in candidates)
        for candidate in candidates:
            candidate.pop("_metadata", None)
            candidate.pop("_tile_path", None)
        return {
            "query_image_id": query_image_id,
            "mode": mode,
            "gps_assisted_filter": (
                "satellite parent footprints containing valid image EXIF GPS"
                if mode == "gps_assisted" else None
            ),
            "retrieval_configuration": {
                "query_preprocessing_px": 280,
                "initial_retrieval_top_k": 50,
                "one_ring_seed_count": 5,
                "candidate_budget": 75,
                "local_matching_shortlist": 5,
            },
            "localization_status": (
                estimate["status"] if estimate["status"] != "no_reliable_estimate" else "candidate_retrieval_only"
            ),
            "localization_estimate": estimate,
            "geometrically_verified_candidate_count": verified,
            "quality_control": QUALITY_THRESHOLDS.copy(),
            "precise_localization_claimed": False,
            "note": (
                "An estimate is reported only after spatially distributed RANSAC inliers support "
                "a query-to-satellite homography and the projected image center falls within the "
                "georeferenced patch. Oblique views, relief, and scene change can violate the "
                "planar homography assumption; this estimate is not a calibrated uncertainty."
            ),
            "processing_time_seconds": round(time.perf_counter() - started, 3),
            "candidates": candidates,
        }
    except (FileNotFoundError, LocalizationUnavailableError):
        raise
    except Exception as error:
        logger.exception("UAV-VisLoc inference failed for query image %s", query_image_id)
        raise LocalizationUnavailableError(
            "Visual localization could not complete. Check the cached model, index, and CPU memory."
        ) from error
    finally:
        if not lock_acquired:
            _inference_lock.release()


def reserve_localization_slot() -> bool:
    """Atomically reserve the one CPU/RAM-heavy inference slot for an API run."""
    return _inference_lock.acquire(blocking=False)


def release_localization_slot() -> None:
    _inference_lock.release()


def get_candidate_tile_path(tile_id: str) -> Path:
    """Resolve a known tile ID to its generated preview without trusting path input."""
    common, _selector = _phase3c_modules()
    _config, paths = common.load_config(PHASE3C_DIR / "index_config.yaml")
    with paths["tile_metadata"].open("r", encoding="utf-8-sig", newline="") as handle:
        row = next((item for item in csv.DictReader(handle) if item["tile_id"] == tile_id), None)
    if row is None:
        raise FileNotFoundError("Satellite candidate not found.")
    base = paths["satellite_tiles"].resolve()
    tile = (base / row["image_relative_path"]).resolve()
    try:
        tile.relative_to(base)
    except ValueError as error:
        raise FileNotFoundError("Satellite candidate path is invalid.") from error
    if not tile.is_file():
        raise FileNotFoundError("Satellite candidate preview is unavailable.")
    return tile
