"""Complete persisted image-intelligence views and downloadable reports."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Detection, DroneImage, ProcessingRun, UAVVisLocImageMatch
from ..services.detection_service import render_annotated_image
from ..services.dataset_registry import DEFAULT_DATASET_ROOT
from . import analysis, uav_visloc
from .images import _dataset_match_dict, _uploaded_file_path

router = APIRouter()


def _json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback


def _valid_coordinates(latitude, longitude) -> bool:
    return (
        isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))
        and math.isfinite(latitude) and math.isfinite(longitude)
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    )


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(min(1.0, value)))


def _build_intelligence(image_id: int, db: Session) -> dict:
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    match_row = db.query(UAVVisLocImageMatch).filter_by(image_id=image.id).first()
    dataset_match = _dataset_match_dict(match_row)
    dataset_record = (dataset_match or {}).get("metadata") or {}
    dataset_ground_truth = dataset_record.get("ground_truth") or {
        "available": False,
        "latitude": None,
        "longitude": None,
        "coordinate_reference_system": None,
        "coordinate_source": None,
    }

    detections = (
        db.query(Detection).filter(Detection.image_id == image.id).order_by(Detection.id).all()
    )
    detection_run = (
        db.query(ProcessingRun)
        .filter(ProcessingRun.image_id == image.id, ProcessingRun.pipeline == "detection")
        .order_by(ProcessingRun.started_at.desc(), ProcessingRun.id.desc())
        .first()
    )
    detection_run_result = _json(detection_run.result_json, {}) if detection_run else {}
    class_counts: dict[str, int] = {}
    for detection in detections:
        class_counts[detection.class_name] = class_counts.get(detection.class_name, 0) + 1

    localization_run = (
        db.query(ProcessingRun)
        .filter(ProcessingRun.image_id == image.id, ProcessingRun.pipeline == "localization")
        .order_by(ProcessingRun.started_at.desc(), ProcessingRun.id.desc())
        .first()
    )
    localization_result = _json(localization_run.result_json, None) if localization_run else None
    candidate_results = (localization_result or {}).get("candidates", [])

    expected_maps = {
        Path(value.strip()).stem.casefold()
        for value in str(dataset_record.get("satellite_map") or "").replace(",", ";").split(";")
        if value.strip()
    }
    ground_truth_rank = next((
        candidate.get("rank") for candidate in candidate_results
        if str(candidate.get("parent_satellite_map_id", "")).casefold() in expected_maps
    ), None)
    ground_truth_point = dataset_ground_truth
    candidate_distances = []
    if ground_truth_point.get("available") and _valid_coordinates(
        ground_truth_point.get("latitude"), ground_truth_point.get("longitude")
    ):
        for candidate in candidate_results:
            if _valid_coordinates(candidate.get("latitude"), candidate.get("longitude")):
                candidate_distances.append({
                    "rank": candidate.get("rank"),
                    "satellite_tile_id": candidate.get("satellite_tile_id"),
                    "satellite_candidate_center_distance_m": round(_haversine_meters(
                        ground_truth_point["latitude"], ground_truth_point["longitude"],
                        candidate["latitude"], candidate["longitude"],
                    ), 2),
                })

    try:
        image_path = _uploaded_file_path(image.filepath)
        stat = image_path.stat()
        with Image.open(image_path) as source:
            file_format = source.format
            actual_width, actual_height = source.size
    except HTTPException:
        image_path, stat, file_format, actual_width, actual_height = None, None, None, image.width, image.height

    image_metadata = {
        "image_id": image.id,
        "original_filename": image.filename,
        "file_format": file_format,
        "file_size_bytes": stat.st_size if stat else None,
        "width": image.width or actual_width,
        "height": image.height or actual_height,
        "exif_available": bool(image.exif_available),
        "camera_make": image.camera_make,
        "camera_model": image.camera_model,
        "focal_length_mm": image.focal_length,
        "orientation": image.orientation,
        "capture_time": image.captured_at.isoformat() if image.captured_at else None,
        "exif_gps": {
            "available": _valid_coordinates(image.latitude, image.longitude),
            "latitude": image.latitude if _valid_coordinates(image.latitude, image.longitude) else None,
            "longitude": image.longitude if _valid_coordinates(image.latitude, image.longitude) else None,
            "altitude_m": image.altitude,
            "coordinate_source": "image_exif" if _valid_coordinates(image.latitude, image.longitude) else None,
            "coordinate_reference_system": "EPSG:4326" if _valid_coordinates(image.latitude, image.longitude) else None,
        },
        "survey_id": image.survey_id,
    }
    detection_result = {
        "status": detection_run.status if detection_run else ("completed" if detections else "pending"),
        "count": len(detections),
        "per_class_counts": [{"class_name": name, "count": count} for name, count in sorted(class_counts.items())],
        "coordinate_system": "source_image_pixel_xyxy",
        "annotated_image_url": f"/api/images/{image.id}/annotated",
        "original_image_url": f"/api/images/{image.id}/preview",
        "model_name": detections[0].model_name if detections else detection_run_result.get("model_name"),
        "model_version": detections[0].model_version if detections else detection_run_result.get("model_version"),
        "processing_seconds": detection_run.processing_seconds if detection_run else None,
        "detections": [
            {
                "id": detection.id,
                "class_id": detection.class_id,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "bbox": {"x1": detection.x1, "y1": detection.y1, "x2": detection.x2, "y2": detection.y2},
                "model_name": detection.model_name,
                "model_version": detection.model_version,
            }
            for detection in detections
        ],
        "note": "YOLO boxes are image pixels and do not represent individual ground coordinates.",
    }
    if localization_run is None:
        localization = {"status": "not_run", "message": "No UAV-VisLoc run is stored for this image.", "candidates": []}
    elif localization_result is None:
        localization = {
            "status": localization_run.status,
            "message": localization_run.error_message,
            "mode": localization_run.mode,
            "processing_seconds": localization_run.processing_seconds,
            "candidates": [],
        }
    else:
        localization = {**localization_result, "status": localization_run.status}
    localization_estimate = localization.get("localization_estimate") or {}

    if not dataset_match:
        dataset_match = {"status": "not_checked", "method": None, "confidence": None, "metadata": None}
    dataset_metadata = dataset_record.get("source_fields") or {}
    dataset_metadata.update(dataset_record.get("consolidated_fields") or {})
    return {
        "image": image_metadata,
        "dataset_identity": {
            **{key: value for key, value in dataset_match.items() if key != "metadata"},
            "flight_sequence": dataset_match.get("flight_sequence"),
            "dataset_relative_path": dataset_match.get("dataset_relative_path"),
            "metadata_source_csv": dataset_record.get("metadata_csv"),
        },
        "dataset_metadata": dataset_metadata if dataset_match["status"] == "matched" else None,
        "geospatial": {
            "exif_coordinate": image_metadata["exif_gps"],
            "dataset_ground_truth": dataset_ground_truth,
            "predicted_uav_coordinate": {
                "available": localization_estimate.get("available") is True,
                "latitude": localization_estimate.get("latitude"),
                "longitude": localization_estimate.get("longitude"),
                "coordinate_source": localization_estimate.get("coordinate_source"),
                "status": localization_estimate.get("status", "not_available"),
                "reason": localization_estimate.get("reason"),
            },
            "localization_evaluation": localization.get("evaluation", {"available": False, "reason": "Localization has not been evaluated."}),
            "satellite_candidate_region_rank_for_ground_truth_map": ground_truth_rank,
            "satellite_candidate_center_offsets_from_ground_truth": candidate_distances,
            "candidate_offsets_are_predictions": False,
            "coordinate_reference_system": "EPSG:4326",
        },
        "detection": detection_result,
        "localization": localization,
        "processing": {
            "runs": [
                {
                    "id": run.id,
                    "pipeline": run.pipeline,
                    "mode": run.mode,
                    "status": run.status,
                    "processing_seconds": run.processing_seconds,
                    "result_count": run.result_count,
                    "verified_count": run.verified_count,
                    "error": run.error_message,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                for run in db.query(ProcessingRun).filter(ProcessingRun.image_id == image.id).order_by(ProcessingRun.started_at).all()
            ]
        },
    }


@router.get("/images/{image_id}", summary="Get complete persisted image intelligence")
def get_image_intelligence(image_id: int, db: Session = Depends(get_db)):
    return _build_intelligence(image_id, db)


@router.post("/images/{image_id}/process", summary="Run detection and eligible GPS-free UAV-VisLoc processing")
def process_image_intelligence(
    image_id: int,
    model_version: str = Query(default="visdrone10_yolo11n"),
    run_localization: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    detection_result = analysis.detect_image(image_id, db=db, model_version=model_version)
    match = db.query(UAVVisLocImageMatch).filter_by(image_id=image_id).first()
    localization_error = None
    if run_localization and match is not None and match.status == "matched":
        try:
            uav_visloc.localize_uploaded_image(image_id, mode="gps_free", db=db)
        except HTTPException as error:
            localization_error = {"status": "failed", "message": str(error.detail)}
    result = _build_intelligence(image_id, db)
    result["detection_run_response"] = detection_result
    if not run_localization:
        result["localization"] = {"status": "skipped_by_request", "candidates": []}
    elif match is None or match.status != "matched":
        result["localization"] = {
            "status": "not_applicable",
            "message": "Image was not verified as a UAV-VisLoc dataset image; no localization was started.",
            "candidates": [],
        }
    elif localization_error:
        result["localization"] = localization_error
    return result


@router.get("/images/{image_id}/export.json", summary="Download complete image intelligence JSON")
def export_image_intelligence_json(image_id: int, db: Session = Depends(get_db)):
    payload = json.dumps(_build_intelligence(image_id, db), indent=2, ensure_ascii=False)
    return StreamingResponse(BytesIO(payload.encode("utf-8")), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="image-{image_id}-intelligence.json"'
    })


@router.get("/images/{image_id}/export.csv", summary="Download image metadata and one row per stored detection")
def export_image_intelligence_csv(image_id: int, db: Session = Depends(get_db)):
    result = _build_intelligence(image_id, db)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[
        "image_id", "filename", "file_format", "file_size_bytes", "width", "height",
        "exif_available", "camera_make", "camera_model", "focal_length_mm", "orientation",
        "capture_time", "exif_gps_available", "exif_gps_latitude", "exif_gps_longitude",
        "exif_altitude_m", "survey_id", "flight_sequence", "dataset_match_status",
        "dataset_match_method", "dataset_match_confidence", "dataset_relative_path",
        "metadata_source_csv", "dataset_ground_truth_latitude", "dataset_ground_truth_longitude",
        "dataset_ground_truth_altitude_m", "dataset_capture_time", "dataset_heading_phi",
        "dataset_satellite_map", "dataset_metadata_json", "detection_status", "detection_count",
        "detection_classes_json", "detection_id", "class_id", "class_name", "confidence",
        "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2", "detection_model_name",
        "detection_model_version", "localization_status", "localization_mode",
        "predicted_latitude", "predicted_longitude", "predicted_coordinate_source",
        "localization_estimate_status", "ground_truth_error_m", "within_5m", "within_10m",
        "within_25m", "within_50m",
        "localization_candidate_count", "processing_runs_json",
    ])
    writer.writeheader()
    image = result["image"]
    gt = result["geospatial"]["dataset_ground_truth"]
    dataset = result["dataset_metadata"] or {}
    identity = result["dataset_identity"]
    base = {
        "image_id": image["image_id"],
        "filename": image["original_filename"],
        "file_format": image["file_format"],
        "file_size_bytes": image["file_size_bytes"],
        "width": image["width"],
        "height": image["height"],
        "exif_available": image["exif_available"],
        "camera_make": image["camera_make"],
        "camera_model": image["camera_model"],
        "focal_length_mm": image["focal_length_mm"],
        "orientation": image["orientation"],
        "capture_time": image["capture_time"],
        "exif_gps_available": image["exif_gps"]["available"],
        "exif_gps_latitude": image["exif_gps"].get("latitude"),
        "exif_gps_longitude": image["exif_gps"].get("longitude"),
        "exif_altitude_m": image["exif_gps"].get("altitude_m"),
        "survey_id": image["survey_id"],
        "flight_sequence": identity["flight_sequence"],
        "dataset_match_status": identity["status"],
        "dataset_match_method": identity["method"],
        "dataset_match_confidence": identity["confidence"],
        "dataset_relative_path": identity["dataset_relative_path"],
        "metadata_source_csv": identity["metadata_source_csv"],
        "dataset_ground_truth_latitude": gt.get("latitude"),
        "dataset_ground_truth_longitude": gt.get("longitude"),
        "dataset_ground_truth_altitude_m": dataset.get("height"),
        "dataset_capture_time": dataset.get("date", dataset.get("capture_time_raw")),
        "dataset_heading_phi": dataset.get("Phi1", dataset.get("phi1")),
        "dataset_satellite_map": dataset.get("satellite_map"),
        "dataset_metadata_json": json.dumps(dataset, ensure_ascii=False),
        "detection_status": result["detection"]["status"],
        "detection_count": result["detection"]["count"],
        "detection_classes_json": json.dumps(result["detection"]["per_class_counts"]),
        "localization_status": result["localization"].get("status"),
        "localization_mode": result["localization"].get("mode"),
        "predicted_latitude": result["geospatial"]["predicted_uav_coordinate"].get("latitude"),
        "predicted_longitude": result["geospatial"]["predicted_uav_coordinate"].get("longitude"),
        "predicted_coordinate_source": result["geospatial"]["predicted_uav_coordinate"].get("coordinate_source"),
        "localization_estimate_status": result["geospatial"]["predicted_uav_coordinate"].get("status"),
        "ground_truth_error_m": result["geospatial"]["localization_evaluation"].get("error_m"),
        "within_5m": result["geospatial"]["localization_evaluation"].get("within_5m"),
        "within_10m": result["geospatial"]["localization_evaluation"].get("within_10m"),
        "within_25m": result["geospatial"]["localization_evaluation"].get("within_25m"),
        "within_50m": result["geospatial"]["localization_evaluation"].get("within_50m"),
        "localization_candidate_count": len(result["localization"].get("candidates", [])),
        "processing_runs_json": json.dumps(result["processing"]["runs"]),
    }
    detections = result["detection"]["detections"] or [None]
    for detection in detections:
        row = dict(base)
        if detection is not None:
            bbox = detection["bbox"]
            row.update({
                "detection_id": detection["id"],
                "class_id": detection["class_id"],
                "class_name": detection["class_name"],
                "confidence": detection["confidence"],
                "bbox_x1": bbox["x1"], "bbox_y1": bbox["y1"],
                "bbox_x2": bbox["x2"], "bbox_y2": bbox["y2"],
                "detection_model_name": detection["model_name"],
                "detection_model_version": detection["model_version"],
            })
        writer.writerow(row)
    return StreamingResponse(BytesIO(output.getvalue().encode("utf-8-sig")), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="image-{image_id}-intelligence.csv"'
    })


def _pdf_page(title: str, lines: list[str], width=1240, height=1754) -> Image.Image:
    page = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 0, width, 175), fill=(11, 31, 51))
    draw.text((72, 58), "AEROVISION INTELLIGENCE", fill=(67, 211, 173))
    draw.text((72, 105), title, fill="white")
    y = 225
    for line in lines:
        text = str(line).encode("ascii", "replace").decode("ascii")
        while len(text) > 95:
            draw.text((72, y), text[:95], fill=(30, 48, 65))
            y += 36
            text = text[95:]
        draw.text((72, y), text, fill=(30, 48, 65))
        y += 38
        if y > height - 90:
            break
    return page


def _satellite_context_maps(dataset_record: dict, ground_truth: dict, candidates: list[dict]) -> list[tuple[str, Image.Image]]:
    """Render small, correctly georeferenced source-raster maps for the PDF."""
    flight = dataset_record.get("flight_sequence")
    consolidated = dataset_record.get("consolidated_fields") or {}
    map_value = dataset_record.get("satellite_map") or consolidated.get("satellite_map") or ""
    names = [item.strip() for item in str(map_value).replace(",", ";").split(";") if item.strip()]
    maps: list[tuple[str, Image.Image]] = []
    if not flight:
        return maps
    for name in names[:4]:
        source_path = (DEFAULT_DATASET_ROOT / str(flight) / name).resolve()
        try:
            source_path.relative_to(DEFAULT_DATASET_ROOT)
            with rasterio.open(source_path) as source:
                scale = min(1.0, 500 / source.width, 300 / source.height)
                output_width = max(1, round(source.width * scale))
                output_height = max(1, round(source.height * scale))
                band_count = min(3, source.count)
                values = source.read(
                    indexes=list(range(1, band_count + 1)),
                    out_shape=(band_count, output_height, output_width),
                    resampling=Resampling.bilinear,
                )
                if band_count >= 3:
                    channels = []
                    for channel in values[:3]:
                        low, high = np.nanpercentile(channel, (2, 98))
                        high = high if high > low else low + 1
                        channels.append(np.clip((channel - low) * (255 / (high - low)), 0, 255).astype(np.uint8))
                    raster_image = Image.fromarray(np.stack(channels, axis=-1), mode="RGB")
                else:
                    band = values[0]
                    low, high = np.nanpercentile(band, (2, 98))
                    high = high if high > low else low + 1
                    raster_image = Image.fromarray(np.clip((band - low) * (255 / (high - low)), 0, 255).astype(np.uint8), mode="L").convert("RGB")
                draw = ImageDraw.Draw(raster_image)
                transformer = Transformer.from_crs("EPSG:4326", source.crs, always_xy=True)
                points = []
                if ground_truth.get("available") and _valid_coordinates(ground_truth.get("latitude"), ground_truth.get("longitude")):
                    points.append((ground_truth["latitude"], ground_truth["longitude"], "GT", (234, 179, 8)))
                for candidate in candidates[:20]:
                    if _valid_coordinates(candidate.get("latitude"), candidate.get("longitude")):
                        points.append((candidate["latitude"], candidate["longitude"], str(candidate.get("rank", "")), (249, 115, 22)))
                for latitude, longitude, label, color in points:
                    x, y = transformer.transform(longitude, latitude)
                    row, column = source.index(x, y)
                    px = round(column * output_width / source.width)
                    py = round(row * output_height / source.height)
                    if 0 <= px < output_width and 0 <= py < output_height:
                        radius = 7 if label == "GT" else 4
                        draw.ellipse((px-radius, py-radius, px+radius, py+radius), fill=color, outline="white", width=2)
                        if label == "GT":
                            draw.text((px + 8, py - 8), "GT", fill=(255, 255, 255), stroke_width=2, stroke_fill=(20, 30, 40))
                maps.append((name, raster_image))
        except (OSError, ValueError, rasterio.errors.RasterioError):
            continue
    return maps


@router.get("/images/{image_id}/report.pdf", summary="Download a multi-page image intelligence PDF report")
def export_image_intelligence_pdf(image_id: int, db: Session = Depends(get_db)):
    result = _build_intelligence(image_id, db)
    image = db.query(DroneImage).filter(DroneImage.id == image_id).one()
    candidates = result["localization"].get("candidates", [])
    runs = result["processing"]["runs"]
    overview = result["image"]
    gt = result["geospatial"]["dataset_ground_truth"]
    page1 = _pdf_page("Image intelligence report", [
        f"Image: {overview['original_filename']} (ID {image_id})",
        f"Format / size: {overview['file_format']} / {overview['file_size_bytes']} bytes",
        f"Dimensions: {overview['width']} x {overview['height']} pixels",
        f"EXIF: available={overview['exif_available']}; camera={overview['camera_make']} {overview['camera_model']}; focal length={overview['focal_length_mm']} mm",
        f"EXIF capture time: {overview['capture_time']}; orientation={overview['orientation']}",
        f"EXIF GPS: {overview['exif_gps']}",
        f"Dataset match: {result['dataset_identity']}",
        f"Flight metadata source: {result['dataset_identity']['metadata_source_csv']}",
        f"Dataset ground truth (EPSG:4326): available={gt.get('available')}, latitude={gt.get('latitude')}, longitude={gt.get('longitude')}, altitude={((result['dataset_metadata'] or {}).get('height'))}",
        f"Full UAV-VisLoc dataset fields: {json.dumps(result['dataset_metadata'], ensure_ascii=True)}",
    ])
    detections = result["detection"]["detections"]
    det_lines = [
        f"Detection summary: {result['detection']['count']} objects; class counts={result['detection']['per_class_counts']}",
        "Bounding boxes are image-space xyxy pixels, not ground coordinates.",
        *[
            f"#{d['id']} {d['class_name']} class_id={d['class_id']} confidence={d['confidence']:.4f} bbox={d['bbox']}"
            for d in detections[:28]
        ],
    ]
    page2 = _pdf_page("Object detection", det_lines)
    if detections:
        try:
            path = _uploaded_file_path(image.filepath)
            annotation_bytes = render_annotated_image(path, [
                {**d["bbox"], "class_name": d["class_name"], "confidence": d["confidence"]}
                for d in detections
            ])
            with Image.open(BytesIO(annotation_bytes)) as annotated:
                annotated.thumbnail((1080, 740))
                page2.paste(annotated, ((1240 - annotated.width) // 2, 965))
        except (OSError, HTTPException, ValueError):
            pass
    loc_lines = [
        f"Localization status={result['localization'].get('status')}, mode={result['localization'].get('mode')}, processing={result['localization'].get('processing_time_seconds')} sec",
        f"Predicted UAV image-center coordinate={result['geospatial']['predicted_uav_coordinate']}",
        f"Ground-truth evaluation={result['geospatial']['localization_evaluation']}",
        f"Ground-truth satellite region rank: {result['geospatial']['satellite_candidate_region_rank_for_ground_truth_map']}",
        "Candidate patch centers and homography-projected image-center estimates are separate values.",
        *[
            f"Rank {c.get('rank')} {c.get('satellite_tile_id')} similarity={c.get('similarity_score')} matches={c.get('local_feature_match_count')} inliers={c.get('ransac_inlier_count')} ratio={c.get('inlier_ratio')} status={c.get('verification_status')} center={c.get('latitude')},{c.get('longitude')}"
            for c in candidates[:12]
        ],
        f"Candidate previews show the first 12 of {len(candidates)} returned patches; orange dots below are candidate patch centers and yellow marks dataset ground truth.",
        f"Processing history: {json.dumps(runs, ensure_ascii=True)}",
        "Ground-truth error is evaluation only. Ground truth is not provided to GPS-free retrieval or geometric estimation.",
    ]
    page3 = _pdf_page("Visual localization and processing", loc_lines)
    source_record = {
        "flight_sequence": result["dataset_identity"].get("flight_sequence"),
        "satellite_map": (result["dataset_metadata"] or {}).get("satellite_map"),
    }
    context_maps = _satellite_context_maps(source_record, gt, candidates)
    draw = ImageDraw.Draw(page3)
    for index, (name, map_image) in enumerate(context_maps):
        column, row = index % 2, index // 2
        x = 70 + column * 580
        y = 1080 + row * 320
        page3.paste(map_image, (x, y))
        draw.text((x, y + map_image.height + 5), f"Satellite raster {name} (native CRS transformed from WGS84)", fill=(30, 48, 65))
    output = BytesIO()
    page1.save(output, format="PDF", save_all=True, append_images=[page2, page3], resolution=150)
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="image-{image_id}-intelligence-report.pdf"'
    })
