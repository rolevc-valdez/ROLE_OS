"""Tests for the unified Recent Activity feed (Sprint 4 §7): merges git
commits, filesystem mtimes, adoption events, AI sessions/snapshots, and
discovered assets, sorted by time, deduplicated.
"""

from __future__ import annotations

from app.workspace.activity import build_activity_feed


def _item(**overrides):
    base = {
        "id": "p1",
        "name": "my-app",
        "last_modified": "2026-01-01T00:00:00+00:00",
        "adopted_at": None,
        "ai_sessions": {"sessions": [], "latest_snapshot": None},
        "discovery_detail": {"git": {"is_repo": True, "recent_commits": []}},
    }
    base.update(overrides)
    return base


def test_includes_git_commits():
    item = _item(
        discovery_detail={
            "git": {
                "is_repo": True,
                "recent_commits": [
                    {"hash": "abc", "date": "2026-02-01T00:00:00+00:00", "message": "fix bug"},
                ],
            }
        }
    )
    feed = build_activity_feed([item])
    commit_events = [e for e in feed if e["type"] == "git_commit"]
    assert len(commit_events) == 1
    assert commit_events[0]["summary"] == "fix bug"
    assert commit_events[0]["project_name"] == "my-app"


def test_includes_filesystem_modification():
    feed = build_activity_feed([_item()])
    assert any(e["type"] == "filesystem_modified" for e in feed)


def test_includes_adoption_event_only_when_adopted():
    not_adopted = build_activity_feed([_item(adopted_at=None)])
    assert not any(e["type"] == "adopted" for e in not_adopted)

    adopted = build_activity_feed([_item(adopted_at="2026-01-05T00:00:00+00:00")])
    assert any(e["type"] == "adopted" for e in adopted)


def test_includes_ai_sessions_and_snapshots():
    item = _item(
        ai_sessions={
            "sessions": [
                {
                    "assistant": "claude",
                    "title": "session 1",
                    "last_used_at": "2026-03-01T00:00:00+00:00",
                }
            ],
            "latest_snapshot": {
                "summary": "made progress",
                "created_at": "2026-03-02T00:00:00+00:00",
            },
        }
    )
    feed = build_activity_feed([item])
    assert any(e["type"] == "ai_session" for e in feed)
    assert any(e["type"] == "ai_snapshot" and e["summary"] == "made progress" for e in feed)


def test_includes_discovered_assets():
    asset = {"filename": "logo.png", "modified_at": "2026-04-01T00:00:00+00:00"}
    feed = build_activity_feed([_item()], assets_by_project={"p1": [asset]})
    asset_events = [e for e in feed if e["type"] == "asset_discovered"]
    assert len(asset_events) == 1
    assert "logo.png" in asset_events[0]["summary"]


def test_sorted_by_time_descending():
    item = _item(
        last_modified="2026-01-01T00:00:00+00:00",
        discovery_detail={
            "git": {
                "is_repo": True,
                "recent_commits": [
                    {"hash": "a", "date": "2026-05-01T00:00:00+00:00", "message": "newest"},
                    {"hash": "b", "date": "2026-02-01T00:00:00+00:00", "message": "oldest"},
                ],
            }
        },
    )
    feed = build_activity_feed([item])
    timestamps = [e["timestamp"] for e in feed]
    assert timestamps == sorted(timestamps, reverse=True)


def test_no_duplicate_events():
    item = _item(
        discovery_detail={
            "git": {
                "is_repo": True,
                "recent_commits": [
                    {"hash": "a", "date": "2026-05-01T00:00:00+00:00", "message": "same"},
                ],
            }
        }
    )
    feed = build_activity_feed([item, item])  # same item twice
    commit_events = [e for e in feed if e["type"] == "git_commit"]
    assert len(commit_events) == 1


def test_events_without_timestamp_are_skipped_not_crashed():
    item = _item(
        last_modified=None, discovery_detail={"git": {"is_repo": False, "recent_commits": []}}
    )
    feed = build_activity_feed([item])
    assert isinstance(feed, list)


def test_respects_limit():
    items = []
    for i in range(10):
        items.append(
            _item(
                id=f"p{i}",
                name=f"proj{i}",
                last_modified=f"2026-01-{i + 1:02d}T00:00:00+00:00",
            )
        )
    feed = build_activity_feed(items, limit=3)
    assert len(feed) == 3
