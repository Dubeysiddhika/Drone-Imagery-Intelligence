from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image

from scripts.convert_visdrone10_yolo import (
    CATEGORY_TO_CLASS,
    CLASS_NAMES,
    ConversionError,
    convert_dataset,
    validate_converted_dataset,
)
from scripts.verify_visdrone_source import REQUIRED_SPLITS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConvertVisDrone10YoloTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "staged"
        self.output = self.root / "yolo"
        for split in REQUIRED_SPLITS:
            images = self.source / split / "images"
            annotations = self.source / split / "annotations"
            images.mkdir(parents=True)
            annotations.mkdir()
            for category_id in range(1, 11):
                stem = f"category_{category_id}"
                Image.new("RGB", (100, 80), "white").save(
                    images / f"{stem}.jpg",
                    format="JPEG",
                )
                (annotations / f"{stem}.txt").write_text(
                    f"10,20,30,20,1,{category_id},0,0\n",
                    encoding="utf-8",
                )

    def test_all_ten_category_mappings_and_yaml_consistency(self) -> None:
        report = convert_dataset(self.source, self.output)
        validation = validate_converted_dataset(self.output)

        self.assertEqual(CATEGORY_TO_CLASS, {category: category - 1 for category in range(1, 11)})
        self.assertEqual(validation["class_names"], CLASS_NAMES)
        self.assertEqual(
            validation["per_class_counts"],
            {str(class_id): 2 for class_id in range(10)},
        )
        config = yaml.safe_load((self.output / "data.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["names"], CLASS_NAMES)
        self.assertEqual(len(config["names"]), 10)
        self.assertEqual(report["validation"]["valid"], True)
        for category_id, class_id in CATEGORY_TO_CLASS.items():
            label = (
                self.output
                / "labels"
                / "train"
                / f"category_{category_id}.txt"
            ).read_text(encoding="utf-8").split()
            self.assertEqual(int(label[0]), class_id)

    def test_bounding_box_normalization_is_correct(self) -> None:
        convert_dataset(self.source, self.output)

        fields = (
            self.output / "labels" / "train" / "category_1.txt"
        ).read_text(encoding="utf-8").split()
        self.assertEqual(int(fields[0]), 0)
        values = [float(value) for value in fields[1:]]
        self.assertEqual(values, [0.25, 0.375, 0.3, 0.25])

    def test_categories_zero_and_eleven_are_not_emitted_as_detector_classes(self) -> None:
        annotation = (
            self.source
            / REQUIRED_SPLITS[0]
            / "annotations"
            / "category_1.txt"
        )
        annotation.write_text(
            "10,20,30,20,1,1,0,0\n"
            "0,0,10,10,0,0,0,0\n"
            "10,10,10,10,1,11,0,0\n",
            encoding="utf-8",
        )

        report = convert_dataset(self.source, self.output)
        label = (
            self.output / "labels" / "train" / "category_1.txt"
        ).read_text(encoding="utf-8").splitlines()
        persisted = json.loads(
            (self.output / "conversion_report.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(label), 1)
        self.assertEqual(report["ignored_categories"]["0"]["annotation_count"], 1)
        self.assertEqual(report["ignored_categories"]["11"]["annotation_count"], 1)
        self.assertEqual(persisted["all_exclusion_counts_by_reason"]["ignored_region_category"], 1)
        self.assertEqual(persisted["all_exclusion_counts_by_reason"]["others_category"], 1)

    def test_zero_area_rows_are_reported_and_not_emitted(self) -> None:
        expected_files = (
            "0000293_03401_d_0000939.txt",
            "9999985_00000_d_0000020.txt",
            "9999999_00590_d_0000267.txt",
        )
        expected_lines = (130, 12, 89)
        for index, (filename, target_line) in enumerate(
            zip(expected_files, expected_lines)
        ):
            annotation = (
                self.source
                / REQUIRED_SPLITS[0]
                / "annotations"
                / filename
            )
            image = (
                self.source
                / REQUIRED_SPLITS[0]
                / "images"
                / f"{Path(filename).stem}.jpg"
            )
            Image.new("RGB", (100, 80), "white").save(image, format="JPEG"            )
            category_id = (1, 4, 0)[index]
            rows = ["10,20,1,1,1,1,0,0"] * (target_line - 1)
            rows.append(f"10,20,5,0,1,{category_id},0,0")
            annotation.write_text("\n".join(rows) + "\n", encoding="utf-8")
        originals = {
            path: sha256(path)
            for path in (
                self.source / REQUIRED_SPLITS[0] / "annotations" / name
                for name in expected_files
            )
        }

        report = convert_dataset(self.source, self.output)

        self.assertEqual(report["zero_area_exclusion_count"], 3)
        self.assertTrue(report["known_three_zero_height_rows_reported"])
        self.assertEqual(
            {Path(item["annotation_filename"]).name for item in report["zero_area_exclusions"]},
            set(expected_files),
        )
        self.assertEqual(
            {path: sha256(path) for path in originals},
            originals,
        )

    def test_missing_images_fail_before_output_creation(self) -> None:
        image = (
            self.source
            / REQUIRED_SPLITS[0]
            / "images"
            / "category_1.jpg"
        )
        image.unlink()

        with self.assertRaisesRegex(ConversionError, "no matching image"):
            convert_dataset(self.source, self.output)

        self.assertFalse(self.output.exists())

    def test_invalid_coordinates_fail_without_writing_output(self) -> None:
        annotation = (
            self.source / REQUIRED_SPLITS[0] / "annotations" / "category_1.txt"
        )
        annotation.write_text("99,20,30,20,1,1,0,0\n", encoding="utf-8")

        with self.assertRaisesRegex(ConversionError, "outside image bounds"):
            convert_dataset(self.source, self.output)

        self.assertFalse(self.output.exists())

    def test_malformed_rows_fail_without_writing_output(self) -> None:
        annotation = (
            self.source / REQUIRED_SPLITS[0] / "annotations" / "category_1.txt"
        )
        annotation.write_text("10,20,30,20,1,1,0\n", encoding="utf-8")

        with self.assertRaisesRegex(ConversionError, "failed structural verification"):
            convert_dataset(self.source, self.output)

        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self) -> None:
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("original", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            convert_dataset(self.source, self.output)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "original")

    def test_output_validation_rejects_corrupt_labels(self) -> None:
        convert_dataset(self.source, self.output)
        label = self.output / "labels" / "train" / "category_1.txt"
        label.write_text("10 0.5 0.5 0.2 0.2\n", encoding="utf-8")

        with self.assertRaisesRegex(ConversionError, "outside 0-9"):
            validate_converted_dataset(self.output)


if __name__ == "__main__":
    unittest.main()
