import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, get_db
from app.models.models import Detection, DroneImage
from app.routes import analysis
from app.services.detector import PROJECT_ROOT


TEST_IMAGE = (
    PROJECT_ROOT
    / "dataset"
    / "images"
    / "test"
    / "0000007_04999_d_0000036.jpg"
)


class DetectionPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.sqlite"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(analysis.router, prefix="/api/analysis")
        self.app.dependency_overrides[get_db] = self._get_test_db
        self.client = TestClient(self.app)

        with self.session_factory() as session:
            self.image = DroneImage(
                filename=TEST_IMAGE.name,
                filepath=str(TEST_IMAGE),
                latitude=None,
                longitude=None,
                altitude=None,
                captured_at=None,
            )
            session.add(self.image)
            session.commit()
            session.refresh(self.image)
            self.image_id = self.image.id

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _get_test_db(self):
        with self.session_factory() as session:
            yield session

    def test_repeated_detection_replaces_rows_and_retrieves_saved_results(self):
        model_results = [
            {
                "class_id": 1,
                "class_name": "vehicle",
                "confidence": 0.91,
                "x1": 12.0,
                "y1": 24.0,
                "x2": 80.0,
                "y2": 100.0,
            },
            {
                "class_id": 0,
                "class_name": "person",
                "confidence": 0.83,
                "x1": 30.0,
                "y1": 40.0,
                "x2": 50.0,
                "y2": 90.0,
            },
        ]

        with patch.object(analysis, "detect_objects", return_value=model_results):
            first_response = self.client.post(
                f"/api/analysis/detect/{self.image_id}"
            )
            second_response = self.client.post(
                f"/api/analysis/detect/{self.image_id}"
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_body = first_response.json()
        second_body = second_response.json()
        self.assertEqual(first_body["image_id"], self.image_id)
        self.assertEqual(first_body["detection_count"], 2)
        self.assertEqual(len(first_body["detections"]), 2)
        self.assertEqual(
            [item["class_name"] for item in first_body["detections"]],
            [item["class_name"] for item in second_body["detections"]],
        )

        with self.session_factory() as session:
            rows = (
                session.query(Detection)
                .filter(Detection.image_id == self.image_id)
                .order_by(Detection.id)
                .all()
            )
            total = session.query(func.count(Detection.id)).scalar()
            self.assertEqual(len(rows), 2)
            self.assertEqual(total, 2)
            self.assertEqual(rows[0].class_id, 1)
            self.assertEqual(rows[0].class_name, "vehicle")
            self.assertAlmostEqual(rows[0].confidence, 0.91)
            self.assertEqual(
                (rows[0].x1, rows[0].y1, rows[0].x2, rows[0].y2),
                (12.0, 24.0, 80.0, 100.0),
            )
            self.assertIsInstance(rows[0].created_at, datetime)

        retrieval = self.client.get(
            f"/api/analysis/detections/{self.image_id}"
        )
        self.assertEqual(retrieval.status_code, 200)
        self.assertEqual(retrieval.json()["detection_count"], 2)
        self.assertEqual(
            retrieval.json()["detections"], second_body["detections"]
        )

    def test_real_model_results_are_persisted(self):
        self.assertTrue(TEST_IMAGE.is_file(), f"Missing test image: {TEST_IMAGE}")

        response = self.client.post(
            f"/api/analysis/detect/{self.image_id}"
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["image_id"], self.image_id)
        self.assertEqual(body["detection_count"], len(body["detections"]))

        with self.session_factory() as session:
            rows = (
                session.query(Detection)
                .filter(Detection.image_id == self.image_id)
                .all()
            )
            self.assertEqual(len(rows), body["detection_count"])
            for row in rows:
                self.assertIsNotNone(row.class_id)
                self.assertTrue(row.class_name)
                self.assertGreaterEqual(row.confidence, 0.0)
                self.assertLessEqual(row.confidence, 1.0)
                self.assertIsNotNone(row.created_at)

        retrieval = self.client.get(
            f"/api/analysis/detections/{self.image_id}"
        )
        self.assertEqual(retrieval.status_code, 200)
        self.assertEqual(
            retrieval.json()["detection_count"], body["detection_count"]
        )


if __name__ == "__main__":
    unittest.main()