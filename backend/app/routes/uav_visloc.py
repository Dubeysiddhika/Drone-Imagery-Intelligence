"""UAV-VisLoc dataset metadata and bounded visual-localization inference APIs."""

import logging
import json
import math
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import DroneImage, ProcessingRun, UAVVisLocImageMatch, UAVVisLocRecord
from ..services.visual_localization import (
    LocalizationUnavailableError,
    PHASE3C_DIR,
    QUALITY_THRESHOLDS,
    get_candidate_tile_path,
    localize_image,
    release_localization_slot,
    reserve_localization_slot,
)
from .images import _dataset_match_dict, _uploaded_file_path, _valid_gps

router = APIRouter()
logger = logging.getLogger(__name__)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, a)))


def _attach_ground_truth_evaluation(result: dict, image: DroneImage, db: Session) -> None:
    """Compare an already-computed estimate to dataset GT after GPS-free inference."""
    row = db.query(UAVVisLocImageMatch).filter_by(image_id=image.id).first()
    match = _dataset_match_dict(row)
    ground_truth = ((match or {}).get("metadata") or {}).get("ground_truth") or {}
    estimate = result.get("localization_estimate") or {}
    valid_gt = (
        (match or {}).get("status") == "matched"
        and ground_truth.get("available") is True
        and isinstance(ground_truth.get("latitude"), (int, float))
        and isinstance(ground_truth.get("longitude"), (int, float))
        and math.isfinite(ground_truth["latitude"]) and math.isfinite(ground_truth["longitude"])
        and -90 <= ground_truth["latitude"] <= 90 and -180 <= ground_truth["longitude"] <= 180
    )
    valid_estimate = (
        estimate.get("available") is True
        and isinstance(estimate.get("latitude"), (int, float))
        and isinstance(estimate.get("longitude"), (int, float))
    )
    if not valid_gt:
        result["evaluation"] = {"available": False, "reason": "No valid matched dataset ground truth is available."}
    elif not valid_estimate:
        result["evaluation"] = {
            "available": False,
            "status": "localization_failed",
            "ground_truth_available": True,
            "ground_truth_latitude": ground_truth["latitude"],
            "ground_truth_longitude": ground_truth["longitude"],
            "reason": estimate.get("reason") or "No estimate passed geometric quality control.",
        }
    else:
        error_m = _haversine_meters(
            estimate["latitude"], estimate["longitude"],
            ground_truth["latitude"], ground_truth["longitude"],
        )
        result["evaluation"] = {
            "available": True,
            "metric": "haversine_ground_truth_error",
            "error_m": round(error_m, 3),
            "within_5m": error_m <= 5,
            "within_10m": error_m <= 10,
            "within_25m": error_m <= 25,
            "within_50m": error_m <= 50,
            "ground_truth_latitude": ground_truth["latitude"],
            "ground_truth_longitude": ground_truth["longitude"],
            "ground_truth_source": ground_truth.get("coordinate_source"),
            "note": "Evaluation only; dataset ground truth was not provided to GPS-free retrieval or geometric estimation.",
        }


