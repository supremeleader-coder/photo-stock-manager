"""
Filter system for photo gallery.

Provides a modular, extensible filter architecture with:
- Filter registry for easy addition of new filters
- Dynamic option loading from database
- Query builder for applying filters to SQLAlchemy queries
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session, Query

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import Image, ProcessingStatus


@dataclass
class FilterOption:
    """Represents a single option in a filter dropdown."""
    value: str
    label: str
    count: Optional[int] = None


class BaseFilter(ABC):
    """Abstract base class for all filters."""

    # Unique identifier used in URL params
    param_name: str
    # Display label in UI
    label: str
    # Filter type: 'select', 'multi_select', 'range', 'date_range'
    filter_type: str

    @abstractmethod
    def get_options(self, session: Session) -> list[FilterOption]:
        """Fetch available options from database."""
        pass

    @abstractmethod
    def apply(self, query: Query, value: Any) -> Query:
        """Apply filter to query and return modified query."""
        pass

    def parse_value(self, raw_value: str) -> Any:
        """Parse URL parameter value. Override for custom parsing."""
        return raw_value


class CountryFilter(BaseFilter):
    """Filter by location country."""

    param_name = "country"
    label = "Country"
    filter_type = "select"

    def get_options(self, session: Session) -> list[FilterOption]:
        results = session.query(
            Image.location_country,
            func.count(Image.id)
        ).filter(
            Image.processing_status == ProcessingStatus.COMPLETED,
            Image.location_country.isnot(None)
        ).group_by(Image.location_country).order_by(Image.location_country).all()

        return [FilterOption(value=r[0], label=r[0], count=r[1]) for r in results]

    def apply(self, query: Query, value: str) -> Query:
        return query.filter(Image.location_country == value)


class CameraModelFilter(BaseFilter):
    """Filter by camera model."""

    param_name = "camera"
    label = "Camera"
    filter_type = "select"

    def get_options(self, session: Session) -> list[FilterOption]:
        results = session.query(
            Image.exif_camera_make,
            Image.exif_camera_model,
            func.count(Image.id)
        ).filter(
            Image.processing_status == ProcessingStatus.COMPLETED,
            Image.exif_camera_model.isnot(None)
        ).group_by(
            Image.exif_camera_make, Image.exif_camera_model
        ).order_by(Image.exif_camera_make, Image.exif_camera_model).all()

        options = []
        for make, model, count in results:
            # Combine make and model for display
            display = f"{make} {model}".strip() if make else model
            options.append(FilterOption(value=model, label=display, count=count))
        return options

    def apply(self, query: Query, value: str) -> Query:
        return query.filter(Image.exif_camera_model == value)


class FileSizeFilter(BaseFilter):
    """Filter by file size ranges."""

    param_name = "size"
    label = "File Size"
    filter_type = "select"

    # Predefined size ranges (in bytes)
    SIZE_RANGES = {
        "large": (">4 MB", 4 * 1024 * 1024, None),
    }

    def get_options(self, session: Session) -> list[FilterOption]:
        options = []
        for key, (label, min_size, max_size) in self.SIZE_RANGES.items():
            conditions = [
                Image.processing_status == ProcessingStatus.COMPLETED,
                Image.file_size >= min_size
            ]
            if max_size:
                conditions.append(Image.file_size < max_size)

            count = session.query(func.count(Image.id)).filter(
                and_(*conditions)
            ).scalar()

            if count > 0:
                options.append(FilterOption(value=key, label=label, count=count))

        return options

    def apply(self, query: Query, value: str) -> Query:
        if value not in self.SIZE_RANGES:
            return query

        _, min_size, max_size = self.SIZE_RANGES[value]
        query = query.filter(Image.file_size >= min_size)
        if max_size:
            query = query.filter(Image.file_size < max_size)
        return query


class DateRangeFilter(BaseFilter):
    """Filter by year taken."""

    param_name = "year"
    label = "Year"
    filter_type = "select"

    def get_options(self, session: Session) -> list[FilterOption]:
        result = session.query(
            func.min(Image.exif_date_taken),
            func.max(Image.exif_date_taken)
        ).filter(
            Image.processing_status == ProcessingStatus.COMPLETED,
            Image.exif_date_taken.isnot(None)
        ).first()

        if not result or not result[0]:
            return []

        min_date, max_date = result
        options = []

        for year in range(max_date.year, min_date.year - 1, -1):
            count = session.query(func.count(Image.id)).filter(
                Image.processing_status == ProcessingStatus.COMPLETED,
                func.extract('year', Image.exif_date_taken) == year
            ).scalar()

            if count > 0:
                options.append(FilterOption(value=str(year), label=str(year), count=count))

        return options

    def apply(self, query: Query, value: str) -> Query:
        try:
            year = int(value)
            return query.filter(
                func.extract('year', Image.exif_date_taken) == year
            )
        except ValueError:
            return query


class FilterRegistry:
    """
    Central registry for all available filters.

    Provides methods to:
    - Register new filters
    - Get all filter options for template rendering
    - Apply all active filters to a query
    """

    def __init__(self):
        self._filters: dict[str, BaseFilter] = {}

    def register(self, filter_instance: BaseFilter) -> None:
        """Register a filter instance."""
        self._filters[filter_instance.param_name] = filter_instance

    def get_all(self) -> list[BaseFilter]:
        """Get all registered filters in registration order."""
        return list(self._filters.values())

    def get(self, param_name: str) -> Optional[BaseFilter]:
        """Get a specific filter by param name."""
        return self._filters.get(param_name)

    def get_filter_options(self, session: Session) -> dict[str, dict]:
        """
        Get all filter options for template rendering.

        Returns:
            Dict mapping param_name to filter info with options.
        """
        result = {}
        for param_name, filter_obj in self._filters.items():
            options = filter_obj.get_options(session)
            # Only include filters that have options
            if options:
                result[param_name] = {
                    "label": filter_obj.label,
                    "type": filter_obj.filter_type,
                    "options": options,
                }
        return result

    def apply_filters(self, query: Query, params: dict) -> Query:
        """
        Apply all active filters to query based on request params.

        Args:
            query: Base SQLAlchemy query
            params: Dict of URL parameters (e.g., request.args)

        Returns:
            Modified query with filters applied
        """
        for param_name, filter_obj in self._filters.items():
            if param_name in params and params[param_name]:
                raw_value = params[param_name]
                parsed_value = filter_obj.parse_value(raw_value)
                query = filter_obj.apply(query, parsed_value)
        return query


# Create and populate the default registry
gallery_filters = FilterRegistry()
gallery_filters.register(CountryFilter())
gallery_filters.register(CameraModelFilter())
gallery_filters.register(FileSizeFilter())
gallery_filters.register(DateRangeFilter())
