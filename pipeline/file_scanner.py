"""
File scanner module for discovering images in directories.

Provides recursive directory scanning with filtering for image files.
"""

import logging
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".tiff", ".tif", ".webp", ".heic", ".heif"
}


class FileScanner:
    """
    Scanner for discovering image files in directories.

    Attributes:
        extensions: Set of file extensions to include.
        recursive: Whether to scan subdirectories.
    """

    def __init__(
        self,
        extensions: set[str] | None = None,
        recursive: bool = True
    ):
        """
        Initialize the file scanner.

        Args:
            extensions: Set of file extensions to scan for.
                       Defaults to IMAGE_EXTENSIONS.
            recursive: Whether to scan subdirectories.
        """
        self.extensions = extensions or IMAGE_EXTENSIONS
        self.recursive = recursive

    def scan(self, directory: str | Path) -> list[Path]:
        """
        Scan directory for image files.

        Args:
            directory: Path to directory to scan.

        Returns:
            List of paths to image files, sorted by name.

        Raises:
            ValueError: If directory doesn't exist or isn't a directory.
        """
        directory = Path(directory)

        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        images = list(self._scan_iter(directory))
        images.sort(key=lambda p: p.name.lower())

        logger.info(f"Found {len(images)} image(s) in {directory}")
        return images

    def _scan_iter(self, directory: Path) -> Iterator[Path]:
        """
        Iterate over image files in directory.

        Args:
            directory: Path to directory to scan.

        Yields:
            Paths to image files.
        """
        try:
            if self.recursive:
                pattern_iter = directory.rglob("*")
            else:
                pattern_iter = directory.iterdir()

            for path in pattern_iter:
                if self._is_image(path):
                    yield path

        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
        except Exception as e:
            logger.error(f"Error scanning directory: {e}")

    def _is_image(self, path: Path) -> bool:
        """
        Check if path is a valid image file.

        Args:
            path: Path to check.

        Returns:
            True if path is an image file.
        """
        return (
            path.is_file() and
            path.suffix.lower() in self.extensions and
            not path.name.startswith(".")  # Skip hidden files
        )

    def count(self, directory: str | Path) -> int:
        """
        Count image files in directory without loading all paths.

        Args:
            directory: Path to directory to scan.

        Returns:
            Number of image files found.
        """
        return sum(1 for _ in self._scan_iter(Path(directory)))


def scan_directory(
    directory: str | Path,
    recursive: bool = True,
    extensions: set[str] | None = None
) -> list[Path]:
    """
    Convenience function to scan a directory for images.

    Args:
        directory: Path to directory to scan.
        recursive: Whether to scan subdirectories.
        extensions: Set of file extensions to include.

    Returns:
        List of paths to image files.
    """
    scanner = FileScanner(extensions=extensions, recursive=recursive)
    return scanner.scan(directory)
