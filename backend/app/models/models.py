from datetime import datetime

from sqlalchemy import (
    Boolean,
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

    # Camera orientation (EXIF 1-8) and focal length in millimeters.
    orientation = Column(Integer, nullable=True)
    focal_length = Column(Float, nullable=True)
    camera_make = Column(String(200), nullable=True)
    camera_model = Column(String(200), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    exif_available = Column(Boolean, nullable=True)

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

    # Model metadata for auditability and traceability.
    model_name = Column(
        String(100),
        nullable=True,
        default="YOLO11n"
    )

    model_version = Column(
        String(200),
        nullable=True,
        default="drone_person_vehicle"
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


class ProcessingRun(Base):
    """Persisted operational history for detection and visual localization."""

    __tablename__ = "processing_runs"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False, index=True)
    pipeline = Column(String(40), nullable=False, index=True)
    mode = Column(String(24), nullable=True)
    status = Column(String(24), nullable=False, default="processing", index=True)
    processing_seconds = Column(Float, nullable=True)
    result_count = Column(Integer, nullable=True)
    verified_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    image = relationship("DroneImage")


class UAVVisLocImageMatch(Base):
    """Verified association and complete source-row metadata for an uploaded image."""

    __tablename__ = "uav_visloc_image_matches"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(24), nullable=False, default="not_matched")
    match_method = Column(String(48), nullable=True)
    match_confidence = Column(Float, nullable=True)
    flight_sequence = Column(String(12), nullable=True, index=True)
    dataset_relative_path = Column(String(500), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    image = relationship("DroneImage")


class User(Base):
    """Application account with normalized unique email and Argon2 password hash."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    normalized_email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(512), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    token_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    """Single-use hashed password-reset token with an explicit expiry."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user = relationship("User")


# ============================================================
# UAV-VISLOC DATASET METADATA
# ============================================================

class UAVVisLocRecord(Base):
    """Metadata for images in the UAV-VisLoc research dataset."""

    __tablename__ = "uav_visloc_records"

    id = Column(Integer, primary_key=True, index=True)

    # Stable path relative to the UAV-VisLoc dataset directory.
    # Unique paths make repeated imports safe.
    relative_path = Column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )

    filename = Column(String(255), nullable=False)

    # Preserve the original date string without losing source information.
    capture_time_raw = Column(String(80), nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    height = Column(Float, nullable=True)

    # Camera orientation; NULL when unavailable in the source CSV.
    omega = Column(Float, nullable=True)
    kappa = Column(Float, nullable=True)
    phi1 = Column(Float, nullable=True)
    phi2 = Column(Float, nullable=True)

    # Source metadata file, useful for traceability.
    metadata_csv = Column(String(255), nullable=False)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


@event.listens_for(DroneImage, "before_insert")
@event.listens_for(DroneImage, "before_update")
def _sync_image_location(mapper, connection, target) -> None:
    _set_image_location(target)
