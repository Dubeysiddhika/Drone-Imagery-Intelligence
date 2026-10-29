import tempfile
import unittest
from pathlib import Path

from scripts.train_visdrone10 import (
    DEFAULT_DATASET,
    DEFAULT_MODEL,
    DEFAULT_PROJECT,
    DEFAULT_RUN_NAME,
    PROJECT_ROOT,
    build_parser,
    resolve_project_path,
    select_device,
    validate_model_path,
    validate_run_target,
)


class TrainVisDrone10Tests(unittest.TestCase):
    def test_defaults_select_full_ten_class_training_configuration(self):
        args = build_parser().parse_args([])

        self.assertEqual(args.model, DEFAULT_MODEL)
        self.assertEqual(args.data, DEFAULT_DATASET)
        self.assertEqual(args.imgsz, 640)
        self.assertEqual(args.epochs, 100)
        self.assertEqual(args.batch, 2)
        self.assertEqual(args.device, "auto")
        self.assertEqual(args.workers, 0)
        self.assertEqual(args.project, DEFAULT_PROJECT)
        self.assertEqual(args.name, DEFAULT_RUN_NAME)
        self.assertEqual(args.seed, 42)
        self.assertTrue(args.deterministic)

    def test_cli_arguments_override_training_defaults(self):
        args = build_parser().parse_args(
            [
                "--epochs",
                "12",
                "--imgsz",
                "512",
                "--batch",
                "4",
                "--device",
                "cpu",
                "--workers",
                "3",
                "--name",
                "custom_run",
                "--no-deterministic",
            ]
        )

        self.assertEqual(args.epochs, 12)
        self.assertEqual(args.imgsz, 512)
        self.assertEqual(args.batch, 4)
        self.assertEqual(args.device, "cpu")
        self.assertEqual(args.workers, 3)
        self.assertEqual(args.name, "custom_run")
        self.assertFalse(args.deterministic)

    def test_path_resolution_roots_relative_paths_in_project(self):
        project_root = Path("E:/Drone-image-intelligence")

        self.assertEqual(
            resolve_project_path(Path("dataset_visdrone10_yolo/data.yaml"), project_root),
            project_root / "dataset_visdrone10_yolo" / "data.yaml",
        )
        self.assertEqual(
            resolve_project_path(Path("E:/data.yaml"), project_root),
            Path("E:/data.yaml"),
        )

    def test_auto_device_uses_cpu_when_cuda_is_unavailable(self):
        self.assertEqual(select_device("auto", cuda_available=False), "cpu")

    def test_auto_device_uses_cuda_when_available(self):
        self.assertEqual(select_device("auto", cuda_available=True), "0")

    def test_existing_run_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            run_project = project_root / "runs"
            existing = run_project / "visdrone10_yolo11n"
            existing.mkdir(parents=True)
            marker = existing / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                validate_run_target(project_root, run_project, "visdrone10_yolo11n")

            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_run_target_cannot_overwrite_legacy_two_class_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            with self.assertRaises(ValueError):
                validate_run_target(
                    project_root,
                    project_root / "runs",
                    "drone_person_vehicle",
                )

    def test_run_name_must_be_a_single_directory_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)

            with self.assertRaises(ValueError):
                validate_run_target(project_root, project_root / "runs", "..\\other")

    def test_baseline_checkpoint_cannot_be_selected_as_initial_weights(self):
        with self.assertRaises(ValueError):
            validate_model_path(
                PROJECT_ROOT / "runs" / "drone_person_vehicle" / "weights" / "best.pt"
            )


if __name__ == "__main__":
    unittest.main()
