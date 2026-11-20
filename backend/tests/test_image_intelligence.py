import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models.models import Detection, DroneImage, ProcessingRun, UAVVisLocImageMatch
from app.routes import analysis, intelligence


class ImageIntelligenceApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.image_path = self.root / "image.jpg"
        Image.new("RGB", (160, 100), (50, 100, 150)).save(self.image_path)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session:
            image = DroneImage(filename="01_0065.JPG", filepath=str(self.image_path), width=160, height=100, exif_available=False)
            session.add(image)
            session.flush()
            self.image_id = image.id
            record = {
                "filename": "01_0065.JPG",
                "flight_sequence": "01",
                "dataset_image_path": "01/drone/01_0065.JPG",
                "metadata_csv": "01/01.csv",
                "satellite_map": "satellite02.tif; satellite01.tif",
                "ground_truth": {"available": True, "latitude": 29.7, "longitude": 115.97, "coordinate_reference_system": "EPSG:4326", "coordinate_source": "uav_visloc_dataset_ground_truth"},
                "source_fields": {"Phi1": "168.8"},
                "consolidated_fields": {"satellite_map": "satellite02.tif; satellite01.tif"},
            }
            session.add(UAVVisLocImageMatch(
                image_id=image.id,
                status="matched",
                match_method="exact_filename_and_sha256",
                match_confidence=1.0,
                flight_sequence="01",
                dataset_relative_path="01/drone/01_0065.JPG",
                metadata_json=json.dumps(record),
            ))
            session.add(Detection(
                image_id=image.id, class_id=3, class_name="car", confidence=0.91,
                x1=1, y1=2, x2=30, y2=40, model_name="YOLO11n VisDrone10", model_version="visdrone10_yolo11n",
            ))
            session.add(ProcessingRun(
                image_id=image.id, pipeline="localization", mode="gps_free", status="completed",
                processing_seconds=3.2, result_count=1, verified_count=1,
                result_json=json.dumps({
                    "query_image_id": image.id,
                    "mode": "gps_free",
                    "localization_status": "geometric_candidates_found",
                    "precise_localization_claimed": True,
                    "localization_estimate": {
                        "available": True, "status": "single_verified_candidate",
                        "latitude": 29.7001, "longitude": 115.9701,
                        "coordinate_source": "ransac_verified_query_to_satellite_homography",
                    },
                    "evaluation": {
                        "available": True, "error_m": 14.7, "within_5m": False,
                        "within_10m": False, "within_25m": True, "within_50m": True,
                    },
                    "processing_time_seconds": 3.2,
                    "candidates": [{
                        "rank": 1, "candidate_patch_id": "p1", "satellite_tile_id": "01_satellite01_r1_c1",
                        "parent_satellite_map_id": "satellite01", "similarity_score": 0.8,
                        "local_feature_match_count": 10, "ransac_inlier_count": 5, "inlier_ratio": 0.5,
                        "verification_status": "geometric_consistency_passed", "latitude": 29.701,
                        "longitude": 115.971,
                    }],
                }),
            ))
            session.commit()
        app = FastAPI()
        app.include_router(intelligence.router, prefix="/api/intelligence")
        app.dependency_overrides[get_db] = self._get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.temporary.cleanup()

    def _get_db(self):
        with self.sessions() as session:
            yield session

    def test_complete_result_keeps_coordinate_sources_separate_and_exports(self):
        response = self.client.get(f"/api/intelligence/images/{self.image_id}")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["dataset_identity"]["flight_sequence"], "01")
        self.assertEqual(result["geospatial"]["dataset_ground_truth"]["latitude"], 29.7)
        self.assertFalse(result["geospatial"]["exif_coordinate"]["available"])
        self.assertTrue(result["geospatial"]["predicted_uav_coordinate"]["available"])
        self.assertAlmostEqual(result["geospatial"]["predicted_uav_coordinate"]["latitude"], 29.7001)
        self.assertEqual(result["geospatial"]["localization_evaluation"]["error_m"], 14.7)
        self.assertEqual(result["geospatial"]["satellite_candidate_region_rank_for_ground_truth_map"], 1)
        self.assertEqual(result["detection"]["per_class_counts"], [{"class_name": "car", "count": 1}])
        self.assertEqual(result["localization"]["candidates"][0]["ransac_inlier_count"], 5)

        json_export = self.client.get(f"/api/intelligence/images/{self.image_id}/export.json")
        csv_export = self.client.get(f"/api/intelligence/images/{self.image_id}/export.csv")
        pdf_export = self.client.get(f"/api/intelligence/images/{self.image_id}/report.pdf")
        self.assertEqual(json_export.status_code, 200)
        self.assertIn("dataset_ground_truth", json_export.text)
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("bbox_x1", csv_export.text)
        self.assertIn("dataset_capture_time", csv_export.text)
        self.assertIn("predicted_latitude", csv_export.text)
        self.assertIn("ground_truth_error_m", csv_export.text)
        self.assertEqual(pdf_export.status_code, 200)
        self.assertTrue(pdf_export.content.startswith(b"%PDF"))

    def test_process_endpoint_does_not_localize_unmatched_image(self):
        with self.sessions() as session:
            image = session.get(DroneImage, self.image_id)
            session.query(UAVVisLocImageMatch).filter_by(image_id=self.image_id).delete()
            session.add(UAVVisLocImageMatch(image_id=self.image_id, status="not_matched"))
            session.commit()
        detection_output = {"image_id": self.image_id, "detection_count": 0, "detections": []}
        with patch.object(analysis, "detect_image", return_value=detection_output) as detect, \
                patch("app.routes.intelligence.uav_visloc.localize_uploaded_image") as localize:
            response = self.client.post(f"/api/intelligence/images/{self.image_id}/process")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["localization"]["status"], "not_applicable")
        detect.assert_called_once()
        localize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
