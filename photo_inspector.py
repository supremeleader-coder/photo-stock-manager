#!/usr/bin/env python3
"""
Photo metadata inspector with GPS and location data.
Usage: python photo_inspector.py "/path/to/photos"
"""

from pathlib import Path
from datetime import datetime
import sys
from typing import Tuple, Optional, Dict, Any
import logging

try:
    import reverse_geocoder as rg
    import pycountry
    from PIL import Image
    import piexif
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install Pillow piexif reverse-geocoder pycountry")

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PHOTO_EXT = {
    ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".tiff", ".webp", ".heic", ".heif"
}

# ────────────────────────────── Helper Functions ──────────────────────────── #

def fmt_size(bytes_: int) -> str:
    """Format bytes as KB."""
    return f"{bytes_ / 1024:8.1f} KB"


def dms_to_deg(dms, ref: bytes) -> Optional[float]:
    """Convert GPS DMS coordinates to decimal degrees."""
    try:
        deg, minutes, seconds = (v[0] / v[1] for v in dms)
        sign = -1 if ref in (b"S", b"W") else 1
        return sign * (deg + minutes / 60 + seconds / 3600)
    except (TypeError, ValueError, ZeroDivisionError, IndexError):
        return None


def reverse_location(lat: float, lon: float) -> Tuple[str, str]:
    """
    Return (country_name, location_name) from coordinates.
    Uses offline reverse geocoding database.
    """
    try:
        rec = rg.search((lat, lon), mode=1)[0]
        country_code = rec.get("cc", "")
        country_obj = pycountry.countries.get(alpha_2=country_code)
        country = country_obj.name if country_obj else "Unknown"
        loc_name = f'{rec.get("name", "?")}, {rec.get("admin1", "?")}'
        return country, loc_name
    except Exception as e:
        logger.debug(f"Geocoding failed for {lat}, {lon}: {e}")
        return "Unknown", "Unknown"


def extract_gps_data(path: Path) -> Dict[str, Any]:
    """
    Extract GPS data from image EXIF.
    Returns dict with: has_gps, latitude, longitude, country, location
    """
    result = {
        "has_gps": False,
        "latitude": None,
        "longitude": None,
        "country": "Unknown",
        "location": "Unknown"
    }
    
    try:
        with Image.open(path) as im:
            exif_bytes = im.info.get("exif")
            if not exif_bytes:
                return result
            
            exif_dict = piexif.load(exif_bytes)
            gps_ifd = exif_dict.get("GPS", {})
            
            if not gps_ifd:
                return result
            
            result["has_gps"] = True
            
            lat = dms_to_deg(
                gps_ifd.get(piexif.GPSIFD.GPSLatitude),
                gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
            )
            lon = dms_to_deg(
                gps_ifd.get(piexif.GPSIFD.GPSLongitude),
                gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E")
            )
            
            if lat is not None and lon is not None:
                result["latitude"] = lat
                result["longitude"] = lon
                country, loc_name = reverse_location(lat, lon)
                result["country"] = country
                result["location"] = loc_name
                
    except Exception as e:
        logger.debug(f"Failed to extract GPS from {path.name}: {e}")
    
    return result


def inspect_image(path: Path) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from image.
    Returns dict with dimensions, format, GPS data, etc.
    """
    result = {
        "width": None,
        "height": None,
        "format": "Unknown",
        "size_bytes": 0,
        "modified": None,
        **extract_gps_data(path)  # Merge GPS data
    }
    
    try:
        stats = path.stat()
        result["size_bytes"] = stats.st_size
        result["modified"] = datetime.fromtimestamp(stats.st_mtime)
        
        with Image.open(path) as im:
            result["width"] = im.width
            result["height"] = im.height
            result["format"] = im.format or "Unknown"
            
    except Exception as e:
        logger.warning(f"Failed to inspect {path.name}: {e}")
    
    return result


def fmt_time(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "Unknown"


# ──────────────────────────────── Main CLI ────────────────────────────────── #

def process_folder(folder: Path, recursive: bool = False) -> None:
    """Process and display photo metadata from folder."""
    
    if not folder.is_dir():
        sys.exit(f"Error: {folder} is not a directory.")
    
    # Collect all photo files
    if recursive:
        photos = [f for f in folder.rglob("*") if f.suffix.lower() in PHOTO_EXT and f.is_file()]
    else:
        photos = [f for f in folder.iterdir() if f.suffix.lower() in PHOTO_EXT and f.is_file()]
    
    if not photos:
        print(f"No photos found in {folder}")
        return
    
    print(f"Found {len(photos)} photo(s)\n")
    
    # Print header
    header = (
        f"{'File name':40} {'Size':>10} {'Dimensions':>12} "
        f"{'Format':>8} {'GPS':>5} {'Country':>15} {'Location':>25} {'Modified':>17}"
    )
    print(header)
    print("─" * len(header))
    
    # Process each photo
    for photo in sorted(photos):
        meta = inspect_image(photo)
        
        dim_str = f"{meta['width'] or '?'}×{meta['height'] or '?'}"
        
        print(
            f"{photo.name:40.40s} "
            f"{fmt_size(meta['size_bytes']):>10} "
            f"{dim_str:>12} "
            f"{meta['format']:>8.8s} "
            f"{str(meta['has_gps']):>5} "
            f"{meta['country']:>15.15s} "
            f"{meta['location']:>25.25s} "
            f"{fmt_time(meta['modified']):>17}"
        )


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        sys.exit("Usage: python photo_inspector.py <folder> [--recursive]")
    
    folder_path = Path(sys.argv[1])
    recursive = "--recursive" in sys.argv or "-r" in sys.argv
    
    process_folder(folder_path, recursive)


if __name__ == "__main__":
    main()