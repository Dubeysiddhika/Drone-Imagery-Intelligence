import shutil
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, get_db
from app.models.models import Detection, DroneImage, ProcessingRun, Survey
from app.routes import dashboard, images


TEST_IMAGE = Path(__file__).resolve().parent / "fixtures" / "0000007_04999_d_0000036.jpg"


class DashboardSummaryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.upload_dir = root / "uploads"
        self.upload_dir.mkdir()
        image_path = self.upload_dir / "drone.jpg"
        shutil.copyfile(TEST_IMAGE, image_path)

        self.engine = create_engine(
            f"sqlite:///{(root / 'test.sqlite').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.upload_dir_patch = patch.object(images, "UPLOAD_DIR", self.upload_dir)
        self.upload_dir_patch.start()

        self.app = FastAPI()
        self.app.include_router(dashboard.router, prefix="/api/dashboard")
        self.app.dependency_overrides[get_db] = self._get_test_db
        self.client = TestClient(self.app)

        with self.session_factory() as session:
            session.add(Survey(name="Verified survey"))
            session.flush()
            image = DroneImage(
                filename="drone.jpg",
                filepath=str(image_path),
                latitude=26.4,
                longitude=80.3,
                survey_id=1,
            )
            session.add(image)
            session.flush()
            session.add_all(
                [
                    Detection(
                        image_id=image.id,
                        class_id=0,
                        class_name="pedestrian",
                        confidence=0.8,
                        model_name="YOLO11n VisDrone10",
                        model_version="visdrone10_yolo11n",
                        x1=1,
                        y1=2,
                        x2=3,
                        y2=4,
                    ),
                    Detection(
                        image_id=image.id,
                        class_id=1,
                        class_name="people",
                        confidence=0.6,
                        model_name="YOLO11n VisDrone10",
                        model_version="visdrone10_yolo11n",
                        x1=5,
                        y1=6,
                        x2=7,
                        y2=8,
                    ),
                    Detection(
                        image_id=image.id,
                        class_id=3,
                        class_name="car",
                        confidence=1.0,
                        model_name="YOLO11n VisDrone10",
                        model_version="visdrone10_yolo11n",
                        x1=9,
                        y1=10,
                        x2=11,
                        y2=12,
                    ),
                    Detection(
                        image_id=image.id,
                        class_id=2,
                        class_name="bicycle",
                        confidence=0.9,
                        model_name="YOLO11n VisDrone10",
                        model_version="visdrone10_yolo11n",
                        x1=13,
                        y1=14,
                        x2=15,
                        y2=16,
                    ),
                ]
            )
            session.commit()

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.upload_dir_patch.stop()
        self.temp_dir.cleanup()

    def _get_test_db(self):
        with self.session_factory() as session:
            yield session

    def test_summary_aggregates_real_class_counts_and_safe_recent_images(self):
        response = self.client.get("/api/dashboard/summary")

        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["total_images"], 1)
        self.assertEqual(summary["total_surveys"], 1)
        self.assertEqual(summary["total_detections"], 4)
        self.assertEqual(summary["pedestrian_count"], 2)
        self.assertEqual(summary["vehicle_count"], 1)
        self.assertAlmostEqual(summary["average_confidence"], 0.825)
        self.assertEqual(
            {item["class_name"]: item["count"] for item in summary["class_counts"]},
            {"pedestrian": 1, "people": 1, "car": 1, "bicycle": 1},
        )
        self.assertEqual(summary["recent_images"][0]["detection_count"], 4)
        self.assertEqual(summary["model_version"], "visdrone10_yolo11n")
        self.assertNotIn("filepath", summary["recent_images"][0])
        self.assertEqual(len(summary["recent_activity"]), 4)

    def test_empty_summary_uses_zero_counts_and_unavailable_average(self):
        with self.session_factory() as session:
            session.query(Detection).delete()
            session.query(DroneImage).delete()
            session.query(Survey).delete()
            session.commit()

        response = self.client.get("/api/dashboard/summary")

        self.assertEqual(response.status_code, 200)
        summary = response.json()
        self.assertEqual(summary["total_images"], 0)
        self.assertEqual(summary["total_surveys"], 0)
        self.assertEqual(summary["total_detections"], 0)
        self.assertIsNone(summary["average_confidence"])
        self.assertEqual(summary["class_counts"], [])
        self.assertEqual(summary["recent_images"], [])

    def test_extended_analytics_aggregate_processing_gps_and_survey_records(self):
        with self.session_factory() as session:
            image = session.query(DroneImage).filter_by(filename="drone.jpg").one()
            image.uploaded_at = image.uploaded_at.replace(year=2025, month=3, day=12)
            session.add(DroneImage(
                filename="no-gps.jpg", filepath=str(image.filepath), survey_id=image.survey_id,
                latitude=None, longitude=None, uploaded_at=image.uploaded_at,
            ))
            session.add_all([
                ProcessingRun(image_id=image.id, pipeline="detection", status="completed",
                              processing_seconds=2.5, result_count=4),
                ProcessingRun(image_id=image.id, pipeline="localization", status="completed",
                              processing_seconds=10.0, result_count=75, verified_count=2,
                              result_json=json.dumps({
                                  "localization_estimate": {"available": True, "latitude": 1, "longitude": 2},
                                  "evaluation": {"available": True, "error_m": 8.5},
                              })),
            ])
            session.commit()

        response = self.client.get("/api/dashboard/summary?date_from=2025-03-12&date_to=2025-03-12")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["total_images"], 2)
        self.assertEqual(result["gps_statistics"], {
            "available_images": 1, "missing_images": 1, "availability_rate": 0.5,
        })
        self.assertEqual(result["detection_processing"], {"processed_images": 1, "pending_images": 1})
        self.assertEqual({key: result["localization_statistics"][key] for key in (
            "total_runs", "completed_runs", "failed_or_incomplete_runs",
            "candidate_patches_returned", "verified_candidates",
        )}, {
            "total_runs": 1, "completed_runs": 1, "failed_or_incomplete_runs": 0,
            "candidate_patches_returned": 75, "verified_candidates": 2,
        })
        self.assertEqual(result["localization_statistics"]["estimated_images"], 1)
        self.assertEqual(result["localization_statistics"]["evaluated_images"], 1)
        self.assertEqual(result["localization_statistics"]["median_error_m"], 8.5)
        self.assertEqual(result["localization_statistics"]["within_10m_percent"], 100)
        self.assertEqual(result["processing_time"]["detection"]["completed_runs"], 1)
        self.assertEqual(result["processing_time"]["detection"]["mean_seconds"], 2.5)
        self.assertEqual(result["survey_statistics"][0]["image_count"], 2)
        self.assertEqual([bucket["count"] for bucket in result["confidence_distribution"]], [0, 1, 1, 2])

        filtered = self.client.get("/api/dashboard/summary?survey_id=1&date_from=2025-03-12&date_to=2025-03-12")
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(filtered.json()["total_images"], 2)
        invalid_range = self.client.get("/api/dashboard/summary?date_from=2025-03-13&date_to=2025-03-12")
        self.assertEqual(invalid_range.status_code, 422)

    def test_stats_endpoint_reports_successful_detection_runs(self):
        with self.session_factory() as session:
            image = session.query(DroneImage).one()
            session.add(ProcessingRun(image_id=image.id, pipeline="detection", status="completed", result_count=0))
            session.commit()
        response = self.client.get("/api/dashboard/stats")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["images_processed"], 1)


if __name__ == "__main__":
    unittest.main()
