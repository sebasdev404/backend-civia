"""Miniaturas locales de portadas reales, generadas una sola vez por versión."""

import os
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from urllib.parse import urlparse


GENERIC_COVERS = {"default_cover.jpg", "ig_cover_comuna6.jpg", "ig_cover_malecon.jpg", "ig_cover_ceibas.jpg", "ig_cover_salud.jpg"}


def real_image_url(url):
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.path.rsplit("/", 1)[-1].lower() in GENERIC_COVERS or (parsed.hostname or "").endswith("unsplash.com"):
        return None
    return url


def post_image_urls(post_id, cover, asset_base):
    """Use only the exact post's cached image or its recorded real URL."""
    cover = real_image_url(cover)
    if not post_id or not re.fullmatch(r"[A-Za-z0-9_-]+", post_id):
        return cover, None
    source = Path("static/covers") / f"{post_id}.jpg"
    try:
        stat = source.stat()
        if stat.st_size > 500:
            return (f"{asset_base}/static/covers/{post_id}.jpg",
                    f"{asset_base}/api/v1/meta/post-thumbnail/{post_id}?v={stat.st_mtime_ns}")
    except OSError:
        pass
    return cover, None


def get_thumbnail(post_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", post_id) or f"{post_id}.jpg" in GENERIC_COVERS:
        return None
    source = Path("static/covers") / f"{post_id}.jpg"
    if not source.is_file() or source.stat().st_size <= 500:
        return None
    cache = Path("static/thumbnails")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{post_id}.jpg"
    if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return target
    temporary = None
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image = ImageOps.fit(image, (480, 300), method=Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(dir=cache, suffix=".jpg", delete=False) as output:
                temporary = Path(output.name)
            image.save(temporary, format="JPEG", quality=72, optimize=True)
        os.replace(temporary, target)
        return target
    except (OSError, UnidentifiedImageError):
        return None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
