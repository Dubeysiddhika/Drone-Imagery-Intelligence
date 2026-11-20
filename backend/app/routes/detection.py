from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..services.detection_service import ANNOTATED_DIR, predict_image
from ..services.detector import InferenceError, InvalidImageError, ModelUnavailableError

router = APIRouter()
logger = logging.getLogger(__name__)
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


@router.post("/predict", summary="Detect objects in an uploaded image")
async def predict(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "Unsupported image format. Use JPG, JPEG, PNG, BMP, or TIFF.")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temp_path = Path(temporary.name)
            while chunk := await file.read(1024 * 1024):
                temporary.write(chunk)
        result = predict_image(temp_path)
        return {
            "class_names": sorted({item["class_name"] for item in result["detections"]}),
            "detections": result["detections"],
            "detection_count": result["detection_count"],
            "annotated_image_url": f"/api/detection/result/{result['annotated_filename']}",
        }
    except InvalidImageError as error:
        raise HTTPException(400, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(503, "The configured model weights are unavailable.") from error
    except ModelUnavailableError as error:
        raise HTTPException(503, str(error)) from error
    except InferenceError as error:
        raise HTTPException(500, str(error)) from error
    except Exception as error:
        logger.exception("Unexpected image prediction failure")
        raise HTTPException(500, "Image detection failed.") from error
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        await file.close()


@router.get("/result/{filename}", summary="Retrieve an annotated detection image")
def get_result(filename: str):
    if Path(filename).name != filename or not filename.endswith(".jpg"):
        raise HTTPException(404, "Annotated image not found")
    output = ANNOTATED_DIR / filename
    if not output.is_file():
        raise HTTPException(404, "Annotated image not found")
    return FileResponse(output, media_type="image/jpeg", filename=filename)
