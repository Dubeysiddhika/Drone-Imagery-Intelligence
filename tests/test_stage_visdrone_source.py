from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.stage_visdrone_source import stage_source
from scripts.verify_visdrone_source import REQUIRED_SPLITS, verify_source


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StageVisDroneSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source"
        self.output = self.root / "staged"
        self.source.mkdir()
        for split_name in REQUIRED_SPLITS:
            split = self.source / split_name
            (split / "images").mkdir(parents=True)
            (split / "annotations").mkdir()
            for category_id in range(1, 11):
                stem = f"category_{category_id}"
                (split / "images" / f"{stem}.jpg").write_bytes(b"synthetic image")
                (split / "annotations" / f"{stem}.txt").write_text(
                    f"1,2,3,4,1,{category_id},0,0\n",
                    encoding="utf-8",
                )

    def test_trailing_comma_rows_are_normalized_only_when_valid(self) -> None:
        annotation = (
            self.source
            / REQUIRED_SPLITS[0]
            / "annotations"
            / "9999974_00000_d_0000053.txt"
        )
        annotation.write_text(
            "1,2,3,4,1,1,0,0,\n"
            "1,2,0,4,1,1,0,0,\n"
            "1,2,3,4,1,12,0,0,\n",
            encoding="utf-8",
        )

        report = stage_source(self.source, self.output)
        staged = self.output / REQUIRED_SPLITS[0] / "annotations" / annotation.name

        self.assertEqual(report["changed_row_count"], 1)
        self.assertEqual(
            staged.read_text(encoding="utf-8"),
            "1,2,3,4,1,1,0,0\n"
            "1,2,0,4,1,1,0,0,\n"
            "1,2,3,4,1,12,0,0,\n",
        )

    def test_zero_height_row_is_preserved_and_reported_for_exclusion(self) -> None:
        annotation = (
            self.source / REQUIRED_SPLITS[0] / "annotations" / "category_1.txt"
        )
        original = "10,20,5,0,1,1,0,0\n"
        annotation.write_text(original, encoding="utf-8")

        report = stage_source(self.source, self.output)
        staged = self.output / REQUIRED_SPLITS[0] / "annotations" / annotation.name
        verification = verify_source(self.output)

        self.assertEqual(staged.read_text(encoding="utf-8"), original)
        self.assertEqual(report["zero_area_box_count"], 1)
        self.assertEqual(report["zero_height_box_count"], 1)
        self.assertFalse(verification["ready_for_ten_class_conversion"])
        self.assertEqual(
            verification["splits"][REQUIRED_SPLITS[0]]["zero_height_box_count"],
            1,
        )
        self.assertTrue(
            report["zero_area_annotations"][0][
                "exclude_from_generated_training_labels"
            ]
        )

    def test_report_records_every_repaired_file_and_row(self) -> None:
        annotation = (
            self.source
            / REQUIRED_SPLITS[0]
            / "annotations"
            / "9999974_00000_d_0000053.txt"
        )
        annotation.write_text(
            "".join(
                f"1,2,3,4,1,{category_id},0,0,\n"
                for category_id in range(1, 11)
            ),
            encoding="utf-8",
        )

        report = stage_source(self.source, self.output)
        persisted = json.loads(
            (self.output / "repair_report.json").read_text(encoding="utf-8")
        )

        self.assertEqual(report["changed_files"], [
            f"{REQUIRED_SPLITS[0]}/annotations/{annotation.name}"
        ])
        self.assertEqual(report["changed_row_count"], 10)
        self.assertEqual(
            [row["line"] for row in report["changed_rows"]],
            list(range(1, 11)),
        )
        self.assertEqual(persisted["changed_row_count"], 10)

    def test_staging_keeps_original_source_files_unchanged(self) -> None:
        repair_annotation = (
            self.source
            / REQUIRED_SPLITS[0]
            / "annotations"
            / "9999974_00000_d_0000053.txt"
        )
        repair_annotation.write_text("1,2,3,4,1,1,0,0,\n", encoding="utf-8")
        zero_area_annotations = [
            self.source / REQUIRED_SPLITS[0] / "annotations" / filename
            for filename in (
                "0000293_03401_d_0000939.txt",
                "9999985_00000_d_0000020.txt",
                "9999999_00590_d_0000267.txt",
            )
        ]
        for index, annotation in enumerate(zero_area_annotations):
            annotation.write_text(
                f"10,20,5,0,1,{index + 1},0,0\n",
                encoding="utf-8",
            )
        source_annotations = [repair_annotation, *zero_area_annotations]
        before = {path: _sha256(path) for path in source_annotations}

        stage_source(self.source, self.output)

        self.assertEqual(
            {path: _sha256(path) for path in source_annotations},
            before,
        )

    def test_existing_staging_directory_is_never_overwritten(self) -> None:
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            stage_source(self.source, self.output)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
