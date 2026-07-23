"""Summary extractor.

Produces a short, human-readable summary of a conversation. Prefers the
first substantial user prompt (what the person actually asked for) and
falls back to the conversation title when no prompt is long enough to be
informative.
"""

from __future__ import annotations

import re


def extract_summary(title: str, user_prompts: list[str], max_len: int = 500) -> str:
    """Build a single-line summary from the conversation's user prompts.

    Args:
        title: Conversation title (used as a fallback).
        user_prompts: Ordered list of the user's messages in the conversation.
        max_len: Maximum length of the returned summary.
    """
    source = next((p for p in user_prompts if len(p) >= 30), title or "Untitled")
    return re.sub(r"\s+", " ", source).strip()[:max_len]
