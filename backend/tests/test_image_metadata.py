import tempfile
import unittest
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from shutil import copyfile
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, get_db
from app.models.models import Detection, DroneImage, Survey
from app.routes import images
from app.services.metadata import (
    _parse_capture_time,
    extract_gps_values,
    extract_metadata,
)
from app.services.dataset_registry import identify_dataset_image as identify_real_dataset_image
from app.services.detector import PROJECT_ROOT


TEST_IMAGE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "0000007_04999_d_0000036.jpg"
)


class MetadataServiceTests(unittest.TestCase):
    def test_extracts_gps_from_a_real_jpeg_with_gps_exif(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gps.jpg"
            exif = Image.Exif()
            exif[271] = "DJI"
            exif[272] = "Mavic 3"
            exif[274] = 6
            exif._ifds[34853] = {
                1: "S",
                2: (Fraction(40), Fraction(30), Fraction(0)),
                3: "W",
                4: (Fraction(73), Fraction(15), Fraction(0)),
            }
            Image.new("RGB", (64, 32)).save(path, exif=exif)

            metadata = extract_metadata(str(path))

        self.assertTrue(metadata["gps_available"])
        self.assertEqual(metadata["latitude"], -40.5)
        self.assertEqual(metadata["longitude"], -73.25)
        self.assertIsNone(metadata["altitude"])
        self.assertEqual(metadata["orientation"], 6)
        self.assertEqual(metadata["camera_make"], "DJI")

    def test_extracts_embedded_gps_camera_orientation_and_focal_metadata(self):
        class FakeExif(dict):
            def get_ifd(self, tag):
                if int(tag) == 34853:
                    return {
                        1: "S",
                        2: ((40, 1), (30, 1), (0, 1)),
                        3: "W",
                        4: ((73, 1), (15, 1), (0, 1)),
                        5: 0,
                        6: (125, 1),
                    }
                if int(tag) == 34665:
                    return {36867: "2024:06:12 14:35:09", 37386: (35, 1)}
                return {}

        fake_image = MagicMock()
        fake_image.size = (4000, 3000)
        fake_image.getexif.return_value = FakeExif({271: "DJI", 272: "Mavic 3", 274: 6})
        fake_image.__enter__.return_value = fake_image
        with patch("app.services.metadata.Image.open", return_value=fake_image):
            metadata = extract_metadata("embedded-gps.jpg")

        self.assertEqual(metadata["latitude"], -40.5)
        self.assertEqual(metadata["longitude"], -73.25)
        self.assertEqual(metadata["altitude"], 125.0)
        self.assertEqual(metadata["captured_at"], datetime(2024, 6, 12, 14, 35, 9))
        self.assertEqual(metadata["camera_make"], "DJI")
        self.assertEqual(metadata["camera_model"], "Mavic 3")
        self.assertEqual(metadata["orientation"], 6)
        self.assertEqual(metadata["focal_length"], 35.0)
        self.assertEqual((metadata["width"], metadata["height"]), (4000, 3000))
        self.assertTrue(metadata["gps_available"])

    def test_malformed_partial_exif_never_reports_gps_available(self):
        latitude, longitude, altitude = extract_gps_values(
            {
                "GPSLatitude": ((91, 1), (0, 1), (0, 1)),
                "GPSLatitudeRef": "N",
                "GPSLongitude": ((10, 1), (0, 1), (0, 1)),
                "GPSLongitudeRef": "?",
                "GPSAltitude": (1, 0),
            }
        )
        self.assertIsNone(latitude)
        self.assertIsNone(longitude)
        self.assertIsNone(altitude)

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
        self.dataset_match_patch = patch.object(
            images,
            "identify_dataset_image",
            side_effect=lambda path, filename: identify_real_dataset_image(path, filename)
            if filename.casefold() == "01_0065.jpg"
            else {"status": "not_matched", "method": None, "confidence": None, "record": None},
        )
        self.dataset_match_patch.start()

    def tearDown(self):
        self.upload_dir_patch.stop()
        self.dataset_match_patch.stop()
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
        self.assertFalse(uploaded["gps_available"])
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
        self.assertFalse(detail.json()["gps_available"])

        preview = self.client.get(f"/api/images/{image_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")
        self.assertTrue(preview.content.startswith(b"\xff\xd8"))

        listing = self.client.get("/api/images/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["image_id"], image_id)
        self.assertEqual(listing.json()[0]["detection_count"], 0)
        self.assertNotIn("filepath", listing.json()[0])

    def test_upload_identifies_and_persists_real_uav_visloc_dataset_record(self):
        dataset_image = PROJECT_ROOT / "UAV_VisLoc_dataset" / "01" / "drone" / "01_0065.JPG"
        if not dataset_image.is_file():
            self.skipTest("Local UAV-VisLoc image dataset is not present")
        response = self.client.post(
            "/api/images/upload",
            files={"file": ("01_0065.JPG", dataset_image.read_bytes(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        image_id = response.json()["image"]["image_id"]
        match = response.json()["dataset_match"]
        self.assertEqual(match["status"], "matched")
        self.assertEqual(match["method"], "exact_filename_and_sha256")
        self.assertEqual(match["flight_sequence"], "01")
        self.assertEqual(match["metadata"]["ground_truth"]["latitude"], 29.71534712)
        self.assertEqual(match["metadata"]["source_fields"]["Phi1"], "168.88504")
        detail = self.client.get(f"/api/images/{image_id}").json()
        self.assertEqual(detail["dataset_match"]["dataset_relative_path"], "01/drone/01_0065.JPG")
        with self.session_factory() as session:
            saved = session.query(images.UAVVisLocImageMatch).filter_by(image_id=image_id).one()
            self.assertEqual(saved.status, "matched")
            self.assertEqual(saved.flight_sequence, "01")

    def test_upload_persists_exif_fields_and_associates_selected_survey(self):
        with self.session_factory() as session:
            survey = Survey(name="North field", description="Survey A")
            session.add(survey)
            session.commit()
            survey_id = survey.id

        extracted = {
            "latitude": -40.5,
            "longitude": -73.25,
            "altitude": 125.0,
            "captured_at": datetime(2024, 6, 12, 14, 35, 9),
            "camera_make": "DJI",
            "camera_model": "Mavic 3",
            "width": 4000,
            "height": 3000,
            "exif_available": True,
            "gps_available": True,
            "orientation": 6,
            "focal_length": 35.0,
        }
        with patch("app.routes.images.extract_metadata", return_value=extracted):
            response = self.client.post(
                "/api/images/upload",
                data={"survey_id": str(survey_id)},
                files={"file": ("gps.jpg", TEST_IMAGE.read_bytes(), "image/jpeg")},
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()["image"]
        self.assertTrue(body["gps_available"])
        self.assertEqual(body["latitude"], -40.5)
        self.assertEqual(body["orientation"], 6)
        self.assertEqual(body["focal_length"], 35.0)
        self.assertEqual(body["survey_id"], survey_id)
        detail = self.client.get(f"/api/images/{body['image_id']}").json()
        self.assertEqual(detail["camera_make"], "DJI")
        self.assertEqual(detail["width"], 4000)
        self.assertTrue(detail["gps_available"])
        with self.session_factory() as session:
            image = session.get(DroneImage, body["image_id"])
            self.assertEqual(image.survey_id, survey_id)
            self.assertEqual(image.orientation, 6)
            self.assertEqual(image.focal_length, 35.0)

    def test_real_gps_exif_upload_persists_and_returns_coordinates(self):
        gps_file = Path(self.temp_dir.name) / "capture.jpg"
        exif = Image.Exif()
        exif[271] = "DJI"
        exif[272] = "Mavic 3"
        exif[274] = 6
        exif._ifds[34853] = {
            1: "S",
            2: (Fraction(40), Fraction(30), Fraction(0)),
            3: "W",
            4: (Fraction(73), Fraction(15), Fraction(0)),
        }
        Image.new("RGB", (80, 60)).save(gps_file, exif=exif)
        response = self.client.post(
            "/api/images/upload",
            files={"file": (gps_file.name, gps_file.read_bytes(), "image/jpeg")},
        )

        self.assertEqual(response.status_code, 200, response.text)
        image_body = response.json()["image"]
        self.assertTrue(image_body["gps_available"])
        self.assertEqual(image_body["latitude"], -40.5)
        self.assertEqual(image_body["longitude"], -73.25)
        self.assertEqual(image_body["camera_make"], "DJI")
        self.assertEqual(image_body["orientation"], 6)
        detail = self.client.get(f"/api/images/{image_body['image_id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["gps_available"])
        with self.session_factory() as session:
            saved = session.get(DroneImage, image_body["image_id"])
            self.assertEqual(saved.latitude, -40.5)
            self.assertEqual(saved.longitude, -73.25)
            self.assertEqual(saved.location, "SRID=4326;POINT(-73.25 -40.5)")

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
