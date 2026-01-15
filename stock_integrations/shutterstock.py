"""
Shutterstock contributor integration using session cookie authentication.

This module provides functionality to:
- Upload photos to Shutterstock
- Set metadata (categories, keywords, description)
- Submit photos for review
- Check submission status
- Fetch portfolio and categories

Note: This uses an unofficial API approach with session cookies.
Session cookies must be obtained manually from browser dev tools.
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────────
# Exceptions
# ────────────────────────────────────────────────────────────────────────────────

class ShutterstockError(Exception):
    """Base exception for Shutterstock API errors."""
    pass


class ShutterstockAuthError(ShutterstockError):
    """Authentication failure - session cookie invalid or expired."""
    pass


class ShutterstockUploadError(ShutterstockError):
    """Upload operation failed."""
    pass


class ShutterstockRateLimitError(ShutterstockError):
    """Rate limit exceeded."""
    pass


# ────────────────────────────────────────────────────────────────────────────────
# Shutterstock Category Data
# ────────────────────────────────────────────────────────────────────────────────

SHUTTERSTOCK_CATEGORIES = [
    {"id": 1, "name": "Animals/Wildlife"},
    {"id": 2, "name": "Buildings/Landmarks"},
    {"id": 3, "name": "Backgrounds/Textures"},
    {"id": 4, "name": "Business/Finance"},
    {"id": 5, "name": "Education"},
    {"id": 6, "name": "Food and Drink"},
    {"id": 7, "name": "Healthcare/Medical"},
    {"id": 8, "name": "Holidays"},
    {"id": 9, "name": "Industrial"},
    {"id": 10, "name": "Interiors"},
    {"id": 11, "name": "Miscellaneous"},
    {"id": 12, "name": "Nature"},
    {"id": 13, "name": "Objects"},
    {"id": 14, "name": "Parks/Outdoor"},
    {"id": 15, "name": "People"},
    {"id": 16, "name": "Religion"},
    {"id": 17, "name": "Science"},
    {"id": 18, "name": "Signs/Symbols"},
    {"id": 19, "name": "Sports/Recreation"},
    {"id": 20, "name": "Technology"},
    {"id": 21, "name": "Transportation"},
    {"id": 22, "name": "Vintage"},
    {"id": 23, "name": "Arts"},
    {"id": 24, "name": "Beauty/Fashion"},
    {"id": 25, "name": "Celebrities"},
    {"id": 26, "name": "Editorial"},
]


# ────────────────────────────────────────────────────────────────────────────────
# Client Implementation
# ────────────────────────────────────────────────────────────────────────────────

class ShutterstockClient:
    """
    Client for Shutterstock contributor operations.

    Uses session cookie authentication obtained from browser.

    Usage:
        client = ShutterstockClient()  # Uses SHUTTERSTOCK_SESSION env var
        # or
        client = ShutterstockClient(session_cookie="your_cookie_here")

        if client.is_authenticated():
            result = client.upload_photo("/path/to/photo.jpg")
            client.set_metadata(result["id"], categories=[1, 12])
            client.submit_for_review([result["id"]])
    """

    BASE_URL = "https://submit.shutterstock.com"
    UPLOAD_URL = "https://media-upload.shutterstock.com/v1/media/asset"

    def __init__(
        self,
        session_cookie: str | None = None,
        max_retries: int = 3,
        timeout: int = 60,
    ):
        """
        Initialize Shutterstock client.

        Args:
            session_cookie: Session cookie from browser. If None, reads from
                           SHUTTERSTOCK_SESSION environment variable.
            max_retries: Maximum number of retries for failed requests.
            timeout: Request timeout in seconds.
        """
        self.session_cookie = session_cookie or os.getenv("SHUTTERSTOCK_SESSION")
        self.max_retries = max_retries
        self.timeout = timeout
        self._jwt_token: str | None = None

        if not self.session_cookie:
            logger.warning(
                "No session cookie provided. Set SHUTTERSTOCK_SESSION env var "
                "or pass session_cookie parameter."
            )

        # Setup requests session with connection pooling
        self._session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=retry_strategy,
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _get_headers(self, include_jwt: bool = False) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Cookie": f"session={self.session_cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        if include_jwt and self._jwt_token:
            headers["X-shutterstock-upload-jwt"] = self._jwt_token
        return headers

    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """
        Make an authenticated HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PATCH, etc.)
            url: Full URL or endpoint path
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object

        Raises:
            ShutterstockAuthError: If authentication fails
            ShutterstockRateLimitError: If rate limited
            ShutterstockError: For other errors
        """
        if not url.startswith("http"):
            url = f"{self.BASE_URL}/{url.lstrip('/')}"

        kwargs.setdefault("headers", self._get_headers())
        kwargs.setdefault("timeout", self.timeout)

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.request(method, url, **kwargs)

                if response.status_code == 401:
                    raise ShutterstockAuthError(
                        "Session cookie expired or invalid. Please refresh your cookie."
                    )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise ShutterstockRateLimitError(
                        f"Rate limited. Retry after {retry_after} seconds."
                    )

                response.raise_for_status()
                return response

            except (ShutterstockAuthError, ShutterstockRateLimitError):
                raise

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(
                    f"Request attempt {attempt}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries:
                    sleep_time = 2 ** attempt
                    logger.debug(f"Sleeping {sleep_time}s before retry")
                    time.sleep(sleep_time)

        raise ShutterstockError(
            f"Request failed after {self.max_retries} attempts: {last_error}"
        )

    def is_authenticated(self) -> bool:
        """
        Check if the session cookie is valid.

        Returns:
            True if authenticated, False otherwise.
        """
        if not self.session_cookie:
            return False

        try:
            response = self._make_request("GET", "/upload/portfolio")
            return response.status_code == 200
        except ShutterstockError:
            return False

    def _extract_jwt_token(self, html_content: str) -> str | None:
        """Extract JWT token from portfolio page HTML."""
        # Look for JWT in the page content
        patterns = [
            r'"uploadJwt"\s*:\s*"([^"]+)"',
            r'uploadJwt["\s:]+([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)',
            r'"jwt"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(1)
        return None

    def _ensure_jwt_token(self) -> str:
        """Ensure we have a valid JWT token for uploads."""
        if self._jwt_token:
            return self._jwt_token

        response = self._make_request("GET", "/upload/portfolio")
        token = self._extract_jwt_token(response.text)

        if not token:
            raise ShutterstockError(
                "Could not extract JWT token from portfolio page. "
                "Session may be invalid or page structure changed."
            )

        self._jwt_token = token
        logger.debug("Extracted JWT token for uploads")
        return token

    def fetch_portfolio(
        self,
        page: int = 1,
        per_page: int = 100,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch portfolio images from Shutterstock.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page
            status: Filter by status ('edit', 'submitted', 'approved', 'rejected')

        Returns:
            Dictionary with portfolio data including items and pagination info.
        """
        params = {
            "page": page,
            "per_page": per_page,
        }
        if status:
            params["status"] = status

        response = self._make_request(
            "GET",
            "/api/content_editor/photo",
            params=params,
        )

        return response.json()

    def get_pending_submissions(self) -> list[dict]:
        """
        Get images in 'edit' status awaiting submission.

        Returns:
            List of image dictionaries with pending status.
        """
        result = self.fetch_portfolio(status="edit", per_page=500)
        return result.get("data", [])

    def upload_photo(self, filepath: str | Path) -> dict[str, Any]:
        """
        Upload a photo file to Shutterstock.

        Args:
            filepath: Path to the image file.

        Returns:
            Dictionary with upload result including the media ID.

        Raises:
            ShutterstockUploadError: If upload fails.
            FileNotFoundError: If file doesn't exist.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Ensure we have JWT token
        jwt_token = self._ensure_jwt_token()

        # Determine content type
        suffix = filepath.suffix.lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        content_type = content_types.get(suffix, "image/jpeg")

        # Read file
        with open(filepath, "rb") as f:
            file_data = f.read()

        # Upload
        headers = {
            "X-shutterstock-upload-jwt": jwt_token,
            "Content-Type": content_type,
            "Cookie": f"session={self.session_cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            response = self._session.post(
                self.UPLOAD_URL,
                data=file_data,
                headers=headers,
                timeout=self.timeout * 2,  # Longer timeout for uploads
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"Uploaded {filepath.name} to Shutterstock")
            return result

        except requests.exceptions.RequestException as e:
            raise ShutterstockUploadError(
                f"Failed to upload {filepath.name}: {e}"
            )

    def set_metadata(
        self,
        media_id: str,
        categories: list[int] | None = None,
        description: str | None = None,
        keywords: list[str] | None = None,
        editorial: bool = False,
    ) -> dict[str, Any]:
        """
        Set metadata for an uploaded image.

        Args:
            media_id: Shutterstock media ID from upload result.
            categories: List of category IDs (see get_categories()).
            description: Image description/title.
            keywords: List of keywords/tags.
            editorial: Whether this is editorial content.

        Returns:
            Updated media data.
        """
        data: dict[str, Any] = {"id": media_id}

        if categories:
            data["categories"] = categories
        if description:
            data["description"] = description
        if keywords:
            data["keywords"] = keywords
        if editorial:
            data["editorial"] = editorial

        response = self._make_request(
            "PATCH",
            "/api/content_editor",
            json=data,
            headers={
                **self._get_headers(),
                "Content-Type": "application/json",
            },
        )

        logger.debug(f"Updated metadata for media {media_id}")
        return response.json()

    def submit_for_review(self, media_ids: list[str]) -> dict[str, Any]:
        """
        Submit images for Shutterstock review.

        Args:
            media_ids: List of media IDs to submit.

        Returns:
            Submission result.
        """
        response = self._make_request(
            "POST",
            "/api/content_editor/submit",
            json={"ids": media_ids},
            headers={
                **self._get_headers(),
                "Content-Type": "application/json",
            },
        )

        logger.info(f"Submitted {len(media_ids)} images for review")
        return response.json()

    def check_status(self, media_id: str) -> dict[str, Any]:
        """
        Get status of a submitted image.

        Args:
            media_id: Shutterstock media ID.

        Returns:
            Media data including current status.
        """
        response = self._make_request(
            "GET",
            f"/api/content_editor/photo/{media_id}",
        )
        return response.json()

    def get_categories(self) -> list[dict[str, Any]]:
        """
        Get Shutterstock category list.

        Returns:
            List of category dictionaries with 'id' and 'name'.
        """
        return SHUTTERSTOCK_CATEGORIES.copy()

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
        logger.debug("Shutterstock session closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
