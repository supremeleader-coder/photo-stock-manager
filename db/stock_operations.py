"""
Database operations for stock photo submissions.

Provides StockSubmissionRepository class with methods for:
- Creating submission records
- Tracking submission status
- Querying submissions by status, site, or image
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from db.database import session_scope
from db.models import StockSubmission, SubmissionStatus, Image

logger = logging.getLogger(__name__)


class StockSubmissionRepository:
    """
    Repository for StockSubmission database operations.

    Provides CRUD operations and queries for the stock_submissions table.
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
        image_id: int,
        stock_site: str,
        stock_photo_id: str | None = None,
        status: SubmissionStatus = SubmissionStatus.PENDING,
    ) -> StockSubmission:
        """
        Create a new stock submission record.

        Args:
            image_id: ID of the image being submitted.
            stock_site: Stock site identifier (e.g., "shutterstock").
            stock_photo_id: ID assigned by the stock site (if known).
            status: Initial submission status.

        Returns:
            Created StockSubmission instance.
        """
        submission = StockSubmission(
            image_id=image_id,
            stock_site=stock_site,
            stock_photo_id=stock_photo_id,
            status=status,
        )

        if self._session:
            self._session.add(submission)
            self._session.flush()
        else:
            with session_scope() as session:
                session.add(submission)
                session.flush()
                session.refresh(submission)

        logger.debug(f"Created submission record: {submission}")
        return submission

    # ────────────────────────────────────────────────────────────────────────────
    # Read Operations
    # ────────────────────────────────────────────────────────────────────────────

    def get_by_id(self, submission_id: int) -> StockSubmission | None:
        """
        Get submission by ID.

        Args:
            submission_id: Primary key of the submission.

        Returns:
            StockSubmission instance or None if not found.
        """
        if self._session:
            return self._session.get(StockSubmission, submission_id)

        with session_scope() as session:
            return session.get(StockSubmission, submission_id)

    def get_by_image(self, image_id: int) -> list[StockSubmission]:
        """
        Get all submissions for an image.

        Args:
            image_id: ID of the image.

        Returns:
            List of StockSubmission instances.
        """
        stmt = select(StockSubmission).where(
            StockSubmission.image_id == image_id
        ).order_by(StockSubmission.created_at.desc())

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def get_by_image_and_site(
        self, image_id: int, stock_site: str
    ) -> StockSubmission | None:
        """
        Get submission for a specific image and stock site.

        Args:
            image_id: ID of the image.
            stock_site: Stock site identifier.

        Returns:
            StockSubmission instance or None if not found.
        """
        stmt = select(StockSubmission).where(
            and_(
                StockSubmission.image_id == image_id,
                StockSubmission.stock_site == stock_site,
            )
        )

        if self._session:
            return self._session.execute(stmt).scalar_one_or_none()

        with session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()

    def get_by_status(
        self,
        status: SubmissionStatus,
        stock_site: str | None = None,
    ) -> list[StockSubmission]:
        """
        Get all submissions with a specific status.

        Args:
            status: Submission status to filter by.
            stock_site: Optional stock site to filter by.

        Returns:
            List of StockSubmission instances.
        """
        stmt = select(StockSubmission).where(StockSubmission.status == status)

        if stock_site:
            stmt = stmt.where(StockSubmission.stock_site == stock_site)

        stmt = stmt.order_by(StockSubmission.created_at.desc())

        if self._session:
            return list(self._session.execute(stmt).scalars().all())

        with session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def get_pending(self, stock_site: str | None = None) -> list[StockSubmission]:
        """
        Get all pending submissions.

        Args:
            stock_site: Optional stock site to filter by.

        Returns:
            List of pending StockSubmission instances.
        """
        return self.get_by_status(SubmissionStatus.PENDING, stock_site)

    def get_submitted(self, stock_site: str | None = None) -> list[StockSubmission]:
        """
        Get all submitted (awaiting review) submissions.

        Args:
            stock_site: Optional stock site to filter by.

        Returns:
            List of submitted StockSubmission instances.
        """
        return self.get_by_status(SubmissionStatus.SUBMITTED, stock_site)

    def get_by_stock_photo_id(
        self, stock_site: str, stock_photo_id: str
    ) -> StockSubmission | None:
        """
        Get submission by stock site's photo ID.

        Args:
            stock_site: Stock site identifier.
            stock_photo_id: ID assigned by the stock site.

        Returns:
            StockSubmission instance or None if not found.
        """
        stmt = select(StockSubmission).where(
            and_(
                StockSubmission.stock_site == stock_site,
                StockSubmission.stock_photo_id == stock_photo_id,
            )
        )

        if self._session:
            return self._session.execute(stmt).scalar_one_or_none()

        with session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()

    def count_by_status(
        self, status: SubmissionStatus, stock_site: str | None = None
    ) -> int:
        """
        Count submissions by status.

        Args:
            status: Submission status to count.
            stock_site: Optional stock site to filter by.

        Returns:
            Number of submissions.
        """
        from sqlalchemy import func

        stmt = select(func.count(StockSubmission.id)).where(
            StockSubmission.status == status
        )

        if stock_site:
            stmt = stmt.where(StockSubmission.stock_site == stock_site)

        if self._session:
            return self._session.execute(stmt).scalar() or 0

        with session_scope() as session:
            return session.execute(stmt).scalar() or 0

    # ────────────────────────────────────────────────────────────────────────────
    # Update Operations
    # ────────────────────────────────────────────────────────────────────────────

    def update(self, submission_id: int, **kwargs) -> StockSubmission | None:
        """
        Update a submission record.

        Args:
            submission_id: Primary key of the submission.
            **kwargs: Fields to update.

        Returns:
            Updated StockSubmission instance or None if not found.
        """
        if self._session:
            submission = self._session.get(StockSubmission, submission_id)
            if submission:
                for key, value in kwargs.items():
                    if hasattr(submission, key):
                        setattr(submission, key, value)
                self._session.flush()
            return submission

        with session_scope() as session:
            submission = session.get(StockSubmission, submission_id)
            if submission:
                for key, value in kwargs.items():
                    if hasattr(submission, key):
                        setattr(submission, key, value)
                session.flush()
                session.refresh(submission)
            return submission

    def mark_submitted(
        self, submission_id: int, stock_photo_id: str | None = None
    ) -> StockSubmission | None:
        """
        Mark submission as submitted to stock site.

        Args:
            submission_id: Primary key of the submission.
            stock_photo_id: ID assigned by the stock site.

        Returns:
            Updated StockSubmission instance or None if not found.
        """
        update_data = {
            "status": SubmissionStatus.SUBMITTED,
            "submitted_at": datetime.utcnow(),
        }
        if stock_photo_id:
            update_data["stock_photo_id"] = stock_photo_id

        return self.update(submission_id, **update_data)

    def mark_approved(self, submission_id: int) -> StockSubmission | None:
        """
        Mark submission as approved by stock site.

        Args:
            submission_id: Primary key of the submission.

        Returns:
            Updated StockSubmission instance or None if not found.
        """
        return self.update(
            submission_id,
            status=SubmissionStatus.APPROVED,
            reviewed_at=datetime.utcnow(),
        )

    def mark_rejected(
        self, submission_id: int, reason: str | None = None
    ) -> StockSubmission | None:
        """
        Mark submission as rejected by stock site.

        Args:
            submission_id: Primary key of the submission.
            reason: Rejection reason provided by stock site.

        Returns:
            Updated StockSubmission instance or None if not found.
        """
        return self.update(
            submission_id,
            status=SubmissionStatus.REJECTED,
            reviewed_at=datetime.utcnow(),
            rejection_reason=reason,
        )

    # ────────────────────────────────────────────────────────────────────────────
    # Delete Operations
    # ────────────────────────────────────────────────────────────────────────────

    def delete(self, submission_id: int) -> bool:
        """
        Delete a submission record.

        Args:
            submission_id: Primary key of the submission.

        Returns:
            True if deleted, False if not found.
        """
        if self._session:
            submission = self._session.get(StockSubmission, submission_id)
            if submission:
                self._session.delete(submission)
                return True
            return False

        with session_scope() as session:
            submission = session.get(StockSubmission, submission_id)
            if submission:
                session.delete(submission)
                return True
            return False


# ────────────────────────────────────────────────────────────────────────────────
# Convenience functions
# ────────────────────────────────────────────────────────────────────────────────

def get_submission_by_image_and_site(
    image_id: int, stock_site: str
) -> StockSubmission | None:
    """Get submission for a specific image and stock site."""
    return StockSubmissionRepository().get_by_image_and_site(image_id, stock_site)


def get_pending_submissions(stock_site: str | None = None) -> list[StockSubmission]:
    """Get all pending submissions."""
    return StockSubmissionRepository().get_pending(stock_site)


def count_submissions_by_status(
    status: SubmissionStatus, stock_site: str | None = None
) -> int:
    """Count submissions by status."""
    return StockSubmissionRepository().count_by_status(status, stock_site)
