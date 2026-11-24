from io import BytesIO
import json
import logging
import shutil
import uuid
import math
import os
from datetime import date, datetime, time, timedelta

from pathlib import Path

from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile
)

from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from ..config import PROJECT_ROOT, resolve_project_path
from ..models.database import get_db
from ..models.models import Detection, DroneImage, Survey, UAVVisLocImageMatch
from ..services.detector import InvalidImageError, validate_image

from ..services.metadata import (
    extract_metadata
)
from ..services.detection_service import render_annotated_image
from ..services.dataset_registry import identify_dataset_image


router = APIRouter()
logger = logging.getLogger(__name__)


def _dataset_match_dict(match: UAVVisLocImageMatch | None) -> dict | None:
    if match is None:
        return None
    try:
        metadata = json.loads(match.metadata_json) if match.metadata_json else None
    except (TypeError, ValueError):
        metadata = None
    return {
        "status": match.status,
        "method": match.match_method,
        "confidence": match.match_confidence,
        "flight_sequence": match.flight_sequence,
        "dataset_relative_path": match.dataset_relative_path,
        "metadata": metadata,
    }


def _valid_gps(image: DroneImage) -> bool:
    return (
        image.latitude is not None and image.longitude is not None
        and math.isfinite(image.latitude) and math.isfinite(image.longitude)
        and -90 <= image.latitude <= 90 and -180 <= image.longitude <= 180
    )


def _image_response(image: DroneImage, metadata=None):
    if metadata is None:
        try:
            metadata = extract_metadata(str(_uploaded_file_path(image.filepath)))
        except HTTPException:
            metadata = {
                "camera_make": None,
                "camera_model": None,
                "width": None,
                "height": None,
                "exif_available": False,
                "gps_available": False,
                "orientation": None,
                "focal_length": None,
            }

    return {
        "image_id": image.id,
        "id": image.id,
        "filename": image.filename,
        "latitude": image.latitude,
        "longitude": image.longitude,
        "gps_available": image.latitude is not None and image.longitude is not None,
        "altitude": image.altitude,
        "capture_time": image.captured_at,
        "captured_at": image.captured_at,
        "uploaded_at": image.uploaded_at,
        "detection_count": 0,
        "camera_make": image.camera_make or metadata["camera_make"],
        "camera_model": image.camera_model or metadata["camera_model"],
        "width": image.width or metadata["width"],
        "height": image.height or metadata["height"],
        "exif_available": image.exif_available if image.exif_available is not None else metadata["exif_available"],
        "orientation": image.orientation if image.orientation is not None else metadata.get("orientation"),
        "focal_length": image.focal_length if image.focal_length is not None else metadata.get("focal_length"),
        "survey_id": image.survey_id,
    }


def _uploaded_file_path(filepath: str) -> Path:
    """Resolve only files inside the application upload directory."""
    upload_root = UPLOAD_DIR.resolve()
    try:
        image_path = Path(filepath).resolve(strict=True)
        image_path.relative_to(upload_root)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail="Image file not found") from error
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")
    return image_path


# --------------------------------------------------
# Upload directory
# --------------------------------------------------

BASE_DIR = PROJECT_ROOT
UPLOAD_DIR = resolve_project_path(
    os.environ.get("UPLOAD_DIR"),
    "backend/uploads",
)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Supported image formats
# --------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff"
}


# --------------------------------------------------
# Upload image
# --------------------------------------------------

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    survey_id: int | None = Form(default=None),
    db: Session = Depends(get_db)
):

    # Check filename
    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Filename is missing"
        )


    extension = Path(
        file.filename
    ).suffix.lower()


    # Check image format
    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Use JPG, JPEG, PNG, TIFF."
            )
        )


    # Create unique filename
    unique_filename = (
        f"{uuid.uuid4()}"
        f"{extension}"
    )


    destination = (
        UPLOAD_DIR
        / unique_filename
    )


    # Save uploaded file
    with destination.open("wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    try:
        validate_image(destination)
    except InvalidImageError as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    # Extract metadata
    metadata = extract_metadata(
        str(destination)
    )

    survey = None
    if survey_id is not None:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        if survey is None:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=404, detail="Survey not found")


    # Create database record
    image = DroneImage(

        filename=file.filename,

        filepath=str(destination),

        latitude=metadata[
            "latitude"
        ],

        longitude=metadata[
            "longitude"
        ],

        altitude=metadata[
            "altitude"
        ],

        captured_at=metadata["captured_at"],
        orientation=metadata["orientation"],
        focal_length=metadata["focal_length"],
        camera_make=metadata["camera_make"],
        camera_model=metadata["camera_model"],
        width=metadata["width"],
        height=metadata["height"],
        exif_available=metadata["exif_available"],
        survey_id=survey.id if survey else None,
    )


    db.add(image)
    db.flush()

    try:
        match_result = await run_in_threadpool(
            identify_dataset_image, destination, file.filename
        )
    except Exception:
        logger.exception("UAV-VisLoc dataset matching failed for uploaded image %s", file.filename)
        match_result = {"status": "error", "method": None, "confidence": None, "record": None}

    matched_record = match_result.get("record") if match_result.get("status") == "matched" else None
    match = UAVVisLocImageMatch(
        image_id=image.id,
        status=match_result.get("status", "not_matched"),
        match_method=match_result.get("method"),
        match_confidence=match_result.get("confidence"),
        flight_sequence=matched_record.get("flight_sequence") if matched_record else None,
        dataset_relative_path=matched_record.get("dataset_image_path") if matched_record else None,
        metadata_json=json.dumps(matched_record, separators=(",", ":")) if matched_record else None,
    )
    db.add(match)
    db.commit()

    db.refresh(image)


    # Return result
    return {

        "success": True,

        "message":
            "Image uploaded successfully",

        "image": _image_response(image, metadata),
        "dataset_match": _dataset_match_dict(match),
    }


