import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, get_db
from app.models.models import Detection, DroneImage, Survey
from app.routes import images


class GeospatialImageApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.upload_dir = root / "uploads"
        self.upload_dir.mkdir()
        self.image_path = self.upload_dir / "source.jpg"
        Image.new("RGB", (128, 96), (120, 150, 180)).save(self.image_path)
        self.engine = create_engine(
            f"sqlite:///{(root / 'test.sqlite').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.app = FastAPI()
        self.app.include_router(images.router, prefix="/api/images")
        self.app.dependency_overrides[get_db] = self._get_db
        self.client = TestClient(self.app)
        self.upload_dir_patch = patch.object(images, "UPLOAD_DIR", self.upload_dir)
        self.upload_dir_patch.start()

        with self.sessions() as session:
            survey = Survey(name="North field")
            session.add(survey)
            session.flush()
            self.survey_id = survey.id
            second_survey = Survey(name="South field")
            session.add(second_survey)
            session.flush()
            self.second_survey_id = second_survey.id
            located = DroneImage(
                filename="located-a.jpg",
                filepath=str(self.image_path),
                latitude=37.5,
                longitude=-122.25,
                survey_id=survey.id,
                uploaded_at=datetime(2025, 4, 10, 8),
            )
            second = DroneImage(
                filename="located-b.jpg",
                filepath=str(self.image_path),
                latitude=37.5001,
                longitude=-122.2501,
                survey_id=survey.id,
                uploaded_at=datetime(2025, 4, 11, 8),
            )
            missing = DroneImage(
                filename="missing-gps.jpg",
                filepath=str(self.image_path),
                latitude=None,
                longitude=None,
                survey_id=survey.id,
                uploaded_at=datetime(2025, 4, 11, 9),
            )
            other_survey_image = DroneImage(
                filename="south-field.jpg",
                filepath=str(self.image_path),
                latitude=-35.1,
                longitude=149.1,
                survey_id=second_survey.id,
                uploaded_at=datetime(2025, 4, 12, 8),
            )
            invalid_gps = DroneImage(
                filename="invalid-gps.jpg",
                filepath=str(self.image_path),
                latitude=91.0,
                longitude=190.0,
                survey_id=survey.id,
                uploaded_at=datetime(2025, 4, 13, 8),
            )
            session.add_all([located, second, missing, other_survey_image, invalid_gps])
            session.flush()
            self.image_id = located.id
            session.add_all([
                Detection(image_id=located.id, class_id=0, class_name="pedestrian", confidence=.9, x1=5, y1=6, x2=20, y2=30),
                Detection(image_id=located.id, class_id=3, class_name="car", confidence=.8, x1=25, y1=16, x2=50, y2=40),
                Detection(image_id=second.id, class_id=3, class_name="car", confidence=.7, x1=3, y1=4, x2=30, y2=40),
                Detection(image_id=missing.id, class_id=3, class_name="car", confidence=.75, x1=4, y1=5, x2=20, y2=25),
                Detection(image_id=other_survey_image.id, class_id=1, class_name="bicycle", confidence=.65, x1=4, y1=5, x2=20, y2=25),
            ])
            session.commit()

    def tearDown(self):
        self.upload_dir_patch.stop()
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _get_db(self):
        with self.sessions() as session:
            yield session

    def test_geospatial_results_exclude_missing_gps_and_summarize_detections(self):
        response = self.client.get("/api/images/geospatial")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 3)
        first = next(item for item in body["images"] if item["image_id"] == self.image_id)
        self.assertEqual(first["coordinate_meaning"], "image_capture_point")
        self.assertEqual(first["coordinate_reference_system"], "EPSG:4326")
        self.assertEqual(first["survey_id"], self.survey_id)
        self.assertEqual(first["survey_name"], "North field")
        self.assertTrue(first["gps_available"])
        self.assertEqual(first["original_image_url"], f"/api/images/{self.image_id}/preview")
        self.assertEqual(first["annotated_image_url"], f"/api/images/{self.image_id}/annotated")
        self.assertEqual(first["detection_count"], 2)
        self.assertEqual(
            {item["class_name"]: item["count"] for item in first["detected_classes"]},
            {"car": 1, "pedestrian": 1},
        )
        self.assertNotIn("missing-gps.jpg", {item["filename"] for item in body["images"]})
        self.assertEqual(body["located_total"], 3)
        self.assertEqual(body["unlocated_total"], 2)
        missing = next(item for item in body["unlocated_images"] if item["filename"] == "missing-gps.jpg")
        self.assertEqual(missing["filename"], "missing-gps.jpg")
        self.assertFalse(missing["gps_available"])
        self.assertIsNone(missing["latitude"])
        self.assertIsNone(missing["longitude"])
        self.assertEqual(missing["detection_count"], 1)
        self.assertEqual(missing["survey_name"], "North field")
        invalid = next(item for item in body["unlocated_images"] if item["filename"] == "invalid-gps.jpg")
        self.assertFalse(invalid["gps_available"])

    def test_geospatial_filters_by_survey_image_and_class(self):
        by_survey = self.client.get(f"/api/images/geospatial?survey_id={self.survey_id}")
        self.assertEqual(by_survey.json()["total"], 2)
        south = self.client.get(f"/api/images/geospatial?survey_id={self.second_survey_id}")
        self.assertEqual([item["filename"] for item in south.json()["located_images"]], ["south-field.jpg"])
        by_image = self.client.get(f"/api/images/geospatial?image_id={self.image_id}")
        self.assertEqual([item["image_id"] for item in by_image.json()["images"]], [self.image_id])
        by_class = self.client.get("/api/images/geospatial?class_name=CAR")
        self.assertEqual(by_class.json()["total"], 2)
        self.assertEqual(by_class.json()["unlocated_total"], 1)
        self.assertEqual(self.client.get("/api/images/geospatial?class_name=bus").json()["total"], 0)

    def test_geospatial_date_filter_includes_date_and_keeps_unlocated_images_separate(self):
        response = self.client.get("/api/images/geospatial?date_from=2025-04-11&date_to=2025-04-11")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual({item["filename"] for item in body["located_images"]}, {"located-b.jpg"})
        self.assertEqual([item["filename"] for item in body["unlocated_images"]], ["missing-gps.jpg"])
        invalid = self.client.get("/api/images/geospatial?date_from=2025-04-12&date_to=2025-04-10")
        self.assertEqual(invalid.status_code, 422)

    def test_annotated_image_route_returns_jpeg_with_saved_detection_boxes(self):
        response = self.client.get(f"/api/images/{self.image_id}/annotated")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertTrue(response.content.startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()
