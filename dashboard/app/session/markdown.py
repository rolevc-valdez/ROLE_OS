"""Pure text generation for the Daily Session domain: the copyable Claude
session-initialization prompt and the Obsidian-compatible Markdown daily
record. Both are plain string templating over data already entered by the
user -- no AI/LLM call, no network access, per `docs/architecture/
06_DEVELOPMENT_RULES.md`'s hard constraint against calling an external
model anywhere in ROLE OS.
"""

from __future__ import annotations

from typing import Any


def build_claude_prompt(
    *, mode: str, project_name: str, objective: str, expected_result: str
) -> str:
    """Builds the copyable Claude session-initialization prompt.

    Follows the fixed structure defined for the ROLE OS Dashboard MVP so
    every generated prompt is byte-for-byte consistent regardless of which
    session produced it.
    """
    return f"""Initialize using SYSTEM.md.

ROLE OS Session

Mode:
{mode}

Project:
{project_name}

Today's Objective:
{objective}

Expected Result:
{expected_result}

Read only the documentation required for this mode and project.

At the beginning of the session:

1. Summarize current project status.
2. Identify the highest-impact next milestone.
3. List blockers.
4. Confirm the specific deliverable for this session.
5. Wait for approval before making destructive or architectural changes."""


def build_daily_markdown(session: dict[str, Any]) -> str:
    """Builds the Obsidian-compatible Markdown daily record for a completed
    (or in-progress) session, following the fixed MVP format.
    """
    return f"""# {session['date']}

## Project
{session['project_name']}

## Mode
{session['mode']}

## Objective
{session['objective']}

## Expected Result
{session['expected_result']}

## Completed
{session.get('completed_work') or '(none recorded)'}

## Decisions
{session.get('decisions') or '(none recorded)'}

## Blockers
{session.get('blockers') or '(none recorded)'}

## Next Step
{session.get('next_step') or '(none recorded)'}

## Status
{'Completed' if session.get('status') == 'completed' else session.get('status', 'Active').capitalize()}
"""


def daily_markdown_filename(session: dict[str, Any]) -> str:
    """Obsidian Daily Notes convention: one note per date, named `YYYY-MM-DD.md`."""
    return f"{session['date']}.md"
