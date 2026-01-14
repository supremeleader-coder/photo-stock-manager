"""
Main image processing pipeline orchestrator.

Coordinates all pipeline stages:
1. File discovery
2. Duplicate checking
3. Metadata extraction
4. AI tagging
5. Database storage
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from db.models import ProcessingStatus
from pipeline.file_scanner import FileScanner
from pipeline.duplicate_handler import DuplicateHandler
from pipeline.metadata_extractor import MetadataExtractor
from pipeline.ai_tagger import AITagger
from pipeline.storage_handler import StorageHandler

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single image."""
    filepath: Path
    success: bool
    image_id: int | None = None
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    tags_count: int = 0
    processing_time: float = 0.0


@dataclass
class PipelineStats:
    """Statistics for a pipeline run."""
    total_found: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    results: list[ProcessingResult] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Get total duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def summary(self) -> str:
        """Generate summary string."""
        lines = [
            "=" * 50,
            "Pipeline Processing Complete",
            "=" * 50,
            f"Total images found: {self.total_found}",
            f"Successfully processed: {self.processed}",
            f"Skipped (duplicates/existing): {self.skipped}",
            f"Failed: {self.failed}",
            f"Duration: {self.duration_seconds:.1f} seconds",
        ]

        if self.failed > 0:
            lines.append("")
            lines.append("Failed images:")
            for r in self.results:
                if not r.success and not r.skipped:
                    lines.append(f"  - {r.filepath.name}: {r.error}")

        return "\n".join(lines)


