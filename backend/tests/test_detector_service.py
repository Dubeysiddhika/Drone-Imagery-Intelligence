import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.services import detector
from app.services.model_registry import (
    VISDRONE10_CLASS_NAMES,
    get_model_metadata,
)


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _Box:
    def __init__(self, class_id):
        self.cls = _Scalar(class_id)
        self.conf = _Scalar(0.875)
        self.xyxy = [[_Scalar(2.0), _Scalar(3.0), _Scalar(18.0), _Scalar(19.0)]]


class DetectorServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_path = Path(self.temp_dir.name) / "image.png"
        Image.new("RGB", (20, 20)).save(self.image_path)
        detector._model_cache.clear()

    def tearDown(self):
        detector._model_cache.clear()
        self.temp_dir.cleanup()

    def test_baseline_detection_keeps_original_class_and_pixel_box(self):
        fake_model = SimpleNamespace(
            names={0: "person", 1: "vehicle"},
            predict=lambda **kwargs: [
                SimpleNamespace(boxes=[_Box(1)])
            ],
        )
        with patch.object(detector, "YOLO", return_value=fake_model) as load_model:
            detections = detector.detect_objects(self.image_path)
            detector.detect_objects(self.image_path, model_version="baseline")

        load_model.assert_called_once()
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["class_id"], 1)
        self.assertEqual(detections[0]["class_name"], "vehicle")
        self.assertEqual(detections[0]["confidence"], 0.875)
        self.assertEqual(
            (
                detections[0]["x1"],
                detections[0]["y1"],
                detections[0]["x2"],
                detections[0]["y2"],
            ),
            (2.0, 3.0, 18.0, 19.0),
        )
        self.assertEqual(
            detections[0]["model_version"],
            "drone_person_vehicle",
        )

    def test_visdrone10_detection_uses_configured_class_names(self):
        fake_model = SimpleNamespace(
            names=dict(enumerate(VISDRONE10_CLASS_NAMES)),
            predict=lambda **kwargs: [
                SimpleNamespace(boxes=[_Box(9)])
            ],
        )
        with patch.object(detector, "YOLO", return_value=fake_model) as load_model:
            detections = detector.detect_objects(
                self.image_path,
                model_version="visdrone10_yolo11n",
            )
            detector.detect_objects(
                self.image_path,
                model_version="visdrone10",
            )

        load_model.assert_called_once()
        self.assertEqual(detections[0]["class_id"], 9)
        self.assertEqual(detections[0]["class_name"], "motor")
        self.assertEqual(
            detections[0]["model_version"],
            "visdrone10_yolo11n",
        )

    def test_visdrone10_configuration_uses_project_relative_default_path(self):
        with patch.dict(
            "os.environ",
            {"VISDRONE10_MODEL_PATH": "runs/custom/weights/best.pt"},
        ):
            metadata = get_model_metadata("visdrone10")

        self.assertEqual(metadata["class_names"], VISDRONE10_CLASS_NAMES)
        self.assertEqual(metadata["class_count"], 10)
        self.assertEqual(
            Path(metadata["model_path"]),
            detector.PROJECT_ROOT / "runs" / "custom" / "weights" / "best.pt",
        )

    def test_model_checkpoint_class_mismatch_is_rejected(self):
        fake_model = SimpleNamespace(
            names={0: "person", 1: "vehicle"},
            predict=lambda **kwargs: [],
        )
        with patch.object(detector, "YOLO", return_value=fake_model):
            with self.assertRaisesRegex(
                detector.ModelUnavailableError,
                "classes do not match",
            ):
                detector.get_model("visdrone10")

    def test_unknown_model_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model version"):
            detector.detect_objects(self.image_path, model_version="unknown")

    def test_unsupported_extension_and_corrupt_image_are_rejected(self):
        unsupported = Path(self.temp_dir.name) / "image.gif"
        unsupported.write_bytes(b"not an image")
        corrupt = Path(self.temp_dir.name) / "corrupt.png"
        corrupt.write_bytes(b"not a PNG")

        with self.assertRaisesRegex(detector.InvalidImageError, "Unsupported"):
            detector.validate_image(unsupported)
        with self.assertRaisesRegex(detector.InvalidImageError, "corrupt"):
            detector.validate_image(corrupt)

    def test_extension_and_actual_image_format_must_match(self):
        mismatched = Path(self.temp_dir.name) / "image.jpg"
        Image.new("RGB", (20, 20)).save(mismatched, format="PNG")

        with self.assertRaisesRegex(detector.InvalidImageError, "does not match"):
            detector.validate_image(mismatched)

    def test_inference_failure_is_reported_as_a_safe_domain_error(self):
        def fail_prediction(**kwargs):
            raise RuntimeError("internal detail")

        fake_model = SimpleNamespace(
            names={0: "person", 1: "vehicle"},
            predict=fail_prediction,
        )
        with patch.object(detector, "YOLO", return_value=fake_model):
            with self.assertRaisesRegex(detector.InferenceError, "inference failed"):
                detector.detect_objects(self.image_path)


if __name__ == "__main__":
    unittest.main()
