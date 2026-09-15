from fastapi import APIRouter


router = APIRouter()


@router.get("/stats")
def dashboard_stats():

    return {
        "total_surveys": 0,
        "images_processed": 0,
        "total_detections": 0,
        "analysis_complete": False
    }