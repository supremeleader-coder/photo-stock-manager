"""
Database CRUD operations for Photo Stock Manager.

Provides ImageRepository class with methods for:
- Creating new image records
- Reading/querying images
- Updating image records
- Checking for duplicates
- Batch operations
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.database import session_scope
from db.models import Image, ProcessingStatus

logger = logging.getLogger(__name__)


class ImageRepository:
    """
    Repository for Image database operations.

    Provides CRUD operations and queries for the images table.
    Can be used with a provided session or create its own.
    """

    def __init__(self, session: Session | None = None):
        """
        Initialize repository with optional session.

        Args:
            session: SQLAlchemy session. If None, operations will
                    create their own sessions using session_scope().
        """
        self._session = session

    # ────────────────────────────────────────────────────────────────────────────
    # Create Operations
    # ────────────────────────────────────────────────────────────────────────────

    def create(
        self,
        filename: str,
        filepath: str,
        file_size: int | None = None,
        format: str | None = None,
        file_hash: str | None = None,
        width: int | None = None,
        height: int | None = None,
        exif_camera_make: str | None = None,
        exif_camera_model: str | None = None,
        exif_gps_latitude: float | None = None,
        exif_gps_longitude: float | None = None,
        exif_date_taken: datetime | None = None,
        ai_tags: list[str] | None = None,
        processing_status: ProcessingStatus = ProcessingStatus.PENDING,
    ) -> Image:
        """
        Create a new image record.

        Args:
            filename: Original filename of the image.
            filepath: Full path to the image file.
            file_size: Size in bytes.
            format: Image format (jpg, png, etc.).
            file_hash: SHA256 hash of the file.
            width: Image width in pixels.
            height: Image height in pixels.
            exif_camera_make: Camera manufacturer from EXIF.
            exif_camera_model: Camera model from EXIF.
            exif_gps_latitude: GPS latitude from EXIF.
            exif_gps_longitude: GPS longitude from EXIF.
            exif_date_taken: Date/time photo was taken.
            ai_tags: List of AI-generated keywords.
            processing_status: Initial processing status.

        Returns:
            Created Image instance.
        """
        image = Image(
            filename=filename,
            filepath=filepath,
            file_size=file_size,
            format=format,
            file_hash=file_hash,
            width=width,
            height=height,
            exif_camera_make=exif_camera_make,
            exif_camera_model=exif_camera_model,
            exif_gps_latitude=exif_gps_latitude,
            exif_gps_longitude=exif_gps_longitude,
            exif_date_taken=exif_date_taken,
            ai_tags=ai_tags or [],
            processing_status=processing_status,
        )

        if self._session:
            self._session.add(image)
            self._session.flush()  # Get the ID
        else:
            with session_scope() as session:
                session.add(image)
                session.flush()
                # Refresh to get all defaults
                session.refresh(image)

        logger.debug(f"Created image record: {image}")
        return image

    def create_from_dict(self, data: dict) -> Image:
        """
        Create a new image record from a dictionary.

        Args:
            data: Dictionary with image data.

        Returns:
            Created Image instance.
        """
        return self.create(**data)

    # ────────────────────────────────────────────────────────────────────────────
    # Read Operations
    # ────────────────────────────────────────────────────────────────────────────

    def get_by_id(self, image_id: int) -> Image | None:
        """
        Get image by ID.

        Args:
            image_id: Primary key of the image.

        Returns:
            Image instance or None if not found.
        """
        if self._session:
            return self._session.get(Image, image_id)

        with session_scope() as session:
            return session.get(Image, image_id)

    def get_by_filepath(self, filepath: str) -> Image | None:
        """
        Get image by filepath.

        Args:
            filepath: Full path to the image file.

        Returns:
            Image instance or None if not found.
        """
        stmt = select(Image).where(Image.filepath == filepath)

        if self._session:
            return self._session.execute(stmt).scalar_one_or_none()

        with session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()

    def get_by_filename(self, filename: str) -> list[Image]:
        """
        Get all images with a specific filename.

        Args:
            filename: Original filename to search for.

        Returns:
            List of Image instances with matching filename.
        """
        stmt = select(Image).where(Image.filename == filename)

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def get_by_hash(self, file_hash: str) -> Image | None:
        """
        Get image by file hash.

        Args:
            file_hash: SHA256 hash of the file.

        Returns:
            Image instance or None if not found.
        """
        stmt = select(Image).where(Image.file_hash == file_hash)

        if self._session:
            return self._session.execute(stmt).scalar_one_or_none()

        with session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()

    def exists_by_filepath(self, filepath: str) -> bool:
        """
        Check if an image with the given filepath exists.

        Args:
            filepath: Full path to check.

        Returns:
            True if exists, False otherwise.
        """
        return self.get_by_filepath(filepath) is not None

    def exists_by_hash(self, file_hash: str) -> bool:
        """
        Check if an image with the given hash exists.

        Args:
            file_hash: SHA256 hash to check.

        Returns:
            True if exists, False otherwise.
        """
        return self.get_by_hash(file_hash) is not None

    def get_unprocessed(self, limit: int | None = None) -> list[Image]:
        """
        Get all images with pending status.

        Args:
            limit: Maximum number of images to return.

        Returns:
            List of Image instances with pending status.
        """
        stmt = select(Image).where(
            Image.processing_status == ProcessingStatus.PENDING
        ).order_by(Image.created_at)

        if limit:
            stmt = stmt.limit(limit)

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def get_failed(self) -> list[Image]:
        """
        Get all images with failed processing status.

        Returns:
            List of Image instances with failed status.
        """
        stmt = select(Image).where(
            Image.processing_status == ProcessingStatus.FAILED
        ).order_by(Image.created_at)

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def get_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
        status: ProcessingStatus | None = None,
    ) -> list[Image]:
        """
        Get all images with optional filtering and pagination.

        Args:
            limit: Maximum number of images to return.
            offset: Number of images to skip.
            status: Filter by processing status.

        Returns:
            List of Image instances.
        """
        stmt = select(Image).order_by(Image.created_at.desc())

        if status:
            stmt = stmt.where(Image.processing_status == status)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def count(self, status: ProcessingStatus | None = None) -> int:
        """
        Count images, optionally filtered by status.

        Args:
            status: Filter by processing status.

        Returns:
            Number of images.
        """
        from sqlalchemy import func

        stmt = select(func.count(Image.id))

        if status:
            stmt = stmt.where(Image.processing_status == status)

        if self._session:
            return self._session.execute(stmt).scalar() or 0

        with session_scope() as session:
            return session.execute(stmt).scalar() or 0

    # ────────────────────────────────────────────────────────────────────────────
    # Update Operations
    # ────────────────────────────────────────────────────────────────────────────

    def update(self, image_id: int, **kwargs) -> Image | None:
        """
        Update an image record.

        Args:
            image_id: Primary key of the image.
            **kwargs: Fields to update.

        Returns:
            Updated Image instance or None if not found.
        """
        if self._session:
            image = self._session.get(Image, image_id)
            if image:
                for key, value in kwargs.items():
                    if hasattr(image, key):
                        setattr(image, key, value)
                self._session.flush()
            return image

        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                for key, value in kwargs.items():
                    if hasattr(image, key):
                        setattr(image, key, value)
                session.flush()
                session.refresh(image)
            return image

    def update_status(
        self,
        image_id: int,
        status: ProcessingStatus,
        error_message: str | None = None,
    ) -> Image | None:
        """
        Update processing status of an image.

        Args:
            image_id: Primary key of the image.
            status: New processing status.
            error_message: Error message if status is FAILED.

        Returns:
            Updated Image instance or None if not found.
        """
        update_data = {"processing_status": status}

        if status == ProcessingStatus.COMPLETED:
            update_data["processed_at"] = datetime.utcnow()
        elif status == ProcessingStatus.FAILED and error_message:
            update_data["error_message"] = error_message

        return self.update(image_id, **update_data)

    def mark_processing(self, image_id: int) -> Image | None:
        """Mark image as currently processing."""
        return self.update_status(image_id, ProcessingStatus.PROCESSING)

    def mark_completed(self, image_id: int) -> Image | None:
        """Mark image as completed."""
        return self.update_status(image_id, ProcessingStatus.COMPLETED)

    def mark_failed(self, image_id: int, error_message: str) -> Image | None:
        """Mark image as failed with error message."""
        return self.update_status(image_id, ProcessingStatus.FAILED, error_message)

    def set_ai_tags(self, image_id: int, tags: list[str]) -> Image | None:
        """
        Set AI tags for an image.

        Args:
            image_id: Primary key of the image.
            tags: List of AI-generated keywords.

        Returns:
            Updated Image instance or None if not found.
        """
        return self.update(image_id, ai_tags=tags)

    def update_stock_fields(
        self,
        image_id: int,
        categories: list[str] | None = None,
        editorial: bool | None = None,
    ) -> Image | None:
        """
        Update stock-related fields for an image.

        Args:
            image_id: Primary key of the image.
            categories: List of stock categories.
            editorial: Whether image is editorial content.

        Returns:
            Updated Image instance or None if not found.
        """
        update_data = {}
        if categories is not None:
            update_data["categories"] = categories
        if editorial is not None:
            update_data["editorial"] = editorial

        if update_data:
            return self.update(image_id, **update_data)
        return self.get_by_id(image_id)

    def get_ready_for_submission(self, stock_site: str) -> list[Image]:
        """
        Get images ready for submission to a stock site.

        Returns images that:
        - Have completed processing
        - Have categories assigned
        - Have not yet been submitted to the specified stock site

        Args:
            stock_site: Stock site identifier to check submissions against.

        Returns:
            List of Image instances ready for submission.
        """
        from db.models import StockSubmission

        # Subquery for images already submitted to this site
        subquery = select(StockSubmission.image_id).where(
            StockSubmission.stock_site == stock_site
        ).scalar_subquery()

        stmt = select(Image).where(
            Image.processing_status == ProcessingStatus.COMPLETED,
            Image.categories.isnot(None),
            Image.id.notin_(subquery),
        ).order_by(Image.created_at.desc())

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    # ────────────────────────────────────────────────────────────────────────────
    # Delete Operations
    # ────────────────────────────────────────────────────────────────────────────

    def delete(self, image_id: int) -> bool:
        """
        Delete an image record.

        Args:
            image_id: Primary key of the image.

        Returns:
            True if deleted, False if not found.
        """
        if self._session:
            image = self._session.get(Image, image_id)
            if image:
                self._session.delete(image)
                return True
            return False

        with session_scope() as session:
            image = session.get(Image, image_id)
            if image:
                session.delete(image)
                return True
            return False

    def delete_by_filepath(self, filepath: str) -> bool:
        """
        Delete an image record by filepath.

        Args:
            filepath: Full path to the image file.

        Returns:
            True if deleted, False if not found.
        """
        if self._session:
            image = self.get_by_filepath(filepath)
            if image:
                self._session.delete(image)
                return True
            return False

        with session_scope() as session:
            stmt = select(Image).where(Image.filepath == filepath)
            image = session.execute(stmt).scalar_one_or_none()
            if image:
                session.delete(image)
                return True
            return False


# ────────────────────────────────────────────────────────────────────────────────
# Convenience functions (without repository class)
# ────────────────────────────────────────────────────────────────────────────────

def image_exists(filepath: str) -> bool:
    """Check if an image exists by filepath."""
    return ImageRepository().exists_by_filepath(filepath)


def get_image_by_filepath(filepath: str) -> Image | None:
    """Get an image by filepath."""
    return ImageRepository().get_by_filepath(filepath)


def get_unprocessed_images(limit: int | None = None) -> list[Image]:
    """Get all unprocessed images."""
    return ImageRepository().get_unprocessed(limit)


def get_image_count(status: ProcessingStatus | None = None) -> int:
    """Get count of images, optionally filtered by status."""
    return ImageRepository().count(status)
