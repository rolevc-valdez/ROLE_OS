"""Deterministic, explainable asset classification (Sprint C4: Assets OS).

Every rule below is a plain regex/extension/dimension check over evidence
that already exists (filename, folder name, extension, image dimensions)
-- same style as `app.discovery.classifier`/`app.workspace.advisor`'s
rule-based reasoning. No LLM, no ML model, no external service.

`classify_category` tries rules in a fixed priority order and returns the
first match; every category has a documented reason a human can verify by
reading the filename/folder themselves.
"""

from __future__ import annotations

import re

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}
AUDIO_EXT = {".mp3", ".wav"}
DOCUMENT_EXT = {".pdf", ".docx", ".pptx"}
DESIGN_EXT = {".psd", ".ai", ".eps"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
ASSET_EXT = IMAGE_EXT | VIDEO_EXT | AUDIO_EXT | DOCUMENT_EXT | DESIGN_EXT | FONT_EXT

CATEGORIES = (
    "Logo",
    "Brand",
    "Character",
    "Photo",
    "Illustration",
    "Screenshot",
    "Icon",
    "Social Media",
    "Thumbnail",
    "Template",
    "Video",
    "Audio",
    "Document",
    "Font",
    "Prompt Resource",
    "Other",
)

# (regex over "filename + folder path, lowercased", category). Order is
# priority -- first match wins. Filename-and-folder evidence outranks
# extension/dimension evidence, since a name like "logo_final.png" is a
# stronger, more specific signal than "it's a PNG".
_NAME_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\blogo\b"), "Logo"),
    (re.compile(r"\bfavicon\b"), "Icon"),
    (re.compile(r"\b(brand|branding|brandkit|brand[-_ ]?kit)\b"), "Brand"),
    (re.compile(r"\b(character|char[-_ ]?sheet|mascot)\b"), "Character"),
    (re.compile(r"\b(screenshot|screen[-_ ]?shot|scrnshot)\b"), "Screenshot"),
    (re.compile(r"\b(icon|iconset|icon[-_ ]?set)\b"), "Icon"),
    (
        re.compile(
            r"\b(instagram|facebook|twitter|linkedin|tiktok|social[-_ ]?media|social[-_ ]?post)\b"
        ),
        "Social Media",
    ),
    (re.compile(r"\b(thumb|thumbnail)\b"), "Thumbnail"),
    (re.compile(r"\b(template|boilerplate)\b"), "Template"),
    (re.compile(r"\b(prompt|gpt|claude[-_ ]?prompt)\b"), "Prompt Resource"),
    (re.compile(r"\b(photo|photography|img_\d+|dsc_?\d+)\b"), "Photo"),
    (re.compile(r"\b(illustration|artwork|drawing)\b"), "Illustration"),
    (re.compile(r"\b(intro|outro|bumper)\b"), "Video"),
)

# Common raw screen-capture resolutions -- a strong signal even when the
# filename gives no hint (e.g. a screenshot saved with its OS-default name).
_SCREENSHOT_DIMENSIONS = {
    (1920, 1080),
    (1080, 1920),
    (1366, 768),
    (2560, 1440),
    (1440, 2560),
    (3840, 2160),
    (1280, 720),
    (720, 1280),
    (1512, 982),
    (2880, 1800),
}
_ICON_MAX_DIMENSION = 192

_REUSABLE_CATEGORIES = {"Logo", "Brand", "Character", "Template", "Font", "Icon"}
_NEVER_REUSABLE_CATEGORIES = {"Screenshot", "Thumbnail", "Photo"}
_LOGO_RE = re.compile(r"\blogo\b")


def _extension_category(ext: str) -> str | None:
    if ext in VIDEO_EXT:
        return "Video"
    if ext in AUDIO_EXT:
        return "Audio"
    if ext in DOCUMENT_EXT:
        return "Document"
    if ext in FONT_EXT:
        return "Font"
    if ext in DESIGN_EXT:
        return "Illustration"
    return None


def classify_category(
    *,
    filename: str,
    folder_path: str,
    extension: str,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Deterministic category classification. Evidence order: filename/
    folder name regex, then image dimensions (icon-sized / common
    screenshot resolution), then plain file extension, else "Other"."""
    # `\b` word-boundary regexes only fire at a transition between a
    # "word" character and a non-word one -- but `_`/`-` both count as
    # word characters in Python's `re`, so "shot_4_logo.png" would never
    # match `\blogo\b` without this normalization (no boundary exists
    # between "_" and "l"). Real filenames use `_`/`-` as word separators
    # far more often than literal underscores/hyphens are part of a word,
    # so this reads as "the same words, just delimited differently."
    haystack = re.sub(r"[_\-]+", " ", f"{filename} {folder_path}".lower())
    for pattern, category in _NAME_RULES:
        if pattern.search(haystack):
            return category

    if extension in IMAGE_EXT and width and height:
        if width <= _ICON_MAX_DIMENSION and height <= _ICON_MAX_DIMENSION:
            return "Icon"
        if (width, height) in _SCREENSHOT_DIMENSIONS:
            return "Screenshot"

    ext_category = _extension_category(extension)
    if ext_category:
        return ext_category

    if extension in IMAGE_EXT:
        return "Photo"

    return "Other"


def is_reusable(*, category: str, filename: str) -> bool:
    """Explainable reusability rule: logos/icons/brand/character-sheets/
    templates/fonts are reusable by default; ordinary screenshots, photos,
    and thumbnails are not (per the brief's explicit "do not mark ordinary
    screenshots and temporary exports reusable by default"). A video/audio
    file is reusable only when its name says it's a reusable intro/outro/
    bumper -- everything else in those categories defaults to not
    reusable."""
    if category in _REUSABLE_CATEGORIES:
        return True
    if category in _NEVER_REUSABLE_CATEGORIES:
        return False
    if category in ("Video", "Audio"):
        normalized = re.sub(r"[_\-]+", " ", filename.lower())
        return bool(re.search(r"\b(intro|outro|bumper)\b", normalized))
    return False


def detect_likely_logo(*, category: str, filename: str) -> bool:
    normalized = re.sub(r"[_\-]+", " ", filename.lower())
    return category == "Logo" or bool(_LOGO_RE.search(normalized))
