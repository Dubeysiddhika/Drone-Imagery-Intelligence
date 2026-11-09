from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Survey, DroneImage, Detection
from .images import _image_response

router = APIRouter()


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db)
):
    surveys = db.query(Survey).count()
    images = db.query(DroneImage).count()
    detections = db.query(Detection).count()

    return {
        "total_surveys": surveys,
        "images_processed": images,
        "total_detections": detections,
        "analysis_complete": images > 0
    }


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
):
    total_images = db.query(DroneImage).count()
    total_surveys = db.query(Survey).count()
    total_detections = db.query(Detection).count()
    average_confidence = db.query(func.avg(Detection.confidence)).scalar()

    grouped_classes = (
        db.query(Detection.class_name, func.count(Detection.id))
        .group_by(Detection.class_name)
        .order_by(func.count(Detection.id).desc(), Detection.class_name)
        .all()
    )
    class_counts = [
        {"class_name": class_name, "count": count}
        for class_name, count in grouped_classes
    ]
    class_totals = {
        class_name.lower(): count for class_name, count in grouped_classes
    }
    pedestrian_count = sum(
        class_totals.get(name, 0) for name in ("pedestrian", "people")
    )
    vehicle_classes = (
        "car",
        "van",
        "truck",
        "tricycle",
        "awning-tricycle",
        "bus",
        "motor",
        "vehicle",
    )
    vehicle_count = sum(class_totals.get(name, 0) for name in vehicle_classes)

    recent_images = (
        db.query(DroneImage)
        .order_by(DroneImage.uploaded_at.desc(), DroneImage.id.desc())
        .limit(8)
        .all()
    )
    recent_image_ids = [image.id for image in recent_images]
    image_detection_counts = {}
    if recent_image_ids:
        image_detection_counts = dict(
            db.query(Detection.image_id, func.count(Detection.id))
            .filter(Detection.image_id.in_(recent_image_ids))
            .group_by(Detection.image_id)
            .all()
        )

    recent_activity_rows = (
        db.query(Detection, DroneImage.filename)
        .join(DroneImage, Detection.image_id == DroneImage.id)
        .order_by(Detection.created_at.desc(), Detection.id.desc())
        .limit(10)
        .all()
    )

    latest_detection = (
        db.query(Detection)
        .filter(Detection.model_version.isnot(None))
        .order_by(Detection.created_at.desc(), Detection.id.desc())
        .first()
    )

    return {
        "total_images": total_images,
        "total_surveys": total_surveys,
        "total_detections": total_detections,
        "pedestrian_count": pedestrian_count,
        "vehicle_count": vehicle_count,
        "average_confidence": (
            float(average_confidence) if average_confidence is not None else None
        ),
        "class_counts": class_counts,
        "category_definitions": {
            "pedestrians": ["pedestrian", "people"],
            "vehicles": list(vehicle_classes),
        },
        "model_name": latest_detection.model_name if latest_detection else None,
        "model_version": latest_detection.model_version if latest_detection else None,
        "recent_images": [
            {
                **_image_response(image),
                "detection_count": image_detection_counts.get(image.id, 0),
            }
            for image in recent_images
        ],
        "recent_activity": [
            {
                "id": detection.id,
                "image_id": detection.image_id,
                "filename": filename,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "created_at": detection.created_at,
                "model_name": detection.model_name,
                "model_version": detection.model_version,
            }
            for detection, filename in recent_activity_rows
        ],
    }