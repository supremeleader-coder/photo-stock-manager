"""
SQLAlchemy models for Photo Stock Manager.

Database Schema:
----------------
images table:
    - id: Primary key, auto-increment
    - filename: Original filename of the image
    - filepath: Full path to the image file
    - file_size: Size in bytes
    - format: Image format (jpg, png, etc.)
    - width: Image width in pixels
    - height: Image height in pixels
    - exif_camera_make: Camera manufacturer from EXIF
    - exif_camera_model: Camera model from EXIF
    - exif_gps_latitude: GPS latitude from EXIF
    - exif_gps_longitude: GPS longitude from EXIF
    - exif_date_taken: Date/time photo was taken from EXIF
    - ai_tags: Array of AI-generated keywords (JSONB)
    - processing_status: Status enum (pending, processing, completed, failed)
    - error_message: Error details if processing failed
    - processed_at: Timestamp when processing completed
    - created_at: Timestamp when record was created
    - updated_at: Timestamp when record was last updated
    - file_hash: SHA256 hash for duplicate detection
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ProcessingStatus(PyEnum):
    """Processing status for images in the pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Image(Base):
    """
    SQLAlchemy model for the images table.

    Stores image metadata, EXIF data, AI tags, and processing status.
    """
    __tablename__ = "images"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # File information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filepath: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA256

    # Image dimensions
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # EXIF metadata
    exif_camera_make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exif_camera_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exif_gps_latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    exif_gps_longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    exif_date_taken: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Location (from reverse geocoding GPS coordinates)
    location_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # AI-generated tags (stored as JSON array)
    ai_tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=list)

    # Processing status
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status_enum"),
        nullable=False,
        default=ProcessingStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Indexes for frequently queried columns
    __table_args__ = (
        Index("idx_images_filename", "filename"),
        Index("idx_images_filepath", "filepath"),
        Index("idx_images_processing_status", "processing_status"),
        Index("idx_images_file_hash", "file_hash"),
        Index("idx_images_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Image(id={self.id}, filename='{self.filename}', "
            f"status={self.processing_status.value})>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary for serialization."""
        return {
            "id": self.id,
            "filename": self.filename,
            "filepath": self.filepath,
            "file_size": self.file_size,
            "format": self.format,
            "file_hash": self.file_hash,
            "width": self.width,
            "height": self.height,
            "exif_camera_make": self.exif_camera_make,
            "exif_camera_model": self.exif_camera_model,
            "exif_gps_latitude": float(self.exif_gps_latitude) if self.exif_gps_latitude else None,
            "exif_gps_longitude": float(self.exif_gps_longitude) if self.exif_gps_longitude else None,
            "exif_date_taken": self.exif_date_taken.isoformat() if self.exif_date_taken else None,
            "location_country": self.location_country,
            "location_name": self.location_name,
            "ai_tags": self.ai_tags or [],
            "processing_status": self.processing_status.value,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
