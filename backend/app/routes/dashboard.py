from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Survey, DroneImage, Detection

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