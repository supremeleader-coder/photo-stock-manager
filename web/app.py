"""
Simple Flask web app to browse photo library.
"""

import os
from pathlib import Path

from flask import Flask, render_template, send_from_directory, request

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import session_scope
from db.models import Image, ProcessingStatus

app = Flask(__name__)

# Thumbnail directory (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
THUMBNAIL_DIR = PROJECT_ROOT / "thumbnails"


@app.route("/")
def gallery():
    """Display gallery of all images with thumbnails."""
    page = request.args.get("page", 1, type=int)
    per_page = 24

    with session_scope() as session:
        # Get total count
        total = session.query(Image).filter(
            Image.processing_status == ProcessingStatus.COMPLETED
        ).count()

        # Get paginated images
        images = session.query(Image).filter(
            Image.processing_status == ProcessingStatus.COMPLETED
        ).order_by(Image.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Convert to list of dicts for template
        image_list = []
        for img in images:
            image_list.append({
                "id": img.id,
                "filename": img.filename,
                "thumbnail_path": img.thumbnail_path,
                "width": img.width,
                "height": img.height,
                "file_size": img.file_size,
                "location_country": img.location_country,
                "location_name": img.location_name,
                "ai_tags": img.ai_tags or [],
                "exif_camera_model": img.exif_camera_model,
                "exif_date_taken": img.exif_date_taken,
            })

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "gallery.html",
        images=image_list,
        page=page,
        total_pages=total_pages,
        total=total
    )


@app.route("/thumbnails/<path:filepath>")
def serve_thumbnail(filepath):
    """Serve thumbnail images."""
    return send_from_directory(THUMBNAIL_DIR, filepath)


@app.route("/image/<int:image_id>")
def image_detail(image_id):
    """Display single image details."""
    with session_scope() as session:
        img = session.get(Image, image_id)
        if not img:
            return "Image not found", 404

        image_data = {
            "id": img.id,
            "filename": img.filename,
            "filepath": img.filepath,
            "thumbnail_path": img.thumbnail_path,
            "width": img.width,
            "height": img.height,
            "file_size": img.file_size,
            "format": img.format,
            "location_country": img.location_country,
            "location_name": img.location_name,
            "ai_tags": img.ai_tags or [],
            "exif_camera_make": img.exif_camera_make,
            "exif_camera_model": img.exif_camera_model,
            "exif_date_taken": img.exif_date_taken,
            "exif_gps_latitude": float(img.exif_gps_latitude) if img.exif_gps_latitude else None,
            "exif_gps_longitude": float(img.exif_gps_longitude) if img.exif_gps_longitude else None,
            "created_at": img.created_at,
        }

    return render_template("detail.html", image=image_data)


def format_size(size_bytes):
    """Format file size for display."""
    if not size_bytes:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_thumbnail_url(thumbnail_path):
    """Convert database thumbnail path to URL path."""
    if not thumbnail_path:
        return None
    # Normalize path separators and extract relative path
    path_str = str(thumbnail_path).replace("\\", "/")
    # Remove 'thumbnails/' prefix if present
    if "thumbnails/" in path_str:
        path_str = path_str.split("thumbnails/", 1)[-1]
    return f"/thumbnails/{path_str}"


# Register template filters
app.jinja_env.filters["format_size"] = format_size
app.jinja_env.filters["thumbnail_url"] = get_thumbnail_url


if __name__ == "__main__":
    print("Starting Photo Library Browser...")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True, host="127.0.0.1", port=5000)
