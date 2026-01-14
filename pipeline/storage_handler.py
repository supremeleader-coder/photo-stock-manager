"""
Database storage handler for the pipeline.

Provides:
- Combined metadata and tag storage
- Status tracking throughout processing
- Selective field updates for reprocessing
- Error logging and recovery
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from db.database import session_scope
from db.models import Image, ProcessingStatus
from db.operations import ImageRepository
from pipeline.metadata_extractor import ImageMetadata

logger = logging.getLogger(__name__)


# Field groups (shortcuts for multiple columns)
FIELD_GROUPS = {
    "metadata": [
        "file_size", "format", "width", "height",
        "exif_camera_make", "exif_camera_model",
        "exif_gps_latitude", "exif_gps_longitude", "exif_date_taken"
    ],
    "location": ["location_country", "location_name"],
    "ai_tags": ["ai_tags"],
}

# All valid individual column names
VALID_COLUMNS = {
    "file_size", "format", "width", "height",
    "exif_camera_make", "exif_camera_model",
    "exif_gps_latitude", "exif_gps_longitude", "exif_date_taken",
    "location_country", "location_name",
    "ai_tags",
}

# Combined valid field names (groups + individual columns)
VALID_UPDATE_FIELDS = set(FIELD_GROUPS.keys()) | VALID_COLUMNS


class StorageHandler:
    """
    Handles storing processed image data in the database.

    Manages the complete lifecycle of image records:
    - Creating new records
    - Updating processing status
    - Storing metadata and AI tags
    - Error tracking
    """

    def __init__(self, repository: ImageRepository | None = None):
        """
        Initialize storage handler.

        Args:
            repository: ImageRepository instance. If None, creates a new one.
        """
        self.repository = repository or ImageRepository()

    def create_record(
        self,
        metadata: ImageMetadata,
        ai_tags: list[str] | None = None,
        status: ProcessingStatus = ProcessingStatus.PENDING
    ) -> Image:
        """
        Create a new image record in the database.

        Args:
            metadata: Extracted image metadata.
            ai_tags: AI-generated tags (optional).
            status: Initial processing status.

        Returns:
            Created Image instance.
        """
        with session_scope() as session:
            image = Image(
                filename=metadata.filename,
                filepath=metadata.filepath,
                file_size=metadata.file_size,
                file_hash=metadata.file_hash,
                format=metadata.format,
                width=metadata.width,
                height=metadata.height,
                exif_camera_make=metadata.exif_camera_make,
                exif_camera_model=metadata.exif_camera_model,
                exif_gps_latitude=metadata.exif_gps_latitude,
                exif_gps_longitude=metadata.exif_gps_longitude,
                exif_date_taken=metadata.exif_date_taken,
                location_country=metadata.location_country,
                location_name=metadata.location_name,
                ai_tags=ai_tags or [],
                processing_status=status,
            )
            session.add(image)
            session.flush()
            session.refresh(image)

            logger.info(f"Created record ID {image.id} for {metadata.filename}")
            return image

    def store_complete(
        self,
        metadata: ImageMetadata,
        ai_tags: list[str]
    ) -> Image:
        """
        Store a fully processed image with all data.

        Args:
            metadata: Extracted image metadata.
            ai_tags: AI-generated tags.

        Returns:
            Created Image instance with COMPLETED status.
        """
        with session_scope() as session:
            image = Image(
                filename=metadata.filename,
                filepath=metadata.filepath,
                file_size=metadata.file_size,
                file_hash=metadata.file_hash,
                format=metadata.format,
                width=metadata.width,
                height=metadata.height,
                exif_camera_make=metadata.exif_camera_make,
                exif_camera_model=metadata.exif_camera_model,
                exif_gps_latitude=metadata.exif_gps_latitude,
                exif_gps_longitude=metadata.exif_gps_longitude,
                exif_date_taken=metadata.exif_date_taken,
                location_country=metadata.location_country,
                location_name=metadata.location_name,
                ai_tags=ai_tags,
                processing_status=ProcessingStatus.COMPLETED,
                processed_at=datetime.utcnow(),
            )
            session.add(image)
            session.flush()
            session.refresh(image)

            logger.info(
                f"Stored completed image ID {image.id}: {metadata.filename} "
                f"({len(ai_tags)} tags)"
            )
            return image

    def mark_processing(self, image_id: int) -> None:
        """
        Mark an image as currently processing.

        Args:
            image_id: ID of the image record.
        """
        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                image.processing_status = ProcessingStatus.PROCESSING
                logger.debug(f"Marked image {image_id} as processing")

    def mark_completed(
        self,
        image_id: int,
        ai_tags: list[str] | None = None
    ) -> None:
        """
        Mark an image as completed.

        Args:
            image_id: ID of the image record.
            ai_tags: AI tags to store (optional).
        """
        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                image.processing_status = ProcessingStatus.COMPLETED
                image.processed_at = datetime.utcnow()
                if ai_tags is not None:
                    image.ai_tags = ai_tags
                logger.info(f"Marked image {image_id} as completed")

    def mark_failed(self, image_id: int, error_message: str) -> None:
        """
        Mark an image as failed with error details.

        Args:
            image_id: ID of the image record.
            error_message: Error description.
        """
        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                image.processing_status = ProcessingStatus.FAILED
                image.error_message = error_message[:1000]  # Truncate if too long
                logger.error(f"Marked image {image_id} as failed: {error_message}")

    def update_tags(self, image_id: int, ai_tags: list[str]) -> None:
        """
        Update AI tags for an existing image.

        Args:
            image_id: ID of the image record.
            ai_tags: New AI tags.
        """
        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                image.ai_tags = ai_tags
                logger.debug(f"Updated tags for image {image_id}: {len(ai_tags)} tags")

    def get_unprocessed(self, limit: int | None = None) -> list[Image]:
        """
        Get images pending processing.

        Args:
            limit: Maximum number to return.

        Returns:
            List of Image instances with PENDING status.
        """
        return self.repository.get_unprocessed(limit)

    def get_failed(self) -> list[Image]:
        """
        Get images that failed processing.

        Returns:
            List of Image instances with FAILED status.
        """
        return self.repository.get_failed()

    def exists(self, filepath: str | Path) -> bool:
        """
        Check if filepath exists in database.

        Args:
            filepath: Path to check.

        Returns:
            True if exists.
        """
        return self.repository.exists_by_filepath(str(Path(filepath).resolve()))

    def get_stats(self) -> dict[str, int]:
        """
        Get processing statistics.

        Returns:
            Dictionary with counts by status.
        """
        return {
            "total": self.repository.count(),
            "pending": self.repository.count(ProcessingStatus.PENDING),
            "processing": self.repository.count(ProcessingStatus.PROCESSING),
            "completed": self.repository.count(ProcessingStatus.COMPLETED),
            "failed": self.repository.count(ProcessingStatus.FAILED),
        }

    def get_all_images(self) -> list[Image]:
        """
        Get all images from database.

        Returns:
            List of all Image instances.
        """
        return self.repository.get_all()

    def get_image_by_filepath(self, filepath: str | Path) -> Image | None:
        """
        Get image record by filepath.

        Args:
            filepath: Path to the image file.

        Returns:
            Image instance or None if not found.
        """
        return self.repository.get_by_filepath(str(Path(filepath).resolve()))

    def update_fields(
        self,
        image_id: int,
        fields: list[str],
        metadata: ImageMetadata | None = None,
        ai_tags: list[str] | None = None
    ) -> bool:
        """
        Update only specific fields for an existing image.

        Args:
            image_id: ID of the image record.
            fields: List of fields to update. Can be group names ('metadata',
                   'location', 'ai_tags') or individual column names
                   ('location_country', 'location_name', etc.).
            metadata: New metadata (required for metadata/location fields).
            ai_tags: New AI tags (required for 'ai_tags' field).

        Returns:
            True if update successful, False otherwise.
        """
        with session_scope() as session:
            image = session.get(Image, image_id)
            if not image:
                logger.warning(f"Image {image_id} not found for update")
                return False

            updated_fields = []

            # Expand field groups to individual columns
            columns_to_update = set()
            for field in fields:
                if field in FIELD_GROUPS:
                    columns_to_update.update(FIELD_GROUPS[field])
                else:
                    columns_to_update.add(field)

            # Update each column
            for column in columns_to_update:
                if column == "ai_tags" and ai_tags is not None:
                    image.ai_tags = ai_tags
                    updated_fields.append("ai_tags")
                elif metadata:
                    if column == "file_size":
                        image.file_size = metadata.file_size
                    elif column == "format":
                        image.format = metadata.format
                    elif column == "width":
                        image.width = metadata.width
                    elif column == "height":
                        image.height = metadata.height
                    elif column == "exif_camera_make":
                        image.exif_camera_make = metadata.exif_camera_make
                    elif column == "exif_camera_model":
                        image.exif_camera_model = metadata.exif_camera_model
                    elif column == "exif_gps_latitude":
                        image.exif_gps_latitude = metadata.exif_gps_latitude
                    elif column == "exif_gps_longitude":
                        image.exif_gps_longitude = metadata.exif_gps_longitude
                    elif column == "exif_date_taken":
                        image.exif_date_taken = metadata.exif_date_taken
                    elif column == "location_country":
                        image.location_country = metadata.location_country
                    elif column == "location_name":
                        image.location_name = metadata.location_name
                    else:
                        continue
                    updated_fields.append(column)

            if updated_fields:
                image.updated_at = datetime.utcnow()
                logger.info(
                    f"Updated image {image_id} fields: {', '.join(updated_fields)}"
                )
                return True

            return False

    def delete_all(self) -> int:
        """
        Delete all image records from database.

        Returns:
            Number of records deleted.
        """
        with session_scope() as session:
            count = session.query(Image).delete()
            logger.warning(f"Deleted {count} image records from database")
            return count
