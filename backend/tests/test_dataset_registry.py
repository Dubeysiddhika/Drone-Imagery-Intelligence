import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.services import dataset_registry
from app.services.dataset_registry import DEFAULT_DATASET_ROOT, DatasetRegistry


class DatasetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "dataset"
        self.flight = self.root / "01"
        (self.flight / "drone").mkdir(parents=True)
        self.image_path = self.flight / "drone" / "01_0065.JPG"
        image = Image.new("RGB", (240, 160), "#a8b899")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 30, 180, 120), fill="#445566")
        draw.line((0, 0, 239, 159), fill="white", width=5)
        image.save(self.image_path, quality=94)
        with (self.flight / "01.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["num", "filename", "date", "lat", "lon", "height", "Phi1", "extra"])
            writer.writeheader()
            writer.writerow({"num": 65, "filename": "01_0065.JPG", "date": "2018-09-17T12:47:57", "lat": "29.71534712", "lon": "115.9747744", "height": "406.37", "Phi1": "168.88504", "extra": "preserved"})
        self.consolidated = Path(self.temporary.name) / "consolidated.csv"
        with self.consolidated.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["image_filename", "satellite_map", "derived_extra"])
            writer.writeheader()
            writer.writerow({"image_filename": "01_0065.JPG", "satellite_map": "satellite01.tif", "derived_extra": "also preserved"})

    def tearDown(self):
        self.temporary.cleanup()

    def test_exact_filename_requires_matching_file_content_and_preserves_all_csv_fields(self):
        with patch.object(dataset_registry, "CONSOLIDATED_CSV", self.consolidated):
            registry = DatasetRegistry(self.root)
            result = registry.identify(self.image_path, "01_0065.JPG")
            self.assertEqual(result["status"], "matched")
            self.assertEqual(result["method"], "exact_filename_and_sha256")
            record = result["record"]
            self.assertEqual(record["flight_sequence"], "01")
            self.assertEqual(record["ground_truth"]["latitude"], 29.71534712)
            self.assertEqual(record["ground_truth"]["coordinate_source"], "uav_visloc_dataset_ground_truth")
            self.assertEqual(record["source_fields"]["extra"], "preserved")
            self.assertEqual(record["consolidated_fields"]["derived_extra"], "also preserved")

            wrong_named_image = Path(self.temporary.name) / "not-the-record.jpg"
            Image.new("RGB", (240, 160), "#ffffff").save(wrong_named_image)
            mismatch = registry.identify(wrong_named_image, "01_0065.JPG")
            self.assertNotEqual(mismatch["status"], "matched")

    def test_renamed_exact_copy_uses_hash_match_and_foreign_image_is_rejected(self):
        renamed = Path(self.temporary.name) / "renamed-copy.jpg"
        renamed.write_bytes(self.image_path.read_bytes())
        foreign = Path(self.temporary.name) / "foreign.jpg"
        Image.new("RGB", (240, 160), "#ffffff").save(foreign)
        with patch.object(dataset_registry, "CONSOLIDATED_CSV", self.consolidated):
            registry = DatasetRegistry(self.root)
            matched = registry.identify(renamed, "renamed-copy.jpg")
            self.assertEqual(matched["status"], "matched")
            self.assertEqual(matched["method"], "sha256_content")
            self.assertEqual(matched["record"]["filename"], "01_0065.JPG")
            rejected = registry.identify(foreign, "foreign.jpg")
            self.assertEqual(rejected["status"], "not_matched")
            self.assertIsNone(rejected["record"])

    def test_dataset_identity_for_a_bounded_sample_from_all_eleven_flights(self):
        if not DEFAULT_DATASET_ROOT.is_dir():
            self.skipTest("Local UAV-VisLoc dataset is not present")
        registry = DatasetRegistry(DEFAULT_DATASET_ROOT)
        samples = ["01_0065.JPG"] + [f"{flight:02d}_0001.JPG" for flight in range(2, 12)]
        for flight, filename in enumerate(samples, start=1):
            image_path = DEFAULT_DATASET_ROOT / f"{flight:02d}" / "drone" / filename
            self.assertTrue(image_path.is_file(), f"Missing acceptance image {image_path}")
            result = registry.identify(image_path, filename)
            self.assertEqual(result["status"], "matched", filename)
            self.assertEqual(result["method"], "exact_filename_and_sha256", filename)
            self.assertEqual(result["record"]["flight_sequence"], f"{flight:02d}")
            self.assertTrue(result["record"]["ground_truth"]["available"])

    def test_renamed_copy_of_real_uav_visloc_image_matches_by_sha256(self):
        source = DEFAULT_DATASET_ROOT / "01" / "drone" / "01_0065.JPG"
        if not source.is_file():
            self.skipTest("Local UAV-VisLoc image dataset is not present")
        temporary_root = Path(self.temporary.name) / "real_dataset"
        flight_root = temporary_root / "01"
        (flight_root / "drone").mkdir(parents=True)
        shutil.copy2(source, flight_root / "drone" / source.name)
        shutil.copy2(DEFAULT_DATASET_ROOT / "01" / "01.csv", flight_root / "01.csv")
        renamed = Path(self.temporary.name) / "renamed_uav_capture.jpg"
        shutil.copy2(source, renamed)
        registry = DatasetRegistry(temporary_root)
        match = registry.identify(renamed, renamed.name)
        self.assertEqual(match["status"], "matched")
        self.assertEqual(match["method"], "sha256_content")
        self.assertEqual(match["record"]["filename"], "01_0065.JPG")
        self.assertEqual(match["record"]["ground_truth"]["latitude"], 29.71534712)


if __name__ == "__main__":
    unittest.main()
