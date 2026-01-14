"""
Image Processing Pipeline for Photo Stock Manager.

This module provides a complete pipeline for:
- Scanning directories for images
- Extracting metadata and EXIF data
- Generating AI tags
- Detecting and handling duplicates
- Storing results in PostgreSQL
"""

from pipeline.file_scanner import FileScanner, scan_directory
from pipeline.duplicate_handler import DuplicateHandler
from pipeline.metadata_extractor import MetadataExtractor
from pipeline.ai_tagger import AITagger
from pipeline.storage_handler import StorageHandler
from pipeline.processor import ImageProcessor

__all__ = [
    "FileScanner",
    "scan_directory",
    "DuplicateHandler",
    "MetadataExtractor",
    "AITagger",
    "StorageHandler",
    "ImageProcessor",
]
