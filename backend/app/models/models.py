from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text
)

from sqlalchemy import event
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from geoalchemy2 import Geometry, WKTElement

from .database import Base


class PointGeometry(TypeDecorator):
    """Use PostGIS geometry in PostgreSQL and plain WKT in SQLite tests."""

    impl = String
    cache_ok = True
    geometry_type = "POINT"
    srid = 4326
    dimension = 2
    spatial_index = True
    use_typmod = True

    def load_dialect_impl(self, dialect):
        if dialect is None:
            return String()
        if dialect.name == "postgresql":
            return dialect.type_descriptor(
                Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
            )
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and isinstance(value, str):
            return WKTElement(value.removeprefix("SRID=4326;"), srid=4326)
        return value


def _set_image_location(target) -> None:
    latitude = target.latitude
    longitude = target.longitude
    if latitude is None or longitude is None:
        target.location = None
        return

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError, OverflowError):
        target.location = None
        return

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        target.location = None
        return

    target.location = f"SRID=4326;POINT({longitude} {latitude})"


# ============================================================
# SURVEY MODEL
# ============================================================

class Survey(Base):

    __tablename__ = "surveys"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(200),
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # One survey can contain multiple drone images
    images = relationship(
        "DroneImage",
        back_populates="survey",
        cascade="all, delete-orphan"
    )


# ============================================================
# DRONE IMAGE MODEL
# ============================================================

class DroneImage(Base):

    __tablename__ = "images"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Original filename uploaded by the user
    filename = Column(
        String(255),
        nullable=False
    )

    # Location where the image is stored on the server
    filepath = Column(
        String(500),
        nullable=False
    )

    # GPS latitude extracted from EXIF
    latitude = Column(
        Float,
        nullable=True
    )

    # GPS longitude extracted from EXIF
    longitude = Column(
        Float,
        nullable=True
    )

    # Populated from valid latitude/longitude by the image persistence hooks.
    location = Column(
        PointGeometry(),
        nullable=True
    )

    # Drone altitude extracted from EXIF
    altitude = Column(
        Float,
        nullable=True
    )

    # Original image capture time
    captured_at = Column(
        DateTime,
        nullable=True
    )

    # Time when image was uploaded to the platform
    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Optional survey association
    survey_id = Column(
        Integer,
        ForeignKey("surveys.id"),
        nullable=True
    )

    # Relationship with Survey
    survey = relationship(
        "Survey",
        back_populates="images"
    )

    # One image can have multiple detected objects
    detections = relationship(
        "Detection",
        back_populates="image",
        cascade="all, delete-orphan"
    )


# ============================================================
# OBJECT DETECTION MODEL
# ============================================================

class Detection(Base):

    __tablename__ = "detections"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Image on which the object was detected
    image_id = Column(
        Integer,
        ForeignKey("images.id"),
        nullable=False
    )

    # Nullable for compatibility with existing rows created before class IDs.
    class_id = Column(
        Integer,
        nullable=True
    )

    # Object class detected by YOLO
    # Example: person, car, truck, bicycle
    class_name = Column(
        String(100),
        nullable=False
    )

    # Model confidence score
    # Example: 0.91
    confidence = Column(
        Float,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=True
    )

    # Bounding box coordinates
    x1 = Column(
        Float,
        nullable=False
    )

    y1 = Column(
        Float,
        nullable=False
    )

    x2 = Column(
        Float,
        nullable=False
    )

    y2 = Column(
        Float,
        nullable=False
    )

    # Relationship with DroneImage
    image = relationship(
        "DroneImage",
        back_populates="detections"
    )


@event.listens_for(DroneImage, "before_insert")
@event.listens_for(DroneImage, "before_update")
def _sync_image_location(mapper, connection, target) -> None:
    _set_image_location(target)