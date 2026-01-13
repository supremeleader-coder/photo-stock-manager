"""
Database connection and session management for Photo Stock Manager.

Provides:
- Connection pooling via SQLAlchemy
- Session factory with context manager support
- Database initialization and verification
- Configuration loading from environment variables
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────

def get_database_url() -> str:
    """
    Build PostgreSQL connection URL from environment variables.

    Returns:
        PostgreSQL connection string in SQLAlchemy format.

    Raises:
        ValueError: If required environment variables are missing.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "photo_library")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")

    if not password:
        raise ValueError(
            "DB_PASSWORD environment variable is required. "
            "Please set it in your .env file."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def get_pool_settings() -> dict:
    """
    Get connection pool settings from environment variables.

    Returns:
        Dictionary with pool configuration.
    """
    return {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_pre_ping": True,  # Verify connections before use
        "pool_recycle": 3600,   # Recycle connections after 1 hour
    }


# ────────────────────────────────────────────────────────────────────────────────
# Engine and Session Management
# ────────────────────────────────────────────────────────────────────────────────

# Global engine instance (lazy initialization)
_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine with connection pooling.

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    global _engine

    if _engine is None:
        database_url = get_database_url()
        pool_settings = get_pool_settings()

        logger.info("Creating database engine with connection pooling...")
        _engine = create_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            **pool_settings
        )
        logger.info(
            f"Engine created (pool_size={pool_settings['pool_size']}, "
            f"max_overflow={pool_settings['max_overflow']})"
        )

    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get or create the session factory.

    Returns:
        Configured sessionmaker instance.
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    return _session_factory


def get_session() -> Session:
    """
    Create a new database session.

    Returns:
        New SQLAlchemy Session instance.

    Note:
        Caller is responsible for closing the session.
        Prefer using session_scope() context manager instead.
    """
    factory = get_session_factory()
    return factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic commit/rollback.

    Yields:
        SQLAlchemy Session instance.

    Example:
        with session_scope() as session:
            image = session.query(Image).first()
            image.processing_status = ProcessingStatus.COMPLETED
        # Automatically commits on success, rolls back on exception
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rollback due to: {e}")
        raise
    finally:
        session.close()


# ────────────────────────────────────────────────────────────────────────────────
# Database Initialization
# ────────────────────────────────────────────────────────────────────────────────

def init_db() -> bool:
    """
    Initialize database by creating all tables.

    Returns:
        True if successful, False otherwise.
    """
    try:
        engine = get_engine()
        logger.info("Creating database tables...")
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def verify_connection() -> bool:
    """
    Verify database connection is working.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("Database connection verified successfully!")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_db_info() -> dict:
    """
    Get database connection information (for debugging).

    Returns:
        Dictionary with connection details (password masked).
    """
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "photo_library"),
        "user": os.getenv("DB_USER", "postgres"),
        "pool_size": os.getenv("DB_POOL_SIZE", "5"),
        "max_overflow": os.getenv("DB_MAX_OVERFLOW", "10"),
    }


# ────────────────────────────────────────────────────────────────────────────────
# Cleanup
# ────────────────────────────────────────────────────────────────────────────────

def dispose_engine() -> None:
    """
    Dispose of the engine and close all connections.

    Call this when shutting down the application.
    """
    global _engine, _session_factory

    if _engine is not None:
        logger.info("Disposing database engine...")
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed.")