@router.post("/localize/{image_id}", summary="Localize an uploaded drone image against the existing satellite index")
def localize_uploaded_image(
    image_id: int,
    mode: str = Query(default="gps_free", pattern="^(gps_free|gps_assisted|visual_only)$"),
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Query image not found.")
    run_mode = "gps_free" if mode == "visual_only" else mode
    gps_coordinates = None
    if run_mode == "gps_assisted":
        if not _valid_gps(image):
            raise HTTPException(
                status_code=422,
                detail="GPS-assisted localization requires valid latitude and longitude stored from this image's EXIF metadata.",
            )
        gps_coordinates = (float(image.latitude), float(image.longitude))
    if not reserve_localization_slot():
        raise HTTPException(
            status_code=409,
            detail="A UAV-VisLoc query is already processing. Wait for it to finish before starting another.",
        )
    started = time.perf_counter()
    try:
        run = ProcessingRun(
            image_id=image.id,
            pipeline="localization",
            mode=run_mode,
            status="processing",
        )
        db.add(run)
        db.commit()

        def mark_failed(message: str) -> None:
            run.status = "failed"
            run.processing_seconds = time.perf_counter() - started
            run.error_message = message[:2000]
            run.completed_at = datetime.utcnow()
            db.add(run)
            db.commit()

        try:
            query_path = _uploaded_file_path(image.filepath)
            result = localize_image(
                image.id,
                query_path,
                mode=run_mode,
                gps_coordinates=gps_coordinates,
                lock_acquired=True,
            )
            _attach_ground_truth_evaluation(result, image, db)
        except FileNotFoundError as error:
            mark_failed(str(error))
            raise HTTPException(status_code=404, detail=str(error)) from error
        except LocalizationUnavailableError as error:
            mark_failed(str(error))
            raise HTTPException(status_code=503, detail=str(error)) from error
        except Exception as error:
            logger.exception("Could not localize uploaded image %s", image_id)
            mark_failed("UAV-VisLoc inference failed unexpectedly.")
            raise HTTPException(
                status_code=500,
                detail="UAV-VisLoc inference failed unexpectedly.",
            ) from error
        run.status = "completed"
        run.processing_seconds = float(result.get("processing_time_seconds") or (time.perf_counter() - started))
        run.result_count = len(result.get("candidates", []))
        run.result_json = json.dumps(result, separators=(",", ":"), allow_nan=False)
        run.verified_count = sum(
            1 for candidate in result.get("candidates", [])
            if candidate.get("verification_status") == "geometric_consistency_passed"
        )
        run.completed_at = datetime.utcnow()
        db.add(run)
        db.commit()
        result["query_image_url"] = f"/api/images/{image.id}/preview"
        return result
    finally:
        release_localization_slot()


@router.get("/candidates/{tile_id}/preview", summary="Preview a satellite candidate patch")
def get_candidate_preview(tile_id: str):
    try:
        tile_path = get_candidate_tile_path(tile_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(tile_path, media_type="image/jpeg")


@router.get("/localization/status", summary="Check visual-localization artifact availability")
def get_localization_status():
    manifest = PHASE3C_DIR / "metadata" / "satellite_index_manifest.json"
    index = PHASE3C_DIR / "global_features" / "satellite_index.npz"
    return {
        "available": manifest.is_file() and index.is_file(),
        "index_manifest_available": manifest.is_file(),
        "descriptor_index_available": index.is_file(),
        "device": "cpu",
        "supported_modes": ["gps_free", "gps_assisted"],
        "geometric_quality_thresholds": QUALITY_THRESHOLDS,
        "gps_assisted_policy": "Restrict retrieval to satellite parent-map footprints containing the selected image's valid stored EXIF GPS; never fall back to GPS-free mode.",
        "note": "The multi-gigabyte SuperPoint cache is not loaded; local features are computed only for the top five retrieved candidates.",
    }


def record_to_dict(record: UAVVisLocRecord) -> dict:
    """Convert a dataset record to JSON-friendly fields."""
    return {
        "id": record.id,
        "relative_path": record.relative_path,
        "filename": record.filename,
        "capture_time_raw": record.capture_time_raw,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "height": record.height,
        "omega": record.omega,
        "kappa": record.kappa,
        "phi1": record.phi1,
        "phi2": record.phi2,
        "metadata_csv": record.metadata_csv,
    }


@router.get("/stats")
def get_dataset_stats(db: Session = Depends(get_db)):
    """Return dataset record count and metadata availability."""
    total = db.query(UAVVisLocRecord).count()

    orientation_available = db.query(UAVVisLocRecord).filter(
        UAVVisLocRecord.omega.isnot(None),
        UAVVisLocRecord.kappa.isnot(None),
        UAVVisLocRecord.phi1.isnot(None),
        UAVVisLocRecord.phi2.isnot(None),
    ).count()

    return {
        "dataset": "UAV-VisLoc",
        "total_records": total,
        "records_with_complete_orientation": orientation_available,
        "records_without_complete_orientation": (
            total - orientation_available
        ),
    }


@router.get("/records")
def list_dataset_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return a paginated list of dataset records."""
    query = db.query(UAVVisLocRecord)
    total = query.count()

    records = (
        query.order_by(UAVVisLocRecord.relative_path)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "records": [record_to_dict(record) for record in records],
    }


@router.get("/records/{record_id}")
def get_dataset_record(
    record_id: int,
    db: Session = Depends(get_db),
):
    """Return one UAV-VisLoc metadata record."""
    record = (
        db.query(UAVVisLocRecord)
        .filter(UAVVisLocRecord.id == record_id)
        .first()
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="UAV-VisLoc record not found",
        )

    return record_to_dict(record)
