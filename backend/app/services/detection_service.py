from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .detector import detect_objects, validate_image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANNOTATED_DIR = PROJECT_ROOT / "backend" / "uploads" / "annotated"


def render_annotated_image(image_path: str | Path, detections: list[dict[str, Any]]) -> bytes:
    """Render detections onto an image and return an annotated JPEG."""
    source = Path(image_path)
    with Image.open(source) as original:
        image = original.convert("RGB")
    draw = ImageDraw.Draw(image)
    for detection in detections:
        box = (detection["x1"], detection["y1"], detection["x2"], detection["y2"])
        label = f'{detection["class_name"]} {detection["confidence"]:.2f}'
        draw.rectangle(box, outline=(34, 197, 94), width=max(2, image.width // 500))
        draw.text((box[0], max(0, box[1] - 16)), label, fill=(34, 197, 94))
    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def save_annotated_image(image_path: str | Path, detections: list[dict[str, Any]]) -> str:
    """Render detections onto an image and persist the annotated JPEG."""
    ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (ANNOTATED_DIR / filename).write_bytes(render_annotated_image(image_path, detections))
    return filename


def predict_image(image_path: str | Path) -> dict[str, Any]:
    """Run the configured CPU detector and persist an annotated JPEG."""
    source = validate_image(image_path)
    detections = detect_objects(source, model_version="visdrone10_yolo11n")
    filename = save_annotated_image(source, detections)
    return {
        "detections": detections,
        "detection_count": len(detections),
        "annotated_filename": filename,
    }
