from pathlib import Path
from typing import Any

from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = (
    PROJECT_ROOT
    / "runs"
    / "drone_person_vehicle"
    / "weights"
    / "best.pt"
)

_model: YOLO | None = None


def get_model() -> YOLO:
    """Load the project-trained model once, on first use."""
    global _model

    if _model is None:
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"YOLO model weights are not available: {MODEL_PATH}"
            )
        _model = YOLO(str(MODEL_PATH))

    return _model


def detect_objects(image_path: str | Path) -> list[dict[str, Any]]:
    """Run YOLO inference and return class, confidence, and pixel boxes."""
    image = Path(image_path)
    if not image.is_file():
        raise FileNotFoundError(f"Image not found: {image}")

    model = get_model()
    results = model.predict(source=str(image), verbose=False)
    detections: list[dict[str, Any]] = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls.item())
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": str(result.names[class_id]),
                    "confidence": float(box.conf.item()),
                    "x1": float(box.xyxy[0][0].item()),
                    "y1": float(box.xyxy[0][1].item()),
                    "x2": float(box.xyxy[0][2].item()),
                    "y2": float(box.xyxy[0][3].item()),
                }
            )

    return detections
