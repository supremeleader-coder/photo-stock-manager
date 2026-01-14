"""
AI tagging module for the pipeline.

Wraps the photo_tagger module to provide:
- Consistent interface for the pipeline
- Error handling and retries
- Timeout support
- Integration with pipeline logging
"""

import logging
from pathlib import Path
from typing import Any

# Import the existing photo_tagger module
from photo_tagger import tag_photo as _tag_photo, get_file_hash

logger = logging.getLogger(__name__)


class AITaggerError(Exception):
    """Exception raised when AI tagging fails."""
    pass


class AITagger:
    """
    AI-powered image tagging using OpenAI Vision API.

    Wraps the existing photo_tagger module for pipeline integration.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tags: int = 30,
        detail: str = "high",
        use_cache: bool = True,
        max_retries: int = 3
    ):
        """
        Initialize AI tagger.

        Args:
            model: OpenAI model to use (gpt-4o-mini, gpt-4o, etc.)
            max_tags: Maximum number of tags to generate.
            detail: Image detail level for API ("low", "high", "auto").
            use_cache: Whether to use file-based caching.
            max_retries: Maximum retry attempts on failure.
        """
        self.model = model
        self.max_tags = max_tags
        self.detail = detail
        self.use_cache = use_cache
        self.max_retries = max_retries

    def tag(self, filepath: str | Path) -> list[str]:
        """
        Generate AI tags for an image.

        Args:
            filepath: Path to the image file.

        Returns:
            List of lowercase keyword strings.

        Raises:
            AITaggerError: If tagging fails after all retries.
            FileNotFoundError: If file doesn't exist.
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Image not found: {filepath}")

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                tags = _tag_photo(
                    filepath,
                    model=self.model,
                    max_tags=self.max_tags,
                    detail=self.detail,
                    use_cache=self.use_cache
                )
                logger.debug(f"Generated {len(tags)} tags for {filepath.name}")
                return tags

            except FileNotFoundError:
                raise

            except Exception as e:
                last_error = e
                logger.warning(
                    f"AI tagging attempt {attempt}/{self.max_retries} failed "
                    f"for {filepath.name}: {e}"
                )
                if attempt < self.max_retries:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise AITaggerError(
            f"Failed to tag {filepath.name} after {self.max_retries} attempts: "
            f"{last_error}"
        )

    def tag_batch(
        self,
        filepaths: list[Path],
        continue_on_error: bool = True
    ) -> dict[Path, list[str] | None]:
        """
        Generate AI tags for multiple images.

        Args:
            filepaths: List of paths to image files.
            continue_on_error: If True, continue processing after errors.

        Returns:
            Dictionary mapping paths to tag lists (or None if failed).
        """
        results: dict[Path, list[str] | None] = {}

        for i, filepath in enumerate(filepaths, 1):
            logger.info(f"Tagging image {i}/{len(filepaths)}: {filepath.name}")

            try:
                tags = self.tag(filepath)
                results[filepath] = tags
            except Exception as e:
                logger.error(f"Failed to tag {filepath.name}: {e}")
                results[filepath] = None
                if not continue_on_error:
                    raise

        return results

    def get_cached_tags(self, filepath: str | Path) -> list[str] | None:
        """
        Get cached tags for a file if available.

        Args:
            filepath: Path to the image file.

        Returns:
            Cached tags or None if not cached.
        """
        from photo_tagger import load_cached_tags

        filepath = Path(filepath)
        if not filepath.exists():
            return None

        file_hash = get_file_hash(filepath)
        return load_cached_tags(file_hash)

    def is_cached(self, filepath: str | Path) -> bool:
        """
        Check if tags are cached for a file.

        Args:
            filepath: Path to the image file.

        Returns:
            True if cached tags exist.
        """
        return self.get_cached_tags(filepath) is not None


def generate_tags(
    filepath: str | Path,
    model: str = "gpt-4o-mini",
    max_tags: int = 30,
    use_cache: bool = True
) -> list[str]:
    """
    Convenience function to generate tags for an image.

    Args:
        filepath: Path to the image file.
        model: OpenAI model to use.
        max_tags: Maximum number of tags.
        use_cache: Whether to use caching.

    Returns:
        List of tag strings.
    """
    tagger = AITagger(model=model, max_tags=max_tags, use_cache=use_cache)
    return tagger.tag(filepath)
