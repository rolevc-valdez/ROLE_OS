"""Prompts extractor.

Pulls the user's own messages out of a conversation, in order, as the raw
prompt history — useful for re-running or auditing what was actually asked.
"""

from __future__ import annotations


def extract_prompts(messages: list[tuple[str, str]], limit: int = 25) -> list[str]:
    """Return up to `limit` non-empty user messages, in conversation order."""
    prompts = [text.strip() for role, text in messages if role == "user" and text.strip()]
    return prompts[:limit]
