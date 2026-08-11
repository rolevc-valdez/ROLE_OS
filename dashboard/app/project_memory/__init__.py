"""Project Memory (Sprint C7.1): the source of truth Resume Work resumes.

Real-world validation exposed a product flaw: Resume Work resumed an *AI
Session* -- if the session's own title/snapshot were thin or generic, the
copied prompt was too, and the assistant had to ask "what are we working
on?" The AI Session is a transport (where the conversation lives), never
the source of truth for what the project actually needs next.

Project Memory owns that: it is the same already-computed project state
`ProjectContext` assembles (health, git, next action, latest snapshot,
business context) plus, when asked for, the current Operational
Intelligence recommendation for the project (Sprint C6) -- composed here,
not recomputed. `app.workspace.resume` (Resume Work's orchestration) and
`app.routers.pi.ai_sessions`'s per-session resume endpoint both build
their prompt from this, never from the session alone.
"""

from app.project_memory.prompt import build_resume_prompt
from app.project_memory.service import build_project_memory

__all__ = ["build_project_memory", "build_resume_prompt"]
