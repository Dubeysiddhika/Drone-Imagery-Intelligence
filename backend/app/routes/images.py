import shutil
import uuid

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile
)

from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.models import DroneImage

from ..services.metadata import (
    extract_metadata
)


router = APIRouter()


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

        "image": {

            "id":
                image.id,

            "filename":
                image.filename,

            "latitude":
                image.latitude,

            "longitude":
                image.longitude,

            "altitude":
                image.altitude,

            "captured_at":
                image.captured_at,

            "uploaded_at":
                image.uploaded_at
        }
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

    return images


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


    return image