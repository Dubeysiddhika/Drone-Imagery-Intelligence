from datetime import date, datetime, time, timedelta
import json
import statistics

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import Detection, DroneImage, ProcessingRun, Survey, UAVVisLocImageMatch
from .images import _image_response

router = APIRouter()


def _image_query(db: Session, survey_id: int | None, date_from: date | None, date_to: date | None):
    query = db.query(DroneImage)
    if survey_id is not None:
        query = query.filter(DroneImage.survey_id == survey_id)
    if date_from is not None:
        query = query.filter(DroneImage.uploaded_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.filter(DroneImage.uploaded_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return query


def _apply_run_filters(query, survey_id: int | None, date_from: date | None, date_to: date | None):
    query = query.join(DroneImage, ProcessingRun.image_id == DroneImage.id)
    if survey_id is not None:
        query = query.filter(DroneImage.survey_id == survey_id)
    if date_from is not None:
        query = query.filter(DroneImage.uploaded_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.filter(DroneImage.uploaded_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return query


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    surveys = db.query(Survey).count()
    images = db.query(DroneImage).count()
    detections = db.query(Detection).count()
    processed_image_ids = db.query(Detection.image_id).union(
        db.query(ProcessingRun.image_id).filter(
            ProcessingRun.pipeline == "detection", ProcessingRun.status == "completed"
        )
    ).subquery()
    images_processed = db.query(func.count()).select_from(processed_image_ids).scalar() or 0
    return {
        "total_surveys": surveys,
        "images_processed": images_processed,
        "total_detections": detections,
        "analysis_complete": images > 0 and images_processed >= images,
    }


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    survey_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")

    images_query = _image_query(db, survey_id, date_from, date_to)
    image_ids_query = images_query.with_entities(DroneImage.id).statement
    total_images = images_query.count()
    total_detections = db.query(Detection).filter(Detection.image_id.in_(image_ids_query)).count()
    total_surveys = db.query(func.count(func.distinct(DroneImage.survey_id))).filter(
        DroneImage.id.in_(image_ids_query), DroneImage.survey_id.isnot(None)
    ).scalar() or 0
    if survey_id is not None and total_images == 0 and db.query(Survey.id).filter(Survey.id == survey_id).first():
        total_surveys = 1

    detection_query = db.query(Detection).filter(Detection.image_id.in_(image_ids_query))
    average_confidence = detection_query.with_entities(func.avg(Detection.confidence)).scalar()
    grouped_classes = (
        detection_query.with_entities(Detection.class_name, func.count(Detection.id))
        .group_by(Detection.class_name)
        .order_by(func.count(Detection.id).desc(), Detection.class_name)
        .all()
    )
    class_counts = [{"class_name": name, "count": count} for name, count in grouped_classes]
    class_totals = {name.lower(): count for name, count in grouped_classes}
    pedestrian_count = sum(class_totals.get(name, 0) for name in ("pedestrian", "people"))
    vehicle_classes = ("car", "van", "truck", "tricycle", "awning-tricycle", "bus", "motor", "vehicle")
    vehicle_count = sum(class_totals.get(name, 0) for name in vehicle_classes)

    confidence_bins = [
        ("0-49%", Detection.confidence < 0.5),
        ("50-69%", (Detection.confidence >= 0.5) & (Detection.confidence < 0.7)),
        ("70-89%", (Detection.confidence >= 0.7) & (Detection.confidence < 0.9)),
        ("90-100%", Detection.confidence >= 0.9),
    ]
    confidence_distribution = [
        {"range": label, "count": detection_query.filter(condition).count()}
        for label, condition in confidence_bins
    ]

    gps_available = images_query.filter(
        DroneImage.latitude.isnot(None), DroneImage.longitude.isnot(None),
        DroneImage.latitude >= -90, DroneImage.latitude <= 90,
        DroneImage.longitude >= -180, DroneImage.longitude <= 180,
    ).count()

    processed_image_ids = db.query(Detection.image_id).filter(
        Detection.image_id.in_(image_ids_query)
    ).union(
        db.query(ProcessingRun.image_id).filter(
            ProcessingRun.image_id.in_(image_ids_query),
            ProcessingRun.pipeline == "detection", ProcessingRun.status == "completed",
        )
    ).subquery()
    completed_detection_images = db.query(func.count()).select_from(processed_image_ids).scalar() or 0

    survey_rows = (
        db.query(
            Survey.id, Survey.name,
            func.count(func.distinct(DroneImage.id)).label("image_count"),
            func.count(Detection.id).label("detection_count"),
            func.sum(case((
                DroneImage.latitude.isnot(None) & DroneImage.longitude.isnot(None)
                & (DroneImage.latitude >= -90) & (DroneImage.latitude <= 90)
                & (DroneImage.longitude >= -180) & (DroneImage.longitude <= 180), 1
            ), else_=0)).label("gps_image_count"),
        )
        .join(DroneImage, DroneImage.survey_id == Survey.id)
        .outerjoin(Detection, Detection.image_id == DroneImage.id)
        .filter(DroneImage.id.in_(image_ids_query))
        .group_by(Survey.id, Survey.name)
        .order_by(Survey.name)
        .all()
    )
    survey_stats = [
        {"survey_id": row.id, "survey_name": row.name, "image_count": row.image_count,
         "detection_count": row.detection_count, "gps_image_count": row.gps_image_count or 0}
        for row in survey_rows
    ]

    successful_localization = _apply_run_filters(db.query(ProcessingRun), survey_id, date_from, date_to).filter(
        ProcessingRun.pipeline == "localization", ProcessingRun.status == "completed"
    )
    localization_total = _apply_run_filters(db.query(ProcessingRun), survey_id, date_from, date_to).filter(
        ProcessingRun.pipeline == "localization"
    ).count()
    localization_successes = successful_localization.count()
    localization_verified = successful_localization.with_entities(func.coalesce(func.sum(ProcessingRun.verified_count), 0)).scalar() or 0
    localization_candidates = successful_localization.with_entities(func.coalesce(func.sum(ProcessingRun.result_count), 0)).scalar() or 0
    localization_payloads = []
    for run in successful_localization.all():
        try:
            localization_payloads.append(json.loads(run.result_json or "{}"))
        except (TypeError, ValueError):
            localization_payloads.append({})
    localization_estimates = [
        payload.get("localization_estimate") for payload in localization_payloads
        if (payload.get("localization_estimate") or {}).get("available") is True
    ]
    localization_errors = [
        float(payload["evaluation"]["error_m"])
        for payload in localization_payloads
        if (payload.get("evaluation") or {}).get("available") is True
        and isinstance(payload["evaluation"].get("error_m"), (int, float))
    ]
    localization_evaluation = {
        "estimated_images": len(localization_estimates),
        "evaluated_images": len(localization_errors),
        "estimate_success_rate": len(localization_estimates) / localization_total if localization_total else None,
        "unestimated_runs": max(localization_total - len(localization_estimates), 0),
        "mean_error_m": statistics.mean(localization_errors) if localization_errors else None,
        "median_error_m": statistics.median(localization_errors) if localization_errors else None,
        "within_5m_percent": 100 * sum(error <= 5 for error in localization_errors) / len(localization_errors) if localization_errors else None,
        "within_10m_percent": 100 * sum(error <= 10 for error in localization_errors) / len(localization_errors) if localization_errors else None,
        "within_25m_percent": 100 * sum(error <= 25 for error in localization_errors) / len(localization_errors) if localization_errors else None,
        "within_50m_percent": 100 * sum(error <= 50 for error in localization_errors) / len(localization_errors) if localization_errors else None,
        "sample_size": len(localization_errors),
        "note": "Metrics use persisted estimates and matched dataset ground truth; ground truth is excluded from GPS-free inference.",
    }
    per_flight_rows = (
        _apply_run_filters(db.query(ProcessingRun, UAVVisLocImageMatch.flight_sequence), survey_id, date_from, date_to)
        .outerjoin(UAVVisLocImageMatch, UAVVisLocImageMatch.image_id == ProcessingRun.image_id)
        .filter(ProcessingRun.pipeline == "localization")
        .all()
    )
    flight_groups: dict[str, list[dict]] = {}
    for run, flight_sequence in per_flight_rows:
        key = flight_sequence or "unmatched"
        try:
            payload = json.loads(run.result_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        flight_groups.setdefault(key, []).append(payload)
    per_flight_localization = []
    for flight_sequence, payloads in sorted(flight_groups.items()):
        errors = [
            float(payload["evaluation"]["error_m"])
            for payload in payloads
            if (payload.get("evaluation") or {}).get("available") is True
            and isinstance(payload["evaluation"].get("error_m"), (int, float))
        ]
        estimates = sum((payload.get("localization_estimate") or {}).get("available") is True for payload in payloads)
        per_flight_localization.append({
            "flight_sequence": flight_sequence,
            "localization_runs": len(payloads),
            "estimated_images": estimates,
            "failed_or_unestimated_images": len(payloads) - estimates,
            "evaluated_images": len(errors),
            "mean_error_m": statistics.mean(errors) if errors else None,
            "median_error_m": statistics.median(errors) if errors else None,
            "within_5m_percent": 100 * sum(error <= 5 for error in errors) / len(errors) if errors else None,
            "within_10m_percent": 100 * sum(error <= 10 for error in errors) / len(errors) if errors else None,
            "within_25m_percent": 100 * sum(error <= 25 for error in errors) / len(errors) if errors else None,
            "within_50m_percent": 100 * sum(error <= 50 for error in errors) / len(errors) if errors else None,
        })
    localization_evaluation["per_flight"] = per_flight_localization

    run_stats = {}
    for pipeline in ("detection", "localization"):
        pipeline_query = _apply_run_filters(db.query(ProcessingRun), survey_id, date_from, date_to).filter(
            ProcessingRun.pipeline == pipeline, ProcessingRun.status == "completed",
            ProcessingRun.processing_seconds.isnot(None),
        )
        run_stats[pipeline] = {
            "completed_runs": pipeline_query.count(),
            "mean_seconds": pipeline_query.with_entities(func.avg(ProcessingRun.processing_seconds)).scalar(),
            "min_seconds": pipeline_query.with_entities(func.min(ProcessingRun.processing_seconds)).scalar(),
            "max_seconds": pipeline_query.with_entities(func.max(ProcessingRun.processing_seconds)).scalar(),
        }
    for stats in run_stats.values():
        for key in ("mean_seconds", "min_seconds", "max_seconds"):
            if stats[key] is not None:
                stats[key] = float(stats[key])

    recent_images = images_query.order_by(DroneImage.uploaded_at.desc(), DroneImage.id.desc()).limit(8).all()
    recent_image_ids = [image.id for image in recent_images]
    counts = dict(
        db.query(Detection.image_id, func.count(Detection.id))
        .filter(Detection.image_id.in_(recent_image_ids))
        .group_by(Detection.image_id).all()
    ) if recent_image_ids else {}
    recent_activity_rows = (
        db.query(Detection, DroneImage.filename)
        .join(DroneImage, Detection.image_id == DroneImage.id)
        .filter(Detection.image_id.in_(image_ids_query))
        .order_by(Detection.created_at.desc(), Detection.id.desc()).limit(10).all()
    )
    latest_detection = (
        detection_query.filter(Detection.model_version.isnot(None))
        .order_by(Detection.created_at.desc(), Detection.id.desc()).first()
    )
    recent_runs = (
        _apply_run_filters(db.query(ProcessingRun, DroneImage.filename), survey_id, date_from, date_to)
        .order_by(ProcessingRun.started_at.desc(), ProcessingRun.id.desc()).limit(10).all()
    )

    return {
        "total_images": total_images,
        "total_surveys": total_surveys,
        "total_detections": total_detections,
        "pedestrian_count": pedestrian_count,
        "vehicle_count": vehicle_count,
        "average_confidence": float(average_confidence) if average_confidence is not None else None,
        "class_counts": class_counts,
        "confidence_distribution": confidence_distribution,
        "category_definitions": {"pedestrians": ["pedestrian", "people"], "vehicles": list(vehicle_classes)},
        "gps_statistics": {"available_images": gps_available, "missing_images": total_images - gps_available, "availability_rate": gps_available / total_images if total_images else None},
        "detection_processing": {"processed_images": completed_detection_images, "pending_images": max(total_images - completed_detection_images, 0)},
        "processing_time": run_stats,
        "localization_statistics": {
            "total_runs": localization_total, "completed_runs": localization_successes,
            "failed_or_incomplete_runs": localization_total - localization_successes,
            "candidate_patches_returned": int(localization_candidates), "verified_candidates": int(localization_verified),
            **localization_evaluation,
        },
        "survey_statistics": survey_stats,
        "filters": {"survey_id": survey_id, "date_from": date_from, "date_to": date_to},
        "model_name": latest_detection.model_name if latest_detection else None,
        "model_version": latest_detection.model_version if latest_detection else None,
        "recent_images": [{**_image_response(image), "detection_count": counts.get(image.id, 0)} for image in recent_images],
        "recent_activity": [
            {"id": detection.id, "image_id": detection.image_id, "filename": filename,
             "class_name": detection.class_name, "confidence": detection.confidence,
             "created_at": detection.created_at, "model_name": detection.model_name,
             "model_version": detection.model_version}
            for detection, filename in recent_activity_rows
        ],
        "recent_processing_activity": [
            {"id": run.id, "image_id": run.image_id, "filename": filename,
             "pipeline": run.pipeline, "mode": run.mode, "status": run.status,
             "processing_seconds": run.processing_seconds, "result_count": run.result_count,
             "verified_count": run.verified_count, "error_message": run.error_message,
             "started_at": run.started_at, "completed_at": run.completed_at}
            for run, filename in recent_runs
        ],
    }
