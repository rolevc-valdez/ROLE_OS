"""Thumbnail/preview generation (Sprint C4: Assets OS §2).

Generated thumbnails are cached under `Settings.asset_thumbnail_cache_dir`
(`var/role_os_dashboard/asset_thumbnails/` by default) -- **never** inside
a scanned project folder, and never a copy that could be mistaken for
part of the project. The whole cache directory can be deleted at any time;
it is regenerated on next request. Cache key is the asset id plus the
source file's mtime, so an edited source image is never served a stale
thumbnail.

SVG is served as-is (its own file, with an `image/svg+xml` content type)
rather than rasterized -- browsers treat an SVG loaded via `<img src=...>`
as a non-executing image resource (no embedded `<script>` runs), which is
the standard "safe to embed" mechanism the brief asks for, without needing
a sanitizer dependency.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Import for its module-level side effect: sets `Image.MAX_IMAGE_PIXELS`
# to this codebase's own explicit decompression-bomb limit. Without this
# import, whichever of `image_meta`/`preview` happens to be imported
# first would silently determine which limit (or PIL's own default) is
# actually in effect -- importing it here makes the guard unconditional
# regardless of import order.
from app.assets import image_meta  # noqa: F401
from app.config import Settings, get_settings

THUMBNAIL_MAX_DIMENSION = 480
_RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class PreviewError(ValueError):
    pass


def _thumbnail_cache_path(asset_id: str, mtime: float, settings: Settings) -> Path:
    cache_dir = settings.asset_thumbnail_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{asset_id}-{int(mtime)}.png"


def get_or_create_thumbnail(
    asset_id: str, source_path: Path, *, settings: Settings | None = None
) -> Path:
    """Returns a filesystem path to a cached, resized preview image for a
    raster (`_RASTER_EXT`) source file. Never mutates `source_path`. Raises
    `PreviewError` for anything it can't safely open (corrupt file,
    unsupported/exotic image mode, decompression-bomb-sized declared
    dimensions -- see `app.assets.image_meta`'s `Image.MAX_IMAGE_PIXELS`
    guard, which applies here too since this module also calls `Image.
    open`)."""
    settings = settings or get_settings()
    ext = source_path.suffix.lower()
    if ext not in _RASTER_EXT:
        raise PreviewError(f"no raster thumbnail generator for '{ext}'")

    try:
        mtime = source_path.stat().st_mtime
    except OSError as exc:
        raise PreviewError("source file no longer exists") from exc

    cache_path = _thumbnail_cache_path(asset_id, mtime, settings)
    if cache_path.is_file():
        return cache_path

    try:
        with Image.open(source_path) as img:
            img.load()
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.mode or img.mode == "P" else "RGB")
            img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION))
            tmp_path = cache_path.with_suffix(".tmp")
            img.save(tmp_path, format="PNG")
            tmp_path.replace(cache_path)
    except Image.DecompressionBombError as exc:
        # A legitimately huge (or hostile) image -- honestly refuse to
        # preview it rather than loading it fully into memory (§11/§12).
        # `tmp_path` may have been left behind if the failure happened
        # mid-save; nothing else in this function creates other partial
        # state, so cleaning it up here is enough.
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.unlink(missing_ok=True)
        raise PreviewError(f"image too large to preview safely: {exc}") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PreviewError(f"could not generate a preview: {exc}") from exc

    return cache_path
