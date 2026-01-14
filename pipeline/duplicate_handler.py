"""
Duplicate detection and filename handling module.

Provides:
- File hash calculation for true duplicate detection
- Filename collision handling with auto-incrementing suffixes
- Database integration for checking existing files
"""

import hashlib
import logging
from pathlib import Path
from typing import NamedTuple

from db.operations import ImageRepository

logger = logging.getLogger(__name__)


class DuplicateCheckResult(NamedTuple):
    """Result of duplicate check operation."""
    is_duplicate: bool
    duplicate_type: str | None  # "hash" or "filename" or None
    existing_id: int | None     # ID of existing record if duplicate
    suggested_filename: str     # Original or new unique filename


class DuplicateHandler:
    """
    Handler for detecting duplicates and managing filename collisions.

    Supports two types of duplicate detection:
    1. Hash-based: Detects identical files (same content)
    2. Filename-based: Detects same filename in database

    When filename collision occurs, generates unique filename with suffix.
    """

    def __init__(self, repository: ImageRepository | None = None):
        """
        Initialize duplicate handler.

        Args:
            repository: ImageRepository instance for database queries.
                       If None, creates a new one.
        """
        self.repository = repository or ImageRepository()

    def calculate_hash(self, filepath: str | Path) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            filepath: Path to the file.

        Returns:
            Hexadecimal hash string.
        """
        filepath = Path(filepath)
        sha256_hash = hashlib.sha256()

        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def check_duplicate(
        self,
        filepath: str | Path,
        check_hash: bool = True,
        check_filename: bool = True
    ) -> DuplicateCheckResult:
        """
        Check if file is a duplicate.

        Args:
            filepath: Path to the file to check.
            check_hash: Whether to check for content duplicates.
            check_filename: Whether to check for filename duplicates.

        Returns:
            DuplicateCheckResult with duplicate status and suggested filename.
        """
        filepath = Path(filepath)
        filename = filepath.name

        # Check by hash first (true duplicates)
        if check_hash:
            file_hash = self.calculate_hash(filepath)
            existing = self.repository.get_by_hash(file_hash)
            if existing:
                logger.info(f"Found hash duplicate: {filename} matches ID {existing.id}")
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_type="hash",
                    existing_id=existing.id,
                    suggested_filename=filename
                )

        # Check by filepath (exact path match)
        filepath_str = str(filepath.resolve())
        existing = self.repository.get_by_filepath(filepath_str)
        if existing:
            logger.info(f"File already in database: {filepath_str}")
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_type="filepath",
                existing_id=existing.id,
                suggested_filename=filename
            )

        # Check by filename (name collision)
        if check_filename:
            matches = self.repository.get_by_filename(filename)
            if matches:
                new_filename = self._generate_unique_filename(filename)
                logger.info(f"Filename collision: {filename} -> {new_filename}")
                return DuplicateCheckResult(
                    is_duplicate=False,
                    duplicate_type="filename",
                    existing_id=None,
                    suggested_filename=new_filename
                )

        # No duplicates
        return DuplicateCheckResult(
            is_duplicate=False,
            duplicate_type=None,
            existing_id=None,
            suggested_filename=filename
        )

    def _generate_unique_filename(self, filename: str) -> str:
        """
        Generate a unique filename by adding numeric suffix.

        Format: original_name_001.jpg, original_name_002.jpg, etc.

        Args:
            filename: Original filename.

        Returns:
            Unique filename that doesn't exist in database.
        """
        path = Path(filename)
        stem = path.stem
        suffix = path.suffix

        counter = 1
        while counter < 10000:  # Safety limit
            new_filename = f"{stem}_{counter:03d}{suffix}"
            if not self.repository.get_by_filename(new_filename):
                return new_filename
            counter += 1

        # Fallback: use timestamp
        import time
        timestamp = int(time.time())
        return f"{stem}_{timestamp}{suffix}"

    def is_content_duplicate(self, filepath: str | Path) -> bool:
        """
        Check if file content already exists in database.

        Args:
            filepath: Path to the file.

        Returns:
            True if identical file exists in database.
        """
        file_hash = self.calculate_hash(filepath)
        return self.repository.exists_by_hash(file_hash)

    def is_filepath_registered(self, filepath: str | Path) -> bool:
        """
        Check if filepath is already registered in database.

        Args:
            filepath: Path to check.

        Returns:
            True if filepath exists in database.
        """
        filepath_str = str(Path(filepath).resolve())
        return self.repository.exists_by_filepath(filepath_str)
