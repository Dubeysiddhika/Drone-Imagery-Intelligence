from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from ultralytics.data.utils import check_det_dataset

from scripts.verify_visdrone10_handoff import normalize_names, verify_handoff
from scripts.train_visdrone10 import EXPECTED_CLASS_NAMES
from scripts.resume_visdrone10 import validate_dataset, write_runtime_dataset_yaml


class VerifyVisDrone10HandoffTests(unittest.TestCase):
    def test_normalize_names_accepts_ten_class_indexed_mapping(self):
        mapping = {index: name for index, name in enumerate(EXPECTED_CLASS_NAMES)}
        self.assertEqual(normalize_names(mapping), EXPECTED_CLASS_NAMES)

    def test_normalize_names_rejects_non_contiguous_ids(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            normalize_names({0: "pedestrian", 2: "bicycle"})

    def test_resume_dataset_yaml_resolves_relative_to_yaml_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_dir = root / "configs"
            config_dir.mkdir()
            for split in ("train", "val"):
                (root / "dataset" / "images" / split).mkdir(parents=True)
            config_path = config_dir / "visdrone10.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "path": "dataset",
                        "train": "images/train",
                        "val": "images/val",
                        "names": EXPECTED_CLASS_NAMES,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                validate_dataset(config_path, root),
                EXPECTED_CLASS_NAMES,
            )

    def test_runtime_yaml_uses_absolute_dataset_path_for_ultralytics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_config = root / "configs" / "visdrone10.yaml"
            source_config.parent.mkdir()
            source_config.write_text(
                yaml.safe_dump(
                    {
                        "path": "dataset",
                        "train": "images/train",
                        "val": "images/val",
                        "names": EXPECTED_CLASS_NAMES,
                    }
                ),
                encoding="utf-8",
            )
            for split in ("train", "val"):
                (root / "dataset" / "images" / split).mkdir(parents=True)
            runtime_config = write_runtime_dataset_yaml(
                source_config,
                root / "temporary" / "data.yaml",
                root,
            )

            runtime = yaml.safe_load(runtime_config.read_text(encoding="utf-8"))
            loaded = check_det_dataset(str(runtime_config))

            self.assertEqual(runtime["path"], str((root / "dataset").resolve()))
            self.assertEqual(list(loaded["names"].values()), EXPECTED_CLASS_NAMES)

    def test_manifest_verification_reports_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for path in (
                "dataset/images/train",
                "dataset/images/val",
                "dataset/labels/train",
                "dataset/labels/val",
            ):
                (root / path).mkdir(parents=True, exist_ok=True)
            for path in (
                "configs/visdrone10.yaml",
                "requirements-visdrone10.txt",
                "scripts/resume_visdrone10.py",
                "scripts/train_visdrone10.py",
                "runs/visdrone10_yolo11n/results.csv",
                "runs/visdrone10_yolo11n/args.yaml",
            ):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text("test", encoding="utf-8")
            names = {index: name for index, name in enumerate(EXPECTED_CLASS_NAMES)}
            (root / "configs/visdrone10.yaml").write_text(
                yaml.safe_dump({"names": names}),
                encoding="utf-8",
            )
            dataset_file = root / "dataset/images/train/sample.jpg"
            dataset_file.write_bytes(b"image")
            digest = hashlib.sha256(b"image").hexdigest()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "dataset": {
                            "yaml": "configs/visdrone10.yaml",
                            "root": "dataset",
                            "files_by_directory": {
                                "images/train": 1,
                                "images/val": 0,
                                "labels/train": 0,
                                "labels/val": 0,
                            },
                            "files": [
                                {
                                    "path": "images/train/sample.jpg",
                                    "bytes": 5,
                                    "sha256": "0" * 64,
                                }
                            ],
                        },
                        "checkpoints": {},
                    }
                ),
                encoding="utf-8",
            )

            errors = verify_handoff(root, manifest_path)

            self.assertTrue(any("SHA-256 mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
