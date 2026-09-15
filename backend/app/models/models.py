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

from sqlalchemy.orm import relationship

from .database import Base


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