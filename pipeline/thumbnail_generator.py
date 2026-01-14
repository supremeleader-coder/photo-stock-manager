"""
Thumbnail generation module for the pipeline.

Generates thumbnails for images and stores them in a dedicated folder.
Thumbnails are organized in subfolders based on image ID to avoid
having thousands of files in a single directory.
"""

import logging
import os
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Default thumbnail settings
DEFAULT_WIDTH = 300
DEFAULT_QUALITY = 85
DEFAULT_FORMAT = "JPEG"


class ThumbnailGenerator:
    """
    Generates thumbnails for images.

    Thumbnails are stored in a dedicated folder with subdirectories
    based on image ID (e.g., thumbnails/000/001/image_1.jpg).
    """

    def __init__(
        self,
        output_dir: str | Path = "thumbnails",
        width: int = DEFAULT_WIDTH,
        quality: int = DEFAULT_QUALITY
    ):
        """
        Initialize thumbnail generator.

        Args:
            output_dir: Directory to store thumbnails.
            width: Target width in pixels (height is proportional).
            quality: JPEG quality (1-100).
        """
        self.output_dir = Path(output_dir)
        self.width = width
        self.quality = quality

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        source_path: str | Path,
        image_id: int | None = None,
        filename: str | None = None
    ) -> str | None:
        """
        Generate a thumbnail for an image.

        Args:
            source_path: Path to the source image.
            image_id: Database ID for organizing thumbnails (optional).
            filename: Original filename for naming thumbnail (optional).

        Returns:
            Path to the generated thumbnail, or None if generation failed.
        """
        source_path = Path(source_path)

        if not source_path.exists():
            logger.error(f"Source image not found: {source_path}")
            return None

        try:
            # Determine output path
            thumb_path = self._get_thumbnail_path(source_path, image_id, filename)

            # Create parent directory if needed
            thumb_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate thumbnail
            with Image.open(source_path) as img:
                # Convert to RGB if necessary (for JPEG output)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Calculate new dimensions (maintain aspect ratio)
                aspect_ratio = img.height / img.width
                new_width = self.width
                new_height = int(new_width * aspect_ratio)

                # Resize using high-quality resampling
                img_resized = img.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS
                )

                # Save thumbnail
                img_resized.save(
                    thumb_path,
                    format=DEFAULT_FORMAT,
                    quality=self.quality,
                    optimize=True
                )

            logger.debug(f"Generated thumbnail: {thumb_path}")
            return str(thumb_path)

        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {source_path}: {e}")
            return None

    def _get_thumbnail_path(
        self,
        source_path: Path,
        image_id: int | None,
        filename: str | None
    ) -> Path:
        """
        Determine the path for a thumbnail.

        Uses a hierarchical structure based on image ID:
        thumbnails/000/001/image_1.jpg for ID 1
        thumbnails/001/234/image_1234.jpg for ID 1234

        Falls back to hash-based structure if no ID provided.
        """
        # Use provided filename or derive from source
        base_name = filename or source_path.stem
        thumb_filename = f"{base_name}_thumb.jpg"

        if image_id is not None:
            # Create hierarchical structure: ID 12345 -> 012/345/
            id_str = f"{image_id:06d}"
            subdir1 = id_str[:3]
            subdir2 = id_str[3:]
            return self.output_dir / subdir1 / subdir2 / thumb_filename
        else:
            # Fallback: use first chars of filename
            prefix = base_name[:2].lower() if len(base_name) >= 2 else "xx"
            return self.output_dir / prefix / thumb_filename

    def delete(self, thumbnail_path: str | Path) -> bool:
        """
        Delete a thumbnail file.

        Args:
            thumbnail_path: Path to the thumbnail to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        try:
            path = Path(thumbnail_path)
            if path.exists():
                path.unlink()
                logger.debug(f"Deleted thumbnail: {path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete thumbnail {thumbnail_path}: {e}")
            return False

    def exists(self, thumbnail_path: str | Path) -> bool:
        """Check if a thumbnail exists."""
        return Path(thumbnail_path).exists() if thumbnail_path else False


def generate_thumbnail(
    source_path: str | Path,
    output_dir: str | Path = "thumbnails",
    image_id: int | None = None,
    width: int = DEFAULT_WIDTH
) -> str | None:
    """
    Convenience function to generate a single thumbnail.

    Args:
        source_path: Path to the source image.
        output_dir: Directory to store thumbnails.
        image_id: Database ID for organizing thumbnails.
        width: Target width in pixels.

    Returns:
        Path to the generated thumbnail, or None if failed.
    """
    generator = ThumbnailGenerator(output_dir=output_dir, width=width)
    return generator.generate(source_path, image_id=image_id)