class ImageProcessor:
    """
    Main pipeline processor for batch image processing.

    Orchestrates the complete processing workflow for images:
    1. Scans directory for image files
    2. Checks for duplicates
    3. Extracts metadata
    4. Generates AI tags
    5. Stores in database
    """

    def __init__(
        self,
        skip_existing: bool = True,
        skip_duplicates: bool = True,
        enable_ai_tagging: bool = True,
        ai_model: str = "gpt-4o-mini",
        max_tags: int = 30,
        use_tag_cache: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None
    ):
        """
        Initialize the image processor.

        Args:
            skip_existing: Skip images already in database.
            skip_duplicates: Skip content-duplicate images.
            enable_ai_tagging: Whether to generate AI tags.
            ai_model: OpenAI model for tagging.
            max_tags: Maximum tags per image.
            use_tag_cache: Use cached AI tags.
            progress_callback: Callback(current, total, filename) for progress.
        """
        self.skip_existing = skip_existing
        self.skip_duplicates = skip_duplicates
        self.enable_ai_tagging = enable_ai_tagging

        # Initialize components
        self.scanner = FileScanner()
        self.duplicate_handler = DuplicateHandler()
        self.metadata_extractor = MetadataExtractor()
        self.ai_tagger = AITagger(
            model=ai_model,
            max_tags=max_tags,
            use_cache=use_tag_cache
        ) if enable_ai_tagging else None
        self.storage = StorageHandler()
        self.progress_callback = progress_callback

    def process_directory(
        self,
        directory: str | Path,
        recursive: bool = True
    ) -> PipelineStats:
        """
        Process all images in a directory.

        Args:
            directory: Path to directory to process.
            recursive: Whether to scan subdirectories.

        Returns:
            PipelineStats with processing results.
        """
        directory = Path(directory)
        stats = PipelineStats()

        logger.info(f"Starting pipeline for: {directory}")

        # Stage 1: File Discovery
        self.scanner.recursive = recursive
        images = self.scanner.scan(directory)
        stats.total_found = len(images)

        if not images:
            logger.info("No images found to process")
            stats.end_time = datetime.utcnow()
            return stats

        logger.info(f"Found {len(images)} images to process")

        # Stage 2-5: Process each image
        for i, filepath in enumerate(images, 1):
            if self.progress_callback:
                self.progress_callback(i, len(images), filepath.name)

            result = self.process_single(filepath)
            stats.results.append(result)

            if result.success:
                stats.processed += 1
            elif result.skipped:
                stats.skipped += 1
            else:
                stats.failed += 1

        stats.end_time = datetime.utcnow()
        logger.info(stats.summary())

        return stats

    def process_single(self, filepath: str | Path) -> ProcessingResult:
        """
        Process a single image through the pipeline.

        Args:
            filepath: Path to the image file.

        Returns:
            ProcessingResult with outcome details.
        """
        import time
        start_time = time.time()

        filepath = Path(filepath).resolve()
        result = ProcessingResult(filepath=filepath, success=False)

        try:
            # Stage 2: Duplicate Check
            if self.skip_existing or self.skip_duplicates:
                dup_result = self.duplicate_handler.check_duplicate(
                    filepath,
                    check_hash=self.skip_duplicates,
                    check_filename=False  # We handle filename later
                )

                if dup_result.is_duplicate:
                    result.skipped = True
                    result.skip_reason = f"Duplicate ({dup_result.duplicate_type})"
                    result.image_id = dup_result.existing_id
                    logger.debug(f"Skipping duplicate: {filepath.name}")
                    return result

            # Stage 3: Metadata Extraction
            logger.debug(f"Extracting metadata: {filepath.name}")
            metadata = self.metadata_extractor.extract(filepath)

            # Stage 4: AI Tagging
            ai_tags: list[str] = []
            if self.ai_tagger:
                logger.debug(f"Generating AI tags: {filepath.name}")
                try:
                    ai_tags = self.ai_tagger.tag(filepath)
                    result.tags_count = len(ai_tags)
                except Exception as e:
                    logger.warning(f"AI tagging failed for {filepath.name}: {e}")
                    # Continue without tags

            # Stage 5: Database Storage
            logger.debug(f"Storing in database: {filepath.name}")
            image = self.storage.store_complete(metadata, ai_tags)

            result.success = True
            result.image_id = image.id
            result.processing_time = time.time() - start_time

            logger.info(
                f"Processed: {filepath.name} (ID: {image.id}, "
                f"{result.tags_count} tags, {result.processing_time:.2f}s)"
            )

        except Exception as e:
            result.error = str(e)
            result.processing_time = time.time() - start_time
            logger.error(f"Failed to process {filepath.name}: {e}")

        return result

    def retry_failed(self) -> PipelineStats:
        """
        Retry processing of previously failed images.

        Returns:
            PipelineStats with retry results.
        """
        stats = PipelineStats()

        failed_images = self.storage.get_failed()
        stats.total_found = len(failed_images)

        if not failed_images:
            logger.info("No failed images to retry")
            stats.end_time = datetime.utcnow()
            return stats

        logger.info(f"Retrying {len(failed_images)} failed images")

        for i, image in enumerate(failed_images, 1):
            if self.progress_callback:
                self.progress_callback(i, len(failed_images), image.filename)

            filepath = Path(image.filepath)
            if not filepath.exists():
                logger.warning(f"File no longer exists: {filepath}")
                stats.failed += 1
                continue

            # Re-process
            result = self._reprocess_existing(image, filepath)
            stats.results.append(result)

            if result.success:
                stats.processed += 1
            else:
                stats.failed += 1

        stats.end_time = datetime.utcnow()
        return stats

    def _reprocess_existing(self, image, filepath: Path) -> ProcessingResult:
        """Re-process an existing database record."""
        import time
        start_time = time.time()

        result = ProcessingResult(filepath=filepath, success=False)
        result.image_id = image.id

        try:
            self.storage.mark_processing(image.id)

            # Re-extract metadata
            metadata = self.metadata_extractor.extract(filepath)

            # Re-generate tags
            ai_tags: list[str] = []
            if self.ai_tagger:
                ai_tags = self.ai_tagger.tag(filepath)
                result.tags_count = len(ai_tags)

            # Update record
            self.storage.mark_completed(image.id, ai_tags)
            result.success = True
            result.processing_time = time.time() - start_time

        except Exception as e:
            result.error = str(e)
            self.storage.mark_failed(image.id, str(e))

        return result


def process_folder(
    folder: str | Path,
    recursive: bool = True,
    skip_existing: bool = True,
    enable_ai: bool = True,
    verbose: bool = False
) -> PipelineStats:
    """
    Convenience function to process a folder of images.

    Args:
        folder: Path to folder to process.
        recursive: Scan subdirectories.
        skip_existing: Skip already-processed images.
        enable_ai: Enable AI tagging.
        verbose: Print progress to console.

    Returns:
        PipelineStats with results.
    """
    def progress(current: int, total: int, filename: str) -> None:
        if verbose:
            print(f"[{current}/{total}] Processing: {filename}")

    processor = ImageProcessor(
        skip_existing=skip_existing,
        enable_ai_tagging=enable_ai,
        progress_callback=progress if verbose else None
    )

    return processor.process_directory(folder, recursive=recursive)
