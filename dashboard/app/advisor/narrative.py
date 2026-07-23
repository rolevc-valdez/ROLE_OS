"""Narrative provider interface: how a Recommendation's human-facing text
gets generated.

`DeterministicNarrativeProvider` is the default and current implementation
— it builds every string from an f-string template over the candidate's
own structured fields (title, reason, evidence, etc.), with no external
calls and no randomness, so its output is reproducible and fully
explainable from the data alone.

`AdvisorNarrativeProvider` is the seam for a future LLM-backed provider:
one could be dropped in to rephrase the same underlying, rule-computed
data into more natural language, without touching the rule engine, the
scoring system, or persistence at all. The rules and scoring remain the
source of truth for *what* to recommend and *why*; a narrative provider
only ever affects *how it reads*. This Epic does not call any external
AI API — `DeterministicNarrativeProvider` is the only implementation.
"""

from __future__ import annotations

from typing import Protocol

from app.advisor.models import RecommendationCandidate


class AdvisorNarrativeProvider(Protocol):
    """Interface a future LLM-backed narrative provider would implement."""

    def generate_summary(self, candidate: RecommendationCandidate) -> str:
        """One-line summary of the recommendation."""
        ...

    def generate_reason(self, candidate: RecommendationCandidate) -> str:
        """Fuller explanation of why this recommendation was generated."""
        ...

    def generate_daily_brief(self, greeting_name: str, sections: dict[str, list[str]]) -> str:
        """A short prose framing for the daily brief, given its section headlines."""
        ...


class DeterministicNarrativeProvider:
    """Default, dependency-free implementation — no AI, fully reproducible."""

    def generate_summary(self, candidate: RecommendationCandidate) -> str:
        return candidate.summary

    def generate_reason(self, candidate: RecommendationCandidate) -> str:
        return candidate.reason

    def generate_daily_brief(self, greeting_name: str, sections: dict[str, list[str]]) -> str:
        lines = [f"Good morning, {greeting_name}."]
        top = sections.get("top_recommended_projects") or []
        if top:
            lines.append("")
            lines.append("Recommended focus:")
            for i, headline in enumerate(top, start=1):
                lines.append(f"{i}. {headline}")
        return "\n".join(lines)


def get_default_narrative_provider() -> AdvisorNarrativeProvider:
    return DeterministicNarrativeProvider()
