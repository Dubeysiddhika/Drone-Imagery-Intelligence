from fastapi import APIRouter


router = APIRouter()


@router.get("/")
def get_surveys():
    return {
        "message": "Surveys API is working"
    }