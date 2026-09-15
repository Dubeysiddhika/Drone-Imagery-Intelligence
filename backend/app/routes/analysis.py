from fastapi import APIRouter


router = APIRouter()


@router.get("/")
def analysis_status():
    return {
        "message": "Analysis API is working"
    }