#!/usr/bin/env python3
"""
AI-powered photo tagging using OpenAI Vision API.
Includes caching to avoid re-tagging the same images.
"""

from pathlib import Path
import base64
import mimetypes
import json
import hashlib
from typing import List, Optional
import logging

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Install openai: pip install openai>=1.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client (uses OPENAI_API_KEY env var)
client = OpenAI()

# Cache directory for storing tags
CACHE_DIR = Path.home() / ".photo_tagger_cache"
CACHE_DIR.mkdir(exist_ok=True)


def get_file_hash(path: Path) -> str:
    """Generate SHA256 hash of file for caching."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def load_cached_tags(file_hash: str) -> Optional[List[str]]:
    """Load tags from cache if they exist."""
    cache_file = CACHE_DIR / f"{file_hash}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                return data.get("tags", [])
        except Exception as e:
            logger.debug(f"Failed to load cache: {e}")
    return None


def save_cached_tags(file_hash: str, tags: List[str]) -> None:
    """Save tags to cache."""
    cache_file = CACHE_DIR / f"{file_hash}.json"
    try:
        with open(cache_file, "w") as f:
            json.dump({"tags": tags}, f)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")


def tag_photo(
    photo_path: str | Path,
    *,
    model: str = "gpt-4o-mini",  # Fixed: was "gpt-4.1-mini"
    max_tags: int = 30,
    detail: str = "high",
    use_cache: bool = True,
) -> List[str]:
    """
    Return up to `max_tags` concise, lowercase stock-photo keywords
    for `photo_path` using an OpenAI vision model.
    
    Args:
        photo_path: Path to the image file
        model: OpenAI model to use (gpt-4o-mini, gpt-4o, etc.)
        max_tags: Maximum number of tags to return
        detail: Image detail level ("low", "high", "auto")
        use_cache: Whether to use cached results
    
    Returns:
        List of lowercase keyword strings
    
    Example:
        >>> tags = tag_photo('photo.jpg')
        >>> print(tags)
        ['sunset', 'mediterranean', 'sailboat', 'golden hour', ...]
    """
    photo_path = Path(photo_path)
    
    if not photo_path.exists():
        raise FileNotFoundError(f"Photo not found: {photo_path}")
    
    # Check cache first
    if use_cache:
        file_hash = get_file_hash(photo_path)
        cached_tags = load_cached_tags(file_hash)
        if cached_tags:
            logger.info(f"Using cached tags for {photo_path.name}")
            return cached_tags
    
    logger.info(f"Tagging {photo_path.name} with {model}...")
    
    # Prepare image data
    mime, _ = mimetypes.guess_type(photo_path.name)
    data_url = (
        f"data:{mime or 'image/jpeg'};base64,"
        + base64.b64encode(photo_path.read_bytes()).decode()
    )
    
    # Call OpenAI Vision API
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=150,  # Increased from 60 for more tags
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional stock-photo keywording assistant. "
                        "Provide accurate, searchable keywords that describe the image "
                        "content, composition, mood, colors, and potential commercial uses."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Return a comma-separated list of up to {max_tags} "
                                "concise, lowercase keywords. Include: subject matter, "
                                "actions, setting, time of day, weather, colors, mood, "
                                "composition style, and potential commercial applications. "
                                "Be specific and avoid generic terms."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": detail},
                        },
                    ],
                },
            ],
        )
        
        # Parse response
        raw = response.choices[0].message.content
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        
        # Cache the results
        if use_cache:
            save_cached_tags(file_hash, tags)
        
        logger.info(f"Generated {len(tags)} tags")
        return tags
        
    except Exception as e:
        logger.error(f"Failed to tag {photo_path.name}: {e}")
        raise


def batch_tag_photos(
    photo_paths: List[Path],
    **kwargs
) -> dict[Path, List[str]]:
    """
    Tag multiple photos and return results as a dictionary.
    
    Args:
        photo_paths: List of paths to image files
        **kwargs: Arguments to pass to tag_photo()
    
    Returns:
        Dictionary mapping photo paths to their tag lists
    """
    results = {}
    total = len(photo_paths)
    
    for i, path in enumerate(photo_paths, 1):
        logger.info(f"Processing {i}/{total}: {path.name}")
        try:
            tags = tag_photo(path, **kwargs)
            results[path] = tags
        except Exception as e:
            logger.error(f"Failed to process {path.name}: {e}")
            results[path] = []
    
    return results


def main():
    """Demo CLI for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python photo_tagger.py <image_file>")
        sys.exit(1)
    
    photo_path = Path(sys.argv[1])
    tags = tag_photo(photo_path)
    
    print(f"\nTags for {photo_path.name}:")
    print(", ".join(tags))
    print(f"\nTotal: {len(tags)} tags")


if __name__ == "__main__":
    main()
