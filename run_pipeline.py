#!/usr/bin/env python3
"""
CLI entry point for the image processing pipeline.

Usage:
    python run_pipeline.py /path/to/photos
    python run_pipeline.py /path/to/photos --no-ai --verbose
    python run_pipeline.py --retry-failed
"""

import argparse
import logging
import sys
from pathlib import Path

from db.database import verify_connection, dispose_engine
from pipeline.processor import ImageProcessor, PipelineStats


def setup_logging(verbose: bool = False, log_file: str | None = None) -> None:
    """Configure logging for the pipeline run."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )


def print_progress(current: int, total: int, filename: str) -> None:
    """Print progress to console."""
    pct = (current / total) * 100 if total > 0 else 0
    print(f"[{current:4d}/{total:4d}] ({pct:5.1f}%) {filename}")


def run_pipeline(args: argparse.Namespace) -> int:
    """Run the image processing pipeline."""
    # Verify database connection
    print("Verifying database connection...")
    if not verify_connection():
        print("ERROR: Could not connect to database.")
        print("Please check your .env configuration and ensure PostgreSQL is running.")
        return 1

    print("Database connection OK\n")

    # Handle retry-failed mode
    if args.retry_failed:
        print("Retrying previously failed images...\n")
        processor = ImageProcessor(
            enable_ai_tagging=not args.no_ai,
            ai_model=args.model,
            max_tags=args.max_tags,
            use_tag_cache=not args.no_cache,
            progress_callback=print_progress if args.verbose else None
        )
        stats = processor.retry_failed()
        print("\n" + stats.summary())
        return 0 if stats.failed == 0 else 1

    # Validate input path
    input_path = Path(args.path)
    if not input_path.exists():
        print(f"ERROR: Path does not exist: {input_path}")
        return 1

    if not input_path.is_dir():
        print(f"ERROR: Path is not a directory: {input_path}")
        return 1

    # Initialize processor
    processor = ImageProcessor(
        skip_existing=not args.reprocess,
        skip_duplicates=not args.allow_duplicates,
        enable_ai_tagging=not args.no_ai,
        ai_model=args.model,
        max_tags=args.max_tags,
        use_tag_cache=not args.no_cache,
        progress_callback=print_progress if args.verbose else None
    )

    # Print configuration
    print("Pipeline Configuration:")
    print(f"  Input path: {input_path}")
    print(f"  Recursive: {args.recursive}")
    print(f"  Skip existing: {not args.reprocess}")
    print(f"  Skip duplicates: {not args.allow_duplicates}")
    print(f"  AI tagging: {not args.no_ai}")
    if not args.no_ai:
        print(f"  AI model: {args.model}")
        print(f"  Max tags: {args.max_tags}")
        print(f"  Use cache: {not args.no_cache}")
    print()

    # Run pipeline
    print("Starting pipeline...\n")
    stats = processor.process_directory(input_path, recursive=args.recursive)

    # Print results
    print("\n" + stats.summary())

    # Return appropriate exit code
    if stats.failed > 0:
        return 1
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process images: extract metadata, generate AI tags, store in database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py /path/to/photos
  python run_pipeline.py /path/to/photos -v --no-ai
  python run_pipeline.py /path/to/photos --model gpt-4o --max-tags 50
  python run_pipeline.py --retry-failed -v
        """
    )

    # Required arguments
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to directory containing images"
    )

    # Processing options
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        default=True,
        help="Process subdirectories (default: True)"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_false",
        dest="recursive",
        help="Don't process subdirectories"
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess images already in database"
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Process duplicate files (same content)"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed images"
    )

    # AI tagging options
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI tagging"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model for tagging (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--max-tags",
        type=int,
        default=30,
        help="Maximum tags per image (default: 30)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable AI tag caching"
    )

    # Output options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress output"
    )
    parser.add_argument(
        "--log-file",
        help="Write logs to file"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.retry_failed and not args.path:
        parser.error("the following arguments are required: path")

    # Setup logging
    setup_logging(args.verbose, args.log_file)

    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        return 130
    except Exception as e:
        print(f"\nERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    sys.exit(main())
