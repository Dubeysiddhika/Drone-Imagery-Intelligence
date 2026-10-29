from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_visdrone_source import verify_source


class VerifyVisDroneSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.source = Path(self.temp_dir.name)

    def _add_split(
        self,
        split_name: str,
        category_ids: list[int],
        *,
        nested: bool = False,
    ) -> None:
        split_root = self.source / split_name
        if nested:
            split_root = split_root / split_name
        images = split_root / "images"
        annotations = split_root / "annotations"
        images.mkdir(parents=True)
        annotations.mkdir(parents=True)
        for index, category_id in enumerate(category_ids):
            stem = f"image_{index}"
            (images / f"{stem}.jpg").touch()
            (annotations / f"{stem}.txt").write_text(
                f"1,2,3,4,1,{category_id},0,0\n",
                encoding="utf-8",
            )

    def test_valid_original_annotations_cover_all_ten_categories(self) -> None:
        category_ids = list(range(12))
        self._add_split("VisDrone2019-DET-train", category_ids, nested=True)
        self._add_split("VisDrone2019-DET-val", category_ids)

        report = verify_source(self.source)

        self.assertTrue(report["ready_for_ten_class_conversion"])
        self.assertEqual(report["observed_category_ids"], list(range(12)))
        self.assertEqual(
            report["splits"]["VisDrone2019-DET-train"]["image_count"],
            12,
        )
        self.assertEqual(
            report["splits"]["VisDrone2019-DET-val"]["annotation_row_count"],
            12,
        )
        self.assertEqual(
            report["splits"]["VisDrone2019-DET-train"]["category_ids"],
            list(range(12)),
        )

    def test_malformed_rows_and_unmatched_files_block_readiness(self) -> None:
        self._add_split("VisDrone2019-DET-train", list(range(1, 11)))
        self._add_split("VisDrone2019-DET-val", list(range(1, 11)))
        train_root = self.source / "VisDrone2019-DET-train"
        (train_root / "annotations" / "image_0.txt").write_text(
            "1,2,3,4,1,1,0\n",
            encoding="utf-8",
        )
        (train_root / "images" / "without_label.jpg").touch()
        (train_root / "annotations" / "without_image.txt").write_text(
            "1,2,3,4,1,1,0,0\n",
            encoding="utf-8",
        )

        report = verify_source(self.source)
        train_report = report["splits"]["VisDrone2019-DET-train"]

        self.assertFalse(report["ready_for_ten_class_conversion"])
        self.assertEqual(train_report["malformed_row_count"], 1)
        self.assertIn("without_label", train_report["images_without_annotations"])
        self.assertIn("without_image", train_report["annotations_without_images"])

    def test_two_class_source_does_not_claim_missing_categories(self) -> None:
        self._add_split("VisDrone2019-DET-train", [1, 2])
        self._add_split("VisDrone2019-DET-val", [1, 2])

        report = verify_source(self.source)

        self.assertFalse(report["ready_for_ten_class_conversion"])
        self.assertEqual(report["observed_category_ids"], [1, 2])
        self.assertEqual(report["missing_required_category_ids"], list(range(3, 11)))

    def test_optional_test_split_cannot_supply_missing_train_validation_classes(
        self,
    ) -> None:
        self._add_split("VisDrone2019-DET-train", [1, 2])
        self._add_split("VisDrone2019-DET-val", [1, 2])
        self._add_split("VisDrone2019-DET-test-dev", list(range(3, 11)))

        report = verify_source(self.source)

        self.assertFalse(report["ready_for_ten_class_conversion"])
        self.assertEqual(report["observed_category_ids"], list(range(1, 11)))
        self.assertEqual(report["train_validation_category_ids"], [1, 2])
        self.assertEqual(report["missing_required_category_ids"], list(range(3, 11)))

    def test_missing_source_is_not_ready(self) -> None:
        report = verify_source(self.source / "not-present")

        self.assertFalse(report["ready_for_ten_class_conversion"])
        self.assertIn("does not exist", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
