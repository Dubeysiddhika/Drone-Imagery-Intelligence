"""Read-only API endpoints for UAV-VisLoc dataset metadata."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import UAVVisLocRecord

router = APIRouter()


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