#!/usr/bin/env python3
"""
Database initialization script for Photo Stock Manager.

This script:
1. Verifies database connection
2. Creates all tables defined in models
3. Optionally displays connection info for debugging

Usage:
    python init_db.py [--verbose]
"""

import argparse
import logging
import sys

from db.database import (
    dispose_engine,
    get_db_info,
    init_db,
    verify_connection,
)
from db.models import ProcessingStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    parser = argparse.ArgumentParser(
        description="Initialize Photo Stock Manager database"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output including connection info"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only verify connection, don't create tables"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print("Photo Stock Manager - Database Initialization")
    print("=" * 60)
    print()

    # Show connection info (with password masked)
    if args.verbose:
        print("Connection Settings:")
        db_info = get_db_info()
        for key, value in db_info.items():
            print(f"  {key}: {value}")
        print()

    # Step 1: Verify connection
    print("[1/2] Verifying database connection...")
    if not verify_connection():
        print()
        print("ERROR: Could not connect to database!")
        print()
        print("Please check:")
        print("  1. PostgreSQL is running")
        print("  2. Database 'photo_library' exists")
        print("  3. .env file has correct credentials")
        print()
        print("To create the database:")
        print("  - Open pgAdmin")
        print("  - Right-click Databases > Create > Database")
        print("  - Name: photo_library")
        print()
        dispose_engine()
        sys.exit(1)

    print("  -> Connection successful!")
    print()

    if args.check_only:
        print("Check-only mode: Skipping table creation.")
        dispose_engine()
        sys.exit(0)

    # Step 2: Create tables
    print("[2/2] Creating database tables...")
    if not init_db():
        print()
        print("ERROR: Failed to create tables!")
        print("Check the logs above for details.")
        dispose_engine()
        sys.exit(1)

    print("  -> Tables created successfully!")
    print()

    # Summary
    print("=" * 60)
    print("Database initialization complete!")
    print("=" * 60)
    print()
    print("Tables created:")
    print("  - images (with indexes on filename, filepath, status, hash)")
    print()
    print("Processing statuses available:")
    for status in ProcessingStatus:
        print(f"  - {status.value}")
    print()
    print("Next steps:")
    print("  1. Run the image processing pipeline")
    print("  2. Check the 'images' table in pgAdmin to verify")
    print()

    # Clean up
    dispose_engine()


if __name__ == "__main__":
    main()