# --------------------------------------------------
# Get all images
# --------------------------------------------------

@router.get("/")
def get_images(
    db: Session = Depends(get_db)
):

    images = (
        db.query(DroneImage)
        .order_by(
            DroneImage.uploaded_at.desc()
        )
        .all()
    )

    image_ids = [image.id for image in images]
    detection_counts = {}
    if image_ids:
        detection_counts = dict(
            db.query(Detection.image_id, func.count(Detection.id))
            .filter(Detection.image_id.in_(image_ids))
            .group_by(Detection.image_id)
            .all()
        )

    return [
        {
            **_image_response(image),
            "detection_count": detection_counts.get(image.id, 0),
        }
        for image in images
    ]


# --------------------------------------------------
# Get one image
# --------------------------------------------------

@router.get("/geospatial", summary="List image GPS locations and unlocated image metadata")
def get_geospatial_images(
    survey_id: int | None = Query(default=None, gt=0),
    image_id: int | None = Query(default=None, gt=0),
    class_name: str | None = Query(default=None, min_length=1),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    """Return valid image capture points and a separate collection without GPS."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")

    query = db.query(DroneImage, Survey.name).outerjoin(Survey, Survey.id == DroneImage.survey_id)
    if survey_id is not None:
        query = query.filter(DroneImage.survey_id == survey_id)
    if image_id is not None:
        query = query.filter(DroneImage.id == image_id)
    if date_from is not None:
        query = query.filter(DroneImage.uploaded_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.filter(DroneImage.uploaded_at < datetime.combine(date_to + timedelta(days=1), time.min))
    image_rows = query.order_by(DroneImage.uploaded_at.desc(), DroneImage.id.desc()).all()
    images = [image for image, _survey_name in image_rows]
    image_ids = [image.id for image in images]
    grouped: dict[int, list[dict[str, object]]] = {}
    if image_ids:
        rows = (
            db.query(Detection.image_id, Detection.class_name, func.count(Detection.id))
            .filter(Detection.image_id.in_(image_ids))
            .group_by(Detection.image_id, Detection.class_name)
            .all()
        )
        for detected_image_id, detected_class, count in rows:
            grouped.setdefault(detected_image_id, []).append(
                {"class_name": detected_class, "count": count}
            )

    normalized_class = class_name.strip().casefold() if class_name else None
    located_images = []
    unlocated_images = []
    for image, survey_name in image_rows:
        detected_classes = sorted(
            grouped.get(image.id, []),
            key=lambda entry: str(entry["class_name"]).casefold(),
        )
        if normalized_class and not any(
            str(entry["class_name"]).casefold() == normalized_class
            for entry in detected_classes
        ):
            continue
        gps_available = _valid_gps(image)
        record = {
            "image_id": image.id,
            "survey_id": image.survey_id,
            "survey_name": survey_name,
            "gps_available": gps_available,
            "latitude": image.latitude if gps_available else None,
            "longitude": image.longitude if gps_available else None,
            "altitude": image.altitude,
            "filename": image.filename,
            "captured_at": image.captured_at,
            "uploaded_at": image.uploaded_at,
            "detection_count": sum(int(entry["count"]) for entry in detected_classes),
            "detected_classes": detected_classes,
            "original_image_url": f"/api/images/{image.id}/preview",
            "annotated_image_url": f"/api/images/{image.id}/annotated",
            "coordinate_meaning": "image_capture_point",
            "coordinate_reference_system": "EPSG:4326",
        }
        (located_images if gps_available else unlocated_images).append(record)

    available_classes = [
        row[0] for row in db.query(Detection.class_name).distinct().order_by(Detection.class_name).all()
    ]
    return {
        "total": len(located_images),
        "located_total": len(located_images),
        "images": located_images,
        "located_images": located_images,
        "unlocated_images": unlocated_images,
        "unlocated_total": len(unlocated_images),
        "available_classes": available_classes,
    }

@router.get("/{image_id}")
def get_image(
    image_id: int,
    db: Session = Depends(get_db)
):

    image = (
        db.query(DroneImage)
        .filter(
            DroneImage.id == image_id
        )
        .first()
    )


    if not image:

        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    detection_count = db.query(Detection).filter(
        Detection.image_id == image.id
    ).count()
    return {
        **_image_response(image),
        "detection_count": detection_count,
        "dataset_match": _dataset_match_dict(
            db.query(UAVVisLocImageMatch).filter(UAVVisLocImageMatch.image_id == image.id).first()
        ),
    }


@router.get("/{image_id}/annotated", summary="Get image rendered with its saved detections")
def get_annotated_image(
    image_id: int,
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    image_path = _uploaded_file_path(image.filepath)
    detections = (
        db.query(Detection)
        .filter(Detection.image_id == image.id)
        .order_by(Detection.id)
        .all()
    )
    payload = render_annotated_image(
        image_path,
        [
            {
                "x1": item.x1,
                "y1": item.y1,
                "x2": item.x2,
                "y2": item.y2,
                "class_name": item.class_name,
                "confidence": item.confidence,
            }
            for item in detections
        ],
    )
    return StreamingResponse(BytesIO(payload), media_type="image/jpeg")


@router.get("/{image_id}/preview", summary="Get an uploaded image preview")
def get_image_preview(
    image_id: int,
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_path = _uploaded_file_path(image.filepath)
    output = BytesIO()
    try:
        with Image.open(image_path) as source:
            source.thumbnail((2048, 2048))
            source.convert("RGB").save(output, format="JPEG", quality=88)
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise HTTPException(
            status_code=415,
            detail="Stored image cannot be converted to a preview.",
        ) from error

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )
