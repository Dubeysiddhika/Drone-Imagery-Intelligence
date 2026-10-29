import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Detection, DroneImage
from ..services.detector import (
    InferenceError,
    InvalidImageError,
    ModelUnavailableError,
    detect_objects,
)
from ..services.model_registry import get_model_metadata


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
def analysis_status():
    return {
        "message": "Analysis API is working"
    }


@router.post(
    "/detect/{image_id}",
    summary="Detect objects in an uploaded image",
    description=(
        "Defaults to the existing two-class baseline. Set `model_version` to "
        "`visdrone10_yolo11n` to use the separate ten-class VisDrone model. "
        "Bounding boxes use source-image pixel coordinates in xyxy order, "
        "origin at the top-left."
    ),
)
def detect_image(
    image_id: int,
    db: Session = Depends(get_db),
    model_version: str | None = Query(
        default=None,
        description=(
            "Optional model selection: `baseline` (default) or "
            "`visdrone10_yolo11n`."
        ),
    ),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_path = Path(image.filepath)
    try:
        detections = detect_objects(image_path, model_version=model_version)
    except InvalidImageError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ModelUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except InferenceError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        logger.exception("Unexpected detection failure for image %s", image_id)
        raise HTTPException(
            status_code=500,
            detail="Image detection failed.",
        ) from error

    model_metadata = get_model_metadata(model_version)

    try:
        db.query(Detection).filter(
            Detection.image_id == image.id
        ).delete(synchronize_session=False)

        stored_detections = [
            Detection(
                image_id=image.id,
                class_id=detection["class_id"],
                class_name=detection["class_name"],
                confidence=detection["confidence"],
                x1=detection["x1"],
                y1=detection["y1"],
                x2=detection["x2"],
                y2=detection["y2"],
                model_name=detection.get("model_name", model_metadata["model_name"]),
                model_version=detection.get("model_version", model_metadata["model_version"]),
            )
            for detection in detections
        ]
        db.add_all(stored_detections)
        db.flush()

        response_detections = [
            {
                "id": detection.id,
                "class_id": detection.class_id,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "model_name": detection.model_name,
                "model_version": detection.model_version,
                "bbox": {
                    "x1": detection.x1,
                    "y1": detection.y1,
                    "x2": detection.x2,
                    "y2": detection.y2,
                },
            }
            for detection in stored_detections
        ]
        db.commit()
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Could not store detection results: {error}",
        ) from error

    return {
        "image_id": image.id,
        "model_name": model_metadata["model_name"],
        "model_version": model_metadata["model_version"],
        "classes": model_metadata["class_names"],
        "coordinate_system": "pixel_xyxy",
        "image": {
            "id": image.id,
            "filename": image.filename,
            "latitude": image.latitude,
            "longitude": image.longitude,
            "altitude": image.altitude,
            "captured_at": image.captured_at,
        },
        "detections": response_detections,
        "detection_count": len(response_detections),
    }


@router.get(
    "/detections/{image_id}",
    summary="Get detections saved for an image",
    description=(
        "Bounding boxes use source-image pixel coordinates in xyxy order, "
        "origin at the top-left."
    ),
)
def get_image_detections(
    image_id: int,
    db: Session = Depends(get_db),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    detections = (
        db.query(Detection)
        .filter(Detection.image_id == image.id)
        .order_by(Detection.id)
        .all()
    )

    filtered = [
        detection for detection in detections if detection.confidence >= min_confidence
    ]

    return {
        "image_id": image.id,
        "model_name": filtered[0].model_name if filtered else (detections[0].model_name if detections else None),
        "model_version": filtered[0].model_version if filtered else (detections[0].model_version if detections else None),
        "coordinate_system": "pixel_xyxy",
        "detection_count": len(filtered),
        "detections": [
            {
                "id": detection.id,
                "class_id": detection.class_id,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "model_name": detection.model_name,
                "model_version": detection.model_version,
                "bbox": {
                    "x1": detection.x1,
                    "y1": detection.y1,
                    "x2": detection.x2,
                    "y2": detection.y2,
                },
            }
            for detection in filtered
        ],
    }