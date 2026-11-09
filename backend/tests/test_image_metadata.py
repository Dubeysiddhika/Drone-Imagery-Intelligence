import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from shutil import copyfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, get_db
from app.models.models import Detection
from app.routes import images
from app.services.metadata import (
    _parse_capture_time,
    extract_gps_values,
    extract_metadata,
)
from app.services.detector import PROJECT_ROOT


TEST_IMAGE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "0000007_04999_d_0000036.jpg"
)


class MetadataServiceTests(unittest.TestCase):
    def test_dataset_image_reports_dimensions_and_missing_exif(self):
        metadata = extract_metadata(str(TEST_IMAGE))

        self.assertEqual(metadata["width"], 1360)
        self.assertEqual(metadata["height"], 765)
        self.assertFalse(metadata["exif_available"])
        self.assertIsNone(metadata["latitude"])
        self.assertIsNone(metadata["longitude"])
        self.assertIsNone(metadata["altitude"])
        self.assertIsNone(metadata["captured_at"])
        self.assertIsNone(metadata["camera_make"])
        self.assertIsNone(metadata["camera_model"])

    def test_gps_references_set_coordinate_and_altitude_signs(self):
        latitude, longitude, altitude = extract_gps_values(
            {
                "GPSLatitude": ((40, 1), (30, 1), (0, 1)),
                "GPSLatitudeRef": b"S",
                "GPSLongitude": ((73, 1), (15, 1), (0, 1)),
                "GPSLongitudeRef": b"W",
                "GPSAltitude": (25, 2),
                "GPSAltitudeRef": b"\x01",
            }
        )

        self.assertEqual(latitude, -40.5)
        self.assertEqual(longitude, -73.25)
        self.assertEqual(altitude, -12.5)

    def test_missing_gps_reference_does_not_assume_hemisphere(self):
        latitude, longitude, altitude = extract_gps_values(
            {
                "GPSLatitude": (40, 30, 0),
                "GPSLongitude": (73, 15, 0),
            }
        )

        self.assertIsNone(latitude)
        self.assertIsNone(longitude)
        self.assertIsNone(altitude)

    def test_capture_time_uses_existing_naive_datetime_format(self):
        self.assertEqual(
            _parse_capture_time("2024:06:12 14:35:09"),
            datetime(2024, 6, 12, 14, 35, 9),
        )
        self.assertIsNone(_parse_capture_time("not a timestamp"))


class ImageMetadataApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.upload_dir = temp_path / "uploads"
        self.upload_dir.mkdir()
        database_path = temp_path / "test.sqlite"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(images.router, prefix="/api/images")
        self.app.dependency_overrides[get_db] = self._get_test_db
        self.client = TestClient(self.app)
        self.upload_dir_patch = patch.object(images, "UPLOAD_DIR", self.upload_dir)
        self.upload_dir_patch.start()

    def tearDown(self):
        self.upload_dir_patch.stop()
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _get_test_db(self):
        with self.session_factory() as session:
            yield session

    def test_upload_and_detail_endpoint_return_available_metadata(self):
        with TEST_IMAGE.open("rb") as image_file:
            response = self.client.post(
                "/api/images/upload",
                files={
                    "file": (
                        TEST_IMAGE.name,
                        image_file,
                        "image/jpeg",
                    )
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        uploaded = response.json()["image"]
        self.assertEqual(uploaded["width"], 1360)
        self.assertEqual(uploaded["height"], 765)
        self.assertFalse(uploaded["exif_available"])
        self.assertIsNone(uploaded["latitude"])
        self.assertIsNone(uploaded["longitude"])
        self.assertIsNone(uploaded["altitude"])
        self.assertIsNone(uploaded["capture_time"])
        self.assertIsNone(uploaded["camera_make"])
        self.assertIsNone(uploaded["camera_model"])

        image_id = uploaded["image_id"]
        detail = self.client.get(f"/api/images/{image_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["image_id"], image_id)
        self.assertEqual(detail.json()["width"], 1360)
        self.assertIsNone(detail.json()["latitude"])

        preview = self.client.get(f"/api/images/{image_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")
        self.assertTrue(preview.content.startswith(b"\xff\xd8"))

        listing = self.client.get("/api/images/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["image_id"], image_id)
        self.assertEqual(listing.json()[0]["detection_count"], 0)
        self.assertNotIn("filepath", listing.json()[0])

    def test_preview_rejects_file_paths_outside_upload_directory(self):
        outside_image = Path(self.temp_dir.name) / "outside.jpg"
        copyfile(TEST_IMAGE, outside_image)

        with self.session_factory() as session:
            image = images.DroneImage(
                filename=outside_image.name,
                filepath=str(outside_image),
            )
            session.add(image)
            session.commit()
            image_id = image.id

        response = self.client.get(f"/api/images/{image_id}/preview")
        self.assertEqual(response.status_code, 404)

    def test_upload_rejects_corrupt_image_without_storing_file(self):
        response = self.client.post(
            "/api/images/upload",
            files={
                "file": (
                    "corrupt.jpg",
                    b"not a valid image",
                    "image/jpeg",
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("corrupt", response.json()["detail"].lower())
        self.assertEqual(list(self.upload_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()