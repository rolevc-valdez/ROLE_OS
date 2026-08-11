"""Integration tests for the Resume Work Execution Target hotfix: a real
Discovery Engine scan + adopt + resume-work round trip, verifying
`execution_target` lands on `claude_code` for a local software repository
doing implementation work, `claude_web` for a documentation-only project,
and that `launch-claude-code` actually spawns a (mocked) process with the
project's own canonical root as `cwd` -- never a client-supplied path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.main import app
from app.workspace import launcher
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _adopt_software_project(tmp_path: Path, suffix: str, name: str) -> dict:
    """A software repository with real Windows-style spaces/parentheses in
    its own scan root -- the hotfix's own named acceptance case (§9/§10:
    ROLE Commerce Factory, ROLE_OS)."""
    root = tmp_path / f"1 - IA PROJECTS ({suffix})"
    _write(root / name / "README.md", "# App\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    _write(root / name / "src" / "main.py", "print('hi')\n")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def _adopt_documentation_project(tmp_path: Path, suffix: str, name: str) -> dict:
    root = tmp_path / f"scan-root-docs-{suffix}"
    _write(root / name / "README.md", "# Docs\n")
    _write(root / name / "ROADMAP.md", "# Roadmap\n- [ ] plan Q3\n")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def test_software_repository_implementation_task_resumes_in_claude_code(tmp_path):
    """The hotfix's own headline case: ROLE Commerce Factory-shaped
    project + an implementation-style objective must come back
    `execution_target == "claude_code"`, with a real, existing
    `working_directory`, and never claim "I can't access your local
    filesystem" in the prompt."""
    item = _adopt_software_project(tmp_path, "ROLE Commerce Factory", "role-commerce-factory")
    resp = client.post(
        f"/workspace/discovered/{item['id']}/resume-work",
        json={"user_objective": {"requested_action": "Implement the missing payment adapter"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_target"] == "claude_code"
    assert body["working_directory"] and Path(body["working_directory"]).is_dir()
    assert "can't access your local filesystem" not in body["prompt"].lower()
    assert "running inside the project's local repository" in body["prompt"].lower()


def test_role_os_style_project_also_resumes_in_claude_code(tmp_path):
    """§10: the rule is derived from evidence, never a hardcoded project
    name -- a second, differently-named repository gets the same
    treatment."""
    item = _adopt_software_project(tmp_path, "ROLE_OS", "role-os")
    resp = client.post(
        f"/workspace/discovered/{item['id']}/resume-work",
        json={"user_objective": {"requested_action": "Fix the failing discovery test"}},
    )
    assert resp.status_code == 200
    assert resp.json()["execution_target"] == "claude_code"


def test_documentation_project_stays_on_web_assistant(tmp_path):
    """§11: a business/documentation project whose action is satisfied by
    the embedded context must not be forced into Claude Code."""
    item = _adopt_documentation_project(tmp_path, "1", "role-ecosystem")
    resp = client.post(
        f"/workspace/discovered/{item['id']}/resume-work",
        json={"user_objective": {"requested_action": "Review and update the roadmap narrative"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_target"] == "claude_web"
    assert body["working_directory"] is None


def test_launch_claude_code_endpoint_uses_the_projects_own_canonical_root(
    tmp_path, monkeypatch
):
    """§7/§10: the launcher must use the *server-resolved* root, not
    anything the client could supply -- the request body only carries the
    prompt (see `LaunchClaudeCodeRequest`)."""
    monkeypatch.setattr(launcher.platform, "system", lambda: "Windows")
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: "C:/npm/claude.CMD")
    monkeypatch.setattr(launcher, "_copy_to_clipboard", lambda text: True)
    captured = {}

    def fake_popen(args, cwd=None, creationflags=None):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["creationflags"] = creationflags

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    item = _adopt_software_project(tmp_path, "Launch Target", "launch-target")

    resp = client.post(
        f"/workspace/discovered/{item['id']}/launch-claude-code",
        json={"prompt": "Resume prompt text"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["launched"] is True
    assert body["executable"] == "C:/npm/claude.CMD"
    assert captured["cwd"] == body["working_directory"]
    assert captured["args"] == ["C:/npm/claude.CMD"]
    assert captured["creationflags"] == launcher._CREATE_NEW_CONSOLE
    assert item["root_path"] in captured["cwd"] or Path(captured["cwd"]).name == "launch-target"


def test_launch_claude_code_404s_for_unadopted_item(tmp_path):
    root = tmp_path / "scan-root-preadopt-launch"
    _write(root / "app-a" / "README.md", "x")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = items[0]

    resp = client.post(
        f"/workspace/discovered/{item['id']}/launch-claude-code",
        json={"prompt": "text"},
    )
    assert resp.status_code == 404
