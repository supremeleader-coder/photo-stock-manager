"""
Metadata extraction module for images.

Wraps and extends the photo_inspector module to extract:
- Basic image info (dimensions, format, size)
- EXIF data (camera make/model, GPS, date taken)
- Location (reverse geocoded from GPS coordinates)
- File hash for duplicate detection
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
import piexif
import reverse_geocoder as rg
import pycountry

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """Container for extracted image metadata."""
    # File info
    filename: str
    filepath: str
    file_size: int
    file_hash: str
    format: str | None = None

    # Dimensions
    width: int | None = None
    height: int | None = None

    # EXIF - Camera
    exif_camera_make: str | None = None
    exif_camera_model: str | None = None

    # EXIF - GPS
    exif_gps_latitude: float | None = None
    exif_gps_longitude: float | None = None

    # EXIF - Date
    exif_date_taken: datetime | None = None

    # Location (reverse geocoded from GPS)
    location_country: str | None = None
    location_name: str | None = None

    # Extra info (not stored in DB but useful)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "filename": self.filename,
            "filepath": self.filepath,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "exif_camera_make": self.exif_camera_make,
            "exif_camera_model": self.exif_camera_model,
            "exif_gps_latitude": self.exif_gps_latitude,
            "exif_gps_longitude": self.exif_gps_longitude,
            "exif_date_taken": self.exif_date_taken,
            "location_country": self.location_country,
            "location_name": self.location_name,
        }


class MetadataExtractor:
    """
    Extracts comprehensive metadata from image files.

    Combines basic image info with EXIF data extraction.
    """

    def extract(self, filepath: str | Path) -> ImageMetadata:
        """
        Extract all metadata from an image file.

        Args:
            filepath: Path to the image file.

        Returns:
            ImageMetadata object with all extracted data.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file is not a valid image.
        """
        filepath = Path(filepath).resolve()

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        logger.debug(f"Extracting metadata from: {filepath.name}")

        # Get basic file info
        stats = filepath.stat()

        metadata = ImageMetadata(
            filename=filepath.name,
            filepath=str(filepath),
            file_size=stats.st_size,
            file_hash=self._calculate_hash(filepath),
        )

        # Extract image properties and EXIF
        try:
            self._extract_image_info(filepath, metadata)
            self._extract_exif_data(filepath, metadata)

            # Reverse geocode GPS coordinates to get location
            if metadata.exif_gps_latitude and metadata.exif_gps_longitude:
                self._reverse_geocode(metadata)
        except Exception as e:
            logger.warning(f"Error extracting metadata from {filepath.name}: {e}")

        return metadata

    def _calculate_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _extract_image_info(self, filepath: Path, metadata: ImageMetadata) -> None:
        """Extract basic image properties using Pillow."""
        try:
            with Image.open(filepath) as img:
                metadata.width = img.width
                metadata.height = img.height
                metadata.format = img.format
        except Exception as e:
            logger.debug(f"Could not open image {filepath.name}: {e}")

    def _extract_exif_data(self, filepath: Path, metadata: ImageMetadata) -> None:
        """Extract EXIF data from image."""
        try:
            with Image.open(filepath) as img:
                exif_bytes = img.info.get("exif")
                if not exif_bytes:
                    return

                exif_dict = piexif.load(exif_bytes)

                # Extract camera info from 0th IFD
                ifd_0 = exif_dict.get("0th", {})
                metadata.exif_camera_make = self._decode_exif_string(
                    ifd_0.get(piexif.ImageIFD.Make)
                )
                metadata.exif_camera_model = self._decode_exif_string(
                    ifd_0.get(piexif.ImageIFD.Model)
                )

                # Extract date taken from Exif IFD
                exif_ifd = exif_dict.get("Exif", {})
                date_str = self._decode_exif_string(
                    exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
                )
                if date_str:
                    metadata.exif_date_taken = self._parse_exif_date(date_str)

                # Extract GPS data
                gps_ifd = exif_dict.get("GPS", {})
                if gps_ifd:
                    lat, lon = self._extract_gps_coords(gps_ifd)
                    metadata.exif_gps_latitude = lat
                    metadata.exif_gps_longitude = lon

        except Exception as e:
            logger.debug(f"Could not extract EXIF from {filepath.name}: {e}")

    def _decode_exif_string(self, value: bytes | str | None) -> str | None:
        """Decode EXIF string value."""
        if value is None:
            return None
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8").strip().rstrip("\x00")
            except UnicodeDecodeError:
                return value.decode("latin-1").strip().rstrip("\x00")
        return str(value).strip()

    def _parse_exif_date(self, date_str: str) -> datetime | None:
        """Parse EXIF date string to datetime."""
        # EXIF format: "YYYY:MM:DD HH:MM:SS"
        try:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            try:
                # Try alternative format
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.debug(f"Could not parse date: {date_str}")
                return None

    def _extract_gps_coords(
        self,
        gps_ifd: dict
    ) -> tuple[float | None, float | None]:
        """Extract GPS coordinates from EXIF GPS IFD."""
        try:
            lat_dms = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
            lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
            lon_dms = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
            lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E")

            lat = self._dms_to_decimal(lat_dms, lat_ref)
            lon = self._dms_to_decimal(lon_dms, lon_ref)

            return lat, lon
        except Exception:
            return None, None

    def _dms_to_decimal(
        self,
        dms: tuple | None,
        ref: bytes
    ) -> float | None:
        """Convert DMS (degrees, minutes, seconds) to decimal degrees."""
        if not dms:
            return None

        try:
            degrees = dms[0][0] / dms[0][1]
            minutes = dms[1][0] / dms[1][1]
            seconds = dms[2][0] / dms[2][1]

            decimal = degrees + minutes / 60 + seconds / 3600

            if ref in (b"S", b"W"):
                decimal = -decimal

            return round(decimal, 7)
        except (TypeError, ZeroDivisionError, IndexError):
            return None

    def _reverse_geocode(self, metadata: ImageMetadata) -> None:
        """
        Reverse geocode GPS coordinates to get country and location name.

        Uses offline reverse geocoder database for fast lookups.
        """
        try:
            lat = metadata.exif_gps_latitude
            lon = metadata.exif_gps_longitude

            if lat is None or lon is None:
                return

            # Perform reverse geocoding (mode=1 for single result)
            results = rg.search((lat, lon), mode=1)
            if not results:
                return

            result = results[0]

            # Get country name from country code
            country_code = result.get("cc", "")
            if country_code:
                country_obj = pycountry.countries.get(alpha_2=country_code)
                metadata.location_country = country_obj.name if country_obj else country_code

            # Build location name (city, region)
            city = result.get("name", "")
            region = result.get("admin1", "")
            if city and region:
                metadata.location_name = f"{city}, {region}"
            elif city:
                metadata.location_name = city
            elif region:
                metadata.location_name = region

            logger.debug(
                f"Geocoded ({lat}, {lon}) -> {metadata.location_country}, "
                f"{metadata.location_name}"
            )

        except Exception as e:
            logger.debug(f"Reverse geocoding failed: {e}")


def extract_metadata(filepath: str | Path) -> ImageMetadata:
    """
    Convenience function to extract metadata from an image.

    Args:
        filepath: Path to the image file.

    Returns:
        ImageMetadata object with extracted data.
    """
    extractor = MetadataExtractor()
    return extractor.extract(filepath)
