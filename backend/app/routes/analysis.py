from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Detection, DroneImage
from ..services.detector import detect_objects


router = APIRouter()


@router.get("/")
def analysis_status():
    return {
        "message": "Analysis API is working"
    }


@router.post("/detect/{image_id}")
def detect_image(
    image_id: int,
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_path = Path(image.filepath)
    try:
        detections = detect_objects(image_path)
    except FileNotFoundError as error:
        status_code = 503 if "model weights" in str(error) else 404
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Image detection failed: {error}",
        ) from error

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


@router.get("/detections/{image_id}")
def get_image_detections(
    image_id: int,
    db: Session = Depends(get_db),
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

    return {
        "image_id": image.id,
        "detection_count": len(detections),
        "detections": [
            {
                "id": detection.id,
                "class_id": detection.class_id,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "bbox": {
                    "x1": detection.x1,
                    "y1": detection.y1,
                    "x2": detection.x2,
                    "y2": detection.y2,
                },
            }
            for detection in detections
        ],
    }