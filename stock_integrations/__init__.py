"""
Stock integrations module for Photo Stock Manager.

Provides clients for uploading and managing photos on stock photography sites.
"""

from stock_integrations.shutterstock import (
    ShutterstockClient,
    ShutterstockError,
    ShutterstockAuthError,
    ShutterstockUploadError,
    ShutterstockRateLimitError,
)

__all__ = [
    "ShutterstockClient",
    "ShutterstockError",
    "ShutterstockAuthError",
    "ShutterstockUploadError",
    "ShutterstockRateLimitError",
]
