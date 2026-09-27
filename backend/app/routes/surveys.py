from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Survey

router = APIRouter()


@router.post("/")
def create_survey(
    name: str,
    description: str = "",
    db: Session = Depends(get_db)
):
    survey = Survey(
        name=name,
        description=description
    )

    db.add(survey)
    db.commit()
    db.refresh(survey)

    return survey


@router.get("/")
def get_surveys(
    db: Session = Depends(get_db)
):
    surveys = (
        db.query(Survey)
        .order_by(Survey.created_at.desc())
        .all()
    )

    return surveys