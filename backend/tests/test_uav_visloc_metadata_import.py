import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORT_SCRIPT = PROJECT_ROOT / "training" / "import_uav_visloc.py"
SPEC = importlib.util.spec_from_file_location("uav_visloc_metadata_import", IMPORT_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load UAV-VisLoc import script: {IMPORT_SCRIPT}")
importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(importer)


class UAVVisLocMetadataImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temporary.name) / "consolidated.csv"
        self.fields = [
            "flight_number",
            "image_filename",
            "image_path",
            "source_csv",
            "source_row",
            "capture_time_raw",
            "latitude",
            "longitude",
            "height",
            "omega",
            "kappa",
            "phi1",
            "phi2",
            "satellite_map",
        ]

    def tearDown(self):
        self.temporary.cleanup()

    def write_rows(self, rows):
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_loads_and_normalizes_consolidated_metadata_rows(self):
        self.write_rows([{
            "flight_number": "02",
            "image_filename": "02_0015.JPG",
            "image_path": r"E:\Drone-image-intelligence\UAV_VisLoc_dataset\02\drone\02_0015.JPG",
            "source_csv": r"02\02.csv",
            "source_row": "16",
            "capture_time_raw": "2018-09-18T11:30:38",
            "latitude": "29.78959564",
            "longitude": "116.0406953",
            "height": "405.72",
            "omega": "-0.830789",
            "kappa": "-0.876625",
            "phi1": "170.672668",
            "phi2": "178.585215",
            "satellite_map": "satellite02.tif",
        }])

        records = importer.load_metadata_rows(self.csv_path)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["relative_path"], "02/drone/02_0015.JPG")
        self.assertEqual(record["filename"], "02_0015.JPG")
        self.assertEqual(record["capture_time_raw"], "2018-09-18T11:30:38")
        self.assertAlmostEqual(record["latitude"], 29.78959564)
        self.assertAlmostEqual(record["longitude"], 116.0406953)
        self.assertAlmostEqual(record["height"], 405.72)
        self.assertAlmostEqual(record["omega"], -0.830789)
        self.assertAlmostEqual(record["kappa"], -0.876625)
        self.assertAlmostEqual(record["phi1"], 170.672668)
        self.assertAlmostEqual(record["phi2"], 178.585215)
        self.assertEqual(record["metadata_csv"], "02/02.csv")

        output = Path(self.temporary.name) / "metadata.json"
        importer.write_json_export(records, output)
        exported = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["satellite_map"], "satellite02.tif")

    def test_rejects_invalid_coordinates_before_import(self):
        self.write_rows([{
            "flight_number": "02",
            "image_filename": "02_0015.JPG",
            "image_path": "",
            "source_csv": "02/02.csv",
            "source_row": "16",
            "capture_time_raw": "2018-09-18T11:30:38",
            "latitude": "129.0",
            "longitude": "116.0406953",
            "height": "405.72",
            "omega": "",
            "kappa": "",
            "phi1": "",
            "phi2": "",
            "satellite_map": "satellite02.tif",
        }])

        with self.assertRaisesRegex(ValueError, "latitude is out of range"):
            importer.load_metadata_rows(self.csv_path)


if __name__ == "__main__":
    unittest.main()
