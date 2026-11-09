from io import BytesIO
import shutil
import uuid

from pathlib import Path

from fastapi.responses import StreamingResponse
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile
)

from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from ..models.database import get_db
from ..models.models import Detection, DroneImage
from ..services.detector import InvalidImageError, validate_image

from ..services.metadata import (
    extract_metadata
)


router = APIRouter()


def _image_response(image: DroneImage, metadata=None):
    if metadata is None:
        try:
            metadata = extract_metadata(str(_uploaded_file_path(image.filepath)))
        except HTTPException:
            metadata = {
                "camera_make": None,
                "camera_model": None,
                "width": None,
                "height": None,
                "exif_available": False,
            }

    return {
        "image_id": image.id,
        "id": image.id,
        "filename": image.filename,
        "latitude": image.latitude,
        "longitude": image.longitude,
        "altitude": image.altitude,
        "capture_time": image.captured_at,
        "captured_at": image.captured_at,
        "uploaded_at": image.uploaded_at,
        "detection_count": 0,
        "camera_make": metadata["camera_make"],
        "camera_model": metadata["camera_model"],
        "width": metadata["width"],
        "height": metadata["height"],
        "exif_available": metadata["exif_available"],
    }


def _uploaded_file_path(filepath: str) -> Path:
    """Resolve only files inside the application upload directory."""
    upload_root = UPLOAD_DIR.resolve()
    try:
        image_path = Path(filepath).resolve(strict=True)
        image_path.relative_to(upload_root)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail="Image file not found") from error
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")
    return image_path


# --------------------------------------------------
# Upload directory
# --------------------------------------------------

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

UPLOAD_DIR = (
    BASE_DIR / "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# --------------------------------------------------
# Supported image formats
# --------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff"
}


# --------------------------------------------------
# Upload image
# --------------------------------------------------

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    # Check filename
    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Filename is missing"
        )


    extension = Path(
        file.filename
    ).suffix.lower()


    # Check image format
    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Use JPG, JPEG, PNG, TIFF."
            )
        )


    # Create unique filename
    unique_filename = (
        f"{uuid.uuid4()}"
        f"{extension}"
    )


    destination = (
        UPLOAD_DIR
        / unique_filename
    )


    # Save uploaded file
    with destination.open("wb") as buffer:

        shutil.copyfileobj(
            file.file,
            buffer
        )

    try:
        validate_image(destination)
    except InvalidImageError as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    # Extract metadata
    metadata = extract_metadata(
        str(destination)
    )


    # Create database record
    image = DroneImage(

        filename=file.filename,

        filepath=str(destination),

        latitude=metadata[
            "latitude"
        ],

        longitude=metadata[
            "longitude"
        ],

        altitude=metadata[
            "altitude"
        ],

        captured_at=metadata[
            "captured_at"
        ]
    )


    db.add(image)

    db.commit()

    db.refresh(image)


    # Return result
    return {

        "success": True,

        "message":
            "Image uploaded successfully",

        "image": _image_response(image, metadata)
    }


# --------------------------------------------------
# Get all images
# --------------------------------------------------

@router.get("/")
def get_images(
    db: Session = Depends(get_db)
):

    images = (
        db.query(DroneImage)
        .order_by(
            DroneImage.uploaded_at.desc()
        )
        .all()
    )

    image_ids = [image.id for image in images]
    detection_counts = {}
    if image_ids:
        detection_counts = dict(
            db.query(Detection.image_id, func.count(Detection.id))
            .filter(Detection.image_id.in_(image_ids))
            .group_by(Detection.image_id)
            .all()
        )

    return [
        {
            **_image_response(image),
            "detection_count": detection_counts.get(image.id, 0),
        }
        for image in images
    ]


# --------------------------------------------------
# Get one image
# --------------------------------------------------

@router.get("/{image_id}")
def get_image(
    image_id: int,
    db: Session = Depends(get_db)
):

    image = (
        db.query(DroneImage)
        .filter(
            DroneImage.id == image_id
        )
        .first()
    )


    if not image:

        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    detection_count = db.query(Detection).filter(
        Detection.image_id == image.id
    ).count()
    return {
        **_image_response(image),
        "detection_count": detection_count,
    }


@router.get("/{image_id}/preview", summary="Get an uploaded image preview")
def get_image_preview(
    image_id: int,
    db: Session = Depends(get_db),
):
    image = db.query(DroneImage).filter(DroneImage.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    image_path = _uploaded_file_path(image.filepath)
    output = BytesIO()
    try:
        with Image.open(image_path) as source:
            source.thumbnail((2048, 2048))
            source.convert("RGB").save(output, format="JPEG", quality=88)
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise HTTPException(
            status_code=415,
            detail="Stored image cannot be converted to a preview.",
        ) from error

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )