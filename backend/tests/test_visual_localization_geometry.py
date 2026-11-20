import unittest

import cv2
import numpy as np
from rasterio.transform import Affine

from app.services.visual_localization import (
    _candidate_center_wgs84,
    _candidate_footprint_wgs84,
    _estimate_candidate_consensus,
    _geometrically_localize,
    _gps_matching_parent_ids,
)


class VisualLocalizationGeometryTests(unittest.TestCase):
    def setUp(self):
        self.query_points = np.asarray([
            (x, y) for y in (40, 140, 240, 340, 440) for x in (40, 140, 240, 340, 440)
        ], dtype=np.float32)
        self.homography = np.asarray([[1, 0, 18], [0, 1, -12], [0, 0, 1]], dtype=np.float64)
        self.satellite_points = cv2.perspectiveTransform(self.query_points.reshape(-1, 1, 2), self.homography).reshape(-1, 2)
        self.mask = np.ones((len(self.query_points), 1), dtype=np.uint8)
        self.metadata = {
            "affine_transform": str(list(Affine(0.00001, 0, 115, 0, -0.00001, 30))[:6]),
            "tile_width_px": "2048",
            "tile_height_px": "2048",
            "crs": "EPSG:4326",
        }

    def test_gps_filter_selects_only_parent_footprints_containing_query(self):
        rows = [
            {
                "parent_satellite_map_id": "overlap",
                "parent_min_lon": "115.0",
                "parent_max_lon": "116.0",
                "parent_min_lat": "29.0",
                "parent_max_lat": "30.0",
            },
            {
                "parent_satellite_map_id": "outside",
                "parent_min_lon": "116.1",
                "parent_max_lon": "117.0",
                "parent_min_lat": "29.0",
                "parent_max_lat": "30.0",
            },
        ]
        self.assertEqual(_gps_matching_parent_ids(rows, 29.5, 115.5), {"overlap"})
        self.assertEqual(_gps_matching_parent_ids(rows, 29.5, 118.0), set())

    def test_candidate_center_and_footprint_transform_to_wgs84(self):
        metadata = {
            "affine_transform": str(list(Affine(0.01, 0, 115, 0, -0.01, 30))[:6]),
            "tile_width_px": "10",
            "tile_height_px": "10",
            "crs": "EPSG:4326",
        }
        latitude, longitude = _candidate_center_wgs84(metadata)
        self.assertAlmostEqual(latitude, 29.95)
        self.assertAlmostEqual(longitude, 115.05)
        footprint = _candidate_footprint_wgs84(metadata)
        ring = footprint["coordinates"][0]
        self.assertEqual(footprint["type"], "Polygon")
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 5)

    def test_homography_projects_query_center_through_raster_affine(self):
        estimate = _geometrically_localize(
            self.query_points, self.satellite_points, self.mask, self.homography,
            len(self.query_points), (512, 512), (512, 512), self.metadata,
        )
        self.assertEqual(estimate["status"], "geometrically_verified")
        self.assertAlmostEqual(estimate["satellite_pixel_x"], 1096, places=4)
        self.assertAlmostEqual(estimate["satellite_pixel_y"], 976, places=4)
        self.assertAlmostEqual(estimate["longitude"], 115.01096, places=6)
        self.assertAlmostEqual(estimate["latitude"], 29.99024, places=6)

    def test_rejects_insufficient_or_spatially_degenerate_evidence(self):
        weak_mask = np.zeros_like(self.mask)
        weak_mask[:7] = 1
        result = _geometrically_localize(
            self.query_points, self.satellite_points, weak_mask, self.homography,
            len(self.query_points), (512, 512), (512, 512), self.metadata,
        )
        self.assertEqual(result["status"], "rejected_quality_control")
        self.assertIn("8 tentative matches", result["reason"])

        concentrated = np.repeat(np.asarray([[100, 100]], dtype=np.float32), len(self.query_points), axis=0)
        result = _geometrically_localize(
            concentrated, concentrated, self.mask, np.eye(3), len(self.query_points),
            (512, 512), (512, 512), self.metadata,
        )
        self.assertEqual(result["status"], "rejected_quality_control")

    def test_consensus_rejects_conflicting_candidate_fixes(self):
        candidates = [
            {"rank": 1, "estimated_image_center": {"status": "geometrically_verified", "latitude": 30.0, "longitude": 115.0}},
            {"rank": 2, "estimated_image_center": {"status": "geometrically_verified", "latitude": 30.01, "longitude": 115.01}},
        ]
        estimate = _estimate_candidate_consensus(candidates)
        self.assertFalse(estimate["available"])
        self.assertEqual(estimate["status"], "conflicting_candidate_estimates")


if __name__ == "__main__":
    unittest.main()
