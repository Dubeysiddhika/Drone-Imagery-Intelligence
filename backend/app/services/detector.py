import logging
import threading
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

from .model_registry import (
    get_default_model_path,
    get_default_model_version,
    get_model_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = get_default_model_path()
logger = logging.getLogger(__name__)

_model_cache: dict[str, YOLO] = {}
_model_cache_lock = threading.Lock()


class InvalidImageError(ValueError):
    """The image path is unsupported or does not contain a valid image."""


class ModelUnavailableError(RuntimeError):
    """The selected model weights are missing or cannot be loaded."""


class InferenceError(RuntimeError):
    """The selected model failed while running inference."""


_SUPPORTED_IMAGE_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


def validate_image(image_path: str | Path) -> Path:
    """Check that the file extension and decoded image format are supported."""
    image = Path(image_path)
    if not image.is_file():
        raise FileNotFoundError(f"Image not found: {image}")

    expected_format = _SUPPORTED_IMAGE_FORMATS.get(image.suffix.lower())
    if expected_format is None:
        raise InvalidImageError(
            "Unsupported image format. Use JPG, JPEG, PNG, or TIFF."
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(image) as decoded:
                if decoded.format != expected_format:
                    raise InvalidImageError(
                        "Image content does not match its filename extension."
                    )
                decoded.verify()
    except InvalidImageError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ) as error:
        raise InvalidImageError("Image is corrupt or cannot be decoded.") from error

    return image


def _class_names(model: YOLO) -> list[str]:
    names = model.names
    if isinstance(names, dict):
        try:
            return [str(names[index]) for index in range(len(names))]
        except KeyError as error:
            raise ModelUnavailableError(
                "Loaded model class IDs must be contiguous from zero."
            ) from error
    if isinstance(names, list):
        return [str(name) for name in names]
    raise ModelUnavailableError("Loaded model does not expose supported class names.")


def get_model(model_version: str | None = None) -> tuple[YOLO, dict[str, Any]]:
    """Load a configured YOLO model once and return it with model metadata."""
    metadata = get_model_metadata(model_version)
    version_key = metadata["model_version"]

    with _model_cache_lock:
        if version_key not in _model_cache:
            model_path = Path(metadata["model_path"])
            if not model_path.is_file():
                raise ModelUnavailableError(
                    f"YOLO model weights are not available: {model_path}"
                )
            try:
                model = YOLO(str(model_path))
            except Exception as error:
                logger.exception("Could not load YOLO model %s", version_key)
                raise ModelUnavailableError(
                    f"YOLO model could not be loaded: {version_key}"
                ) from error

            if _class_names(model) != metadata["class_names"]:
                raise ModelUnavailableError(
                    f"YOLO checkpoint classes do not match model configuration: "
                    f"{version_key}"
                )
            _model_cache[version_key] = model

    return _model_cache[version_key], metadata


def detect_objects(
    image_path: str | Path,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Return detections with xyxy coordinates in source-image pixel units."""
    image = validate_image(image_path)
    model, metadata = get_model(model_version=model_version)

    try:
        results = model.predict(source=str(image), verbose=False)
    except Exception as error:
        logger.exception("YOLO inference failed for model %s", metadata["model_version"])
        raise InferenceError("YOLO inference failed.") from error

    detections: list[dict[str, Any]] = []
    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls.item())
            if not 0 <= class_id < metadata["class_count"]:
                raise InferenceError(
                    f"Model returned an out-of-range class ID: {class_id}"
                )
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": metadata["class_names"][class_id],
                    "confidence": float(box.conf.item()),
                    "x1": float(box.xyxy[0][0].item()),
                    "y1": float(box.xyxy[0][1].item()),
                    "x2": float(box.xyxy[0][2].item()),
                    "y2": float(box.xyxy[0][3].item()),
                    "model_name": metadata["model_name"],
                    "model_version": metadata["model_version"],
                }
            )

    return detections


def get_default_model() -> tuple[YOLO, dict[str, Any]]:
    return get_model(get_default_model_version())
