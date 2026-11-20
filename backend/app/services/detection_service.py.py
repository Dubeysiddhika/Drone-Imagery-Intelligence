from pathlib import Path
from uuid import uuid4

import cv2
from ultralytics import YOLO


# backend/app/services/detection_service.py
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "runs"
    / "visdrone10_yolo11n"
    / "weights"
    / "best.pt"
)

RESULTS_DIR = BACKEND_DIR / "uploads" / "detection_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

_model = None


def get_model():
    """Load the trained YOLO model once and reuse it."""
    global _model

    if _model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"YOLO weights not found: {MODEL_PATH}"
            )

        _model = YOLO(str(MODEL_PATH))

    return _model


def detect_objects(image_path: str, confidence: float = 0.25):
    """
    Run YOLO inference on one drone image.
    Returns structured detections and the annotated image filename.
    """
    model = get_model()

    results = model.predict(
        source=image_path,
        imgsz=640,
        conf=confidence,
        device="cpu",
        verbose=False
    )

    result = results[0]
    detections = []

    if result.boxes is not None:
        for box in result.boxes:
            class_id = int(box.cls.item())
            score = float(box.conf.item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append({
                "class_id": class_id,
                "class_name": model.names[class_id],
                "confidence": round(score, 4),
                "bounding_box": {
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "x2": round(x2, 2),
                    "y2": round(y2, 2)
                }
            })

    annotated = result.plot()
    output_filename = f"{uuid4().hex}.jpg"
    output_path = RESULTS_DIR / output_filename

    if not cv2.imwrite(str(output_path), annotated):
        raise RuntimeError("Could not save annotated detection image.")

    return {
        "model": "YOLO11n-VisDrone10",
        "image_width": int(result.orig_shape[1]),
        "image_height": int(result.orig_shape[0]),
        "total_detections": len(detections),
        "detections": detections,
        "annotated_image": output_filename
    }