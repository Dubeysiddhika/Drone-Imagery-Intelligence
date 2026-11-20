import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models.models import DroneImage, ProcessingRun, UAVVisLocImageMatch
from app.routes import images, uav_visloc
from app.services.visual_localization import LocalizationUnavailableError, reserve_localization_slot, release_localization_slot


class UAVVisLocLocalizationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.upload_dir = self.root / "uploads"
        self.upload_dir.mkdir()
        self.query_path = self.upload_dir / "query.jpg"
        Image.new("RGB", (48, 32)).save(self.query_path)
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            session.add(DroneImage(filename="query.jpg", filepath=str(self.query_path)))
            session.commit()
            self.image_id = session.query(DroneImage.id).scalar()

        self.app = FastAPI()
        self.app.include_router(images.router, prefix="/api/images")
        self.app.include_router(uav_visloc.router, prefix="/api/uav-visloc")
        self.app.dependency_overrides[get_db] = self._get_db
        self.client = TestClient(self.app)
        self.upload_dir_patch = patch.object(images, "UPLOAD_DIR", self.upload_dir)
        self.upload_dir_patch.start()

    def tearDown(self):
        self.upload_dir_patch.stop()
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _get_db(self):
        with self.sessions() as session:
            yield session

    def test_localize_endpoint_returns_evidence_and_visual_only_disclaimer(self):
        expected = {
            "query_image_id": self.image_id,
            "mode": "gps_free",
            "gps_assisted_filter": None,
            "localization_status": "candidate_retrieval_only",
            "precise_localization_claimed": False,
            "note": "Retrieval is not a localization fix.",
            "processing_time_seconds": 1.25,
            "candidates": [],
        }
        with patch.object(uav_visloc, "localize_image", return_value=expected):
            response = self.client.post(
                f"/api/uav-visloc/localize/{self.image_id}?mode=gps_free"
            )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["query_image_id"], self.image_id)
        self.assertFalse(body["precise_localization_claimed"])
        self.assertEqual(body["query_image_url"], f"/api/images/{self.image_id}/preview")
        with self.sessions() as session:
            run = session.query(ProcessingRun).one()
            self.assertEqual(run.image_id, self.image_id)
            self.assertEqual(run.pipeline, "localization")
            self.assertEqual(run.mode, "gps_free")
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.result_count, 0)
            self.assertEqual(json.loads(run.result_json)["localization_status"], "candidate_retrieval_only")
            self.assertIsNotNone(run.started_at)
            self.assertIsNotNone(run.completed_at)

    def test_localize_endpoint_requires_existing_image_and_explicit_visual_mode(self):
        self.assertEqual(self.client.post("/api/uav-visloc/localize/999").status_code, 404)
        gps_required = self.client.post(
            f"/api/uav-visloc/localize/{self.image_id}?mode=gps_assisted"
        )
        self.assertEqual(gps_required.status_code, 422)
        with self.sessions() as session:
            self.assertEqual(session.query(ProcessingRun).count(), 0)
        invalid_mode = self.client.post(
            f"/api/uav-visloc/localize/{self.image_id}?mode=guess"
        )
        self.assertEqual(invalid_mode.status_code, 422)

    def test_gps_assisted_mode_forwards_only_valid_stored_image_coordinates(self):
        with self.sessions() as session:
            image = session.query(DroneImage).filter_by(id=self.image_id).one()
            image.latitude = 29.75
            image.longitude = 115.98
            session.commit()
        expected = {
            "query_image_id": self.image_id,
            "mode": "gps_assisted",
            "gps_assisted_filter": "satellite parent footprints containing valid image EXIF GPS",
            "localization_status": "candidate_retrieval_only",
            "precise_localization_claimed": False,
            "note": "GPS assisted query",
            "processing_time_seconds": 0.5,
            "candidates": [],
        }
        with patch.object(uav_visloc, "localize_image", return_value=expected) as localize:
            response = self.client.post(
                f"/api/uav-visloc/localize/{self.image_id}?mode=gps_assisted"
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["mode"], "gps_assisted")
        self.assertEqual(localize.call_args.kwargs["gps_coordinates"], (29.75, 115.98))
        with self.sessions() as session:
            run = session.query(ProcessingRun).one()
            self.assertEqual(run.mode, "gps_assisted")

    def test_estimate_and_ground_truth_evaluation_are_persisted_separately(self):
        dataset = {
            "filename": "query.jpg", "flight_sequence": "01",
            "ground_truth": {
                "available": True, "latitude": 29.0, "longitude": 115.0,
                "coordinate_source": "uav_visloc_dataset_ground_truth",
            },
        }
        with self.sessions() as session:
            session.add(UAVVisLocImageMatch(
                image_id=self.image_id, status="matched", flight_sequence="01",
                metadata_json=json.dumps(dataset),
            ))
            session.commit()
        estimate = {
            "available": True, "status": "single_verified_candidate",
            "latitude": 29.0001, "longitude": 115.0001,
            "coordinate_source": "ransac_verified_query_to_satellite_homography",
            "selected_candidate_rank": 1,
        }
        engine_result = {
            "query_image_id": self.image_id, "mode": "gps_free",
            "localization_status": "single_verified_candidate",
            "localization_estimate": estimate, "candidates": [],
            "precise_localization_claimed": True,
            "processing_time_seconds": 1.0,
        }
        with patch.object(uav_visloc, "localize_image", return_value=engine_result):
            response = self.client.post(f"/api/uav-visloc/localize/{self.image_id}?mode=gps_free")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["evaluation"]["available"])
        self.assertGreater(body["evaluation"]["error_m"], 0)
        self.assertLess(body["evaluation"]["error_m"], 20)
        self.assertEqual(body["localization_estimate"]["latitude"], 29.0001)
        with self.sessions() as session:
            run = session.query(ProcessingRun).one()
            persisted = json.loads(run.result_json)
        self.assertEqual(persisted["evaluation"]["ground_truth_latitude"], 29.0)
        self.assertEqual(persisted["localization_estimate"]["latitude"], 29.0001)

    def test_failed_attempt_is_recorded_with_error_and_duplicate_active_run_is_rejected(self):
        with patch.object(
            uav_visloc,
            "localize_image",
            side_effect=LocalizationUnavailableError("RAM threshold not met"),
        ):
            failed = self.client.post(f"/api/uav-visloc/localize/{self.image_id}?mode=gps_free")
        self.assertEqual(failed.status_code, 503)
        with self.sessions() as session:
            run = session.query(ProcessingRun).one()
            self.assertEqual(run.status, "failed")
            self.assertIn("RAM threshold", run.error_message)
            self.assertEqual(run.mode, "gps_free")

        self.assertTrue(reserve_localization_slot())
        try:
            duplicate = self.client.post(f"/api/uav-visloc/localize/{self.image_id}?mode=gps_free")
        finally:
            release_localization_slot()
        self.assertEqual(duplicate.status_code, 409)
        with self.sessions() as session:
            self.assertEqual(session.query(ProcessingRun).count(), 1)

    def test_satellite_candidate_preview_route_serves_resolved_tile(self):
        tile_path = self.root / "tile.jpg"
        Image.new("RGB", (32, 32), (80, 100, 120)).save(tile_path)
        with patch.object(uav_visloc, "get_candidate_tile_path", return_value=tile_path):
            response = self.client.get("/api/uav-visloc/candidates/known_tile/preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertTrue(response.content.startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()
