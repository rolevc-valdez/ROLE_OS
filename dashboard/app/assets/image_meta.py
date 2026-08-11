"""Safe image metadata extraction (Sprint C4: Assets OS).

Reads only the header/dimension info Pillow needs (`Image.open` is lazy --
it does not decode pixel data until you ask it to), never the full pixel
buffer, and defends against decompression-bomb-style images. SVG has no
raster dimensions Pillow can read; its `viewBox`/`width`/`height`
attributes are parsed directly and cheaply from the file's opening bytes
instead.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

# Refuses to even open an image whose declared pixel count exceeds this --
# Pillow's own decompression-bomb guard, set explicitly rather than relying
# on the library default (which warns but doesn't always raise).
Image.MAX_IMAGE_PIXELS = 64_000_000  # ~8000x8000

_RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_SVG_MAX_HEADER_BYTES = 4096
_SVG_DIMENSION_RE = re.compile(rb'(width|height)\s*=\s*["\']?([\d.]+)')
_SVG_VIEWBOX_RE = re.compile(rb'viewBox\s*=\s*["\']([\d.\s,-]+)["\']', re.IGNORECASE)


def read_image_dimensions(path: Path, extension: str) -> tuple[int | None, int | None]:
    """Returns `(width, height)`, or `(None, None)` if the format has no
    raster dimensions (fonts, documents, design files this process can't
    safely open) or the file can't be read. Never raises."""
    try:
        if extension in _RASTER_EXT:
            with Image.open(path) as img:
                return img.width, img.height
        if extension == ".svg":
            return _read_svg_dimensions(path)
    except Exception:
        return None, None
    return None, None


def _read_svg_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with open(path, "rb") as fh:
            head = fh.read(_SVG_MAX_HEADER_BYTES)
    except OSError:
        return None, None

    dims: dict[str, float] = {}
    for match in _SVG_DIMENSION_RE.finditer(head):
        key = match.group(1).decode("ascii")
        try:
            dims[key] = float(match.group(2))
        except ValueError:
            continue
    if "width" in dims and "height" in dims:
        return int(dims["width"]), int(dims["height"])

    viewbox = _SVG_VIEWBOX_RE.search(head)
    if viewbox:
        parts = re.split(rb"[\s,]+", viewbox.group(1).strip())
        if len(parts) == 4:
            try:
                return int(float(parts[2])), int(float(parts[3]))
            except ValueError:
                pass
    return None, None
