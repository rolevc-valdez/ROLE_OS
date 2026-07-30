"""Unit tests for the recent-ecosystem-decisions adapter
(app.session.decisions_adapter): live read when configured, documented
fallback otherwise.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.session.decisions_adapter import FALLBACK_DECISIONS, read_recent_decisions

SAMPLE_LOG = """# Decision Log

## Log

| ID | Date | Decision | Status | Context | Rationale |
|---|---|---|---|---|---|
| D-002 | 2026-07-30 | Second decision. | Accepted | Some context. | Some rationale. |
| D-001 | 2026-07-29 | First decision. | Accepted | Some context. | Some rationale. |

## Best Practices

- Not part of the Log table and must not be parsed as a row.
"""


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.delenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", raising=False)
    return Settings()


def test_falls_back_when_not_configured(settings):
    result = read_recent_decisions(limit=5, settings=settings)
    assert result["source"] == "fallback"
    assert result["decisions"] == list(FALLBACK_DECISIONS[:5])
    assert "not set" in result["note"]


def test_falls_back_when_configured_path_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(tmp_path / "does_not_exist.md"))
    result = read_recent_decisions(limit=5, settings=Settings())
    assert result["source"] == "fallback"
    assert "does not exist" in result["note"]


def test_reads_live_when_configured_and_present(tmp_path, monkeypatch):
    log_path = tmp_path / "DECISION_LOG.md"
    log_path.write_text(SAMPLE_LOG, encoding="utf-8")
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(log_path))

    result = read_recent_decisions(limit=5, settings=Settings())
    assert result["source"] == "ecosystem"
    assert [d["id"] for d in result["decisions"]] == ["D-002", "D-001"]
    assert result["decisions"][0]["decision"] == "Second decision."
    assert result["decisions"][0]["status"] == "Accepted"


def test_respects_limit(tmp_path, monkeypatch):
    log_path = tmp_path / "DECISION_LOG.md"
    log_path.write_text(SAMPLE_LOG, encoding="utf-8")
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(log_path))

    result = read_recent_decisions(limit=1, settings=Settings())
    assert len(result["decisions"]) == 1
    assert result["decisions"][0]["id"] == "D-002"


def test_does_not_duplicate_full_log_context_or_rationale(tmp_path, monkeypatch):
    log_path = tmp_path / "DECISION_LOG.md"
    log_path.write_text(SAMPLE_LOG, encoding="utf-8")
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(log_path))

    result = read_recent_decisions(limit=5, settings=Settings())
    for decision in result["decisions"]:
        assert set(decision.keys()) == {"id", "date", "decision", "status"}


def test_falls_back_on_log_with_no_parseable_rows(tmp_path, monkeypatch):
    log_path = tmp_path / "DECISION_LOG.md"
    log_path.write_text("# Decision Log\n\n## Log\n\nNo table here.\n", encoding="utf-8")
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(log_path))

    result = read_recent_decisions(limit=5, settings=Settings())
    assert result["source"] == "fallback"
