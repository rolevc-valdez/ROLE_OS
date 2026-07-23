#!/usr/bin/env python3
"""Seed the ROLE OS Alpha demo with realistic Project Intelligence data.

This script does not modify any backend code or schema. It only calls the
existing `app.projects.db`, `app.projects.health`, and `app.advisor.engine`
functions (the same ones the `/pi/*` and `/advisor/*` API routes call) to
populate the Project Intelligence and Advisor databases with seven sample
projects, realistic collections, capabilities, dependencies, related-project
links, recomputed Health Scores, and a first batch of Advisor
recommendations -- all derived from real seeded data, never hand-set.

The Builder-generated knowledge database (`samples/role_os_sample`) is left
completely untouched, per the Alpha requirement to seed "using the current
knowledge database" rather than generating new one.

Idempotent: if a project named "ROLE OS" already exists, the script assumes
the demo has already been seeded and exits without making changes, so it is
safe to run every time the app launches.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
sys.path.insert(0, str(DASHBOARD_ROOT))
sys.path.insert(0, str(REPO_ROOT / "builder"))

from app.config import get_settings  # noqa: E402
from app.projects import db as pdb  # noqa: E402
from app.projects.health import compute_health_score  # noqa: E402
from app.advisor import engine as advisor_engine  # noqa: E402
from app import db as knowledge_db  # noqa: E402


def iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def force_updated_at(settings, project_id: str, iso_value: str) -> None:
    """Backdate a project's `updated_at` directly in SQLite.

    Needed for demo realism: `add_collection_item`/`update_project` always
    stamp `updated_at` to "now", so a project that should *look* stale for
    the Advisor demo (e.g. a neglected day-job project) needs its
    `updated_at` rolled back after its collections are seeded.
    """
    conn = sqlite3.connect(str(settings.projects_db_path))
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (iso_value, project_id))
    conn.commit()
    conn.close()


def add_items(settings, project_id: str, field: str, items: list[dict]) -> None:
    for item in items:
        pdb.add_collection_item(project_id, field, item, settings=settings)


def main() -> None:
    settings = get_settings()

    if pdb.get_workspace_by_name("Products", settings=settings):
        existing = [p for p in pdb.list_projects(workspace="Products", settings=settings) if p["name"] == "ROLE OS"]
        if existing:
            print("Alpha demo data already seeded (found project 'ROLE OS') -- skipping.")
            return

    print("Seeding ROLE OS Alpha demo data...")

    # -----------------------------------------------------------------
    # Projects
    # -----------------------------------------------------------------

    role_os = pdb.create_project(
        name="ROLE OS",
        workspace="Products",
        description=(
            "The ROLE OS Knowledge Operating System itself: the Builder, "
            "Dashboard, Project Intelligence, AI Advisor, and Knowledge "
            "Graph that this whole demo runs on."
        ),
        priority="high",
        tags=["meta", "platform", "knowledge-os"],
        owner="Rogelio",
        settings=settings,
    )
    role_master = pdb.create_project(
        name="ROLE MASTER",
        workspace="Products",
        description=(
            "Master brand and character system: identity, avatar, visual "
            "style, and the master prompt library every other ROLE project "
            "builds on."
        ),
        priority="high",
        tags=["brand", "identity", "character"],
        owner="Rogelio",
        settings=settings,
    )
    super_facil = pdb.create_project(
        name="SUPER FACIL",
        workspace="Products",
        description=(
            "Consumer-facing simplified assistant product, built on ROLE "
            "OS's knowledge engine and ROLE MASTER's brand identity."
        ),
        priority="medium",
        tags=["consumer-app", "mobile"],
        owner="Rogelio",
        settings=settings,
    )
    role_valdez = pdb.create_project(
        name="RoleValdez",
        workspace="Personal",
        description="Personal brand and public presence: website, social voice, and content strategy.",
        priority="medium",
        tags=["personal-brand", "content"],
        owner="Rogelio",
        settings=settings,
    )
    kontoor = pdb.create_project(
        name="Kontoor",
        workspace="Kontoor",
        description=(
            "IT service management and systems work at Kontoor Brands: "
            "Freshservice, Device42, CMDB/SAM, and Jet Reports."
        ),
        priority="high",
        tags=["it-ops", "day-job"],
        owner="Rogelio",
        settings=settings,
    )
    unger = pdb.create_project(
        name="Unger",
        workspace="Unger",
        description=(
            "IT operations and reporting support at Unger: Business "
            "Central, Power BI/Excel reporting, and vendor coordination."
        ),
        priority="medium",
        tags=["it-ops", "reporting"],
        owner="Rogelio",
        settings=settings,
    )
    charcos = pdb.create_project(
        name="Charcos",
        workspace="Ideas",
        description="Charcos MC -- music and performance alter ego, a creative side project.",
        priority="low",
        tags=["music", "creative", "side-project"],
        owner="Rogelio",
        settings=settings,
    )

    # -----------------------------------------------------------------
    # Collections (notes, decisions, todos, deliverables, assets, prompts)
    # -----------------------------------------------------------------

    add_items(settings, role_os["id"], "decisions", [
        {"text": "Adopt FastAPI + SQLite with no external services, for full local control.", "status": "resolved", "created_at": iso_days_ago(60)},
    ])
    add_items(settings, role_os["id"], "deliverables", [
        {"text": "Knowledge Graph engine (Epic 3)", "status": "delivered", "created_at": iso_days_ago(20)},
        {"text": "Command Center UI (Epic 4)", "status": "delivered", "created_at": iso_days_ago(5)},
        {"text": "ROLE OS Alpha demo package", "status": "planned", "created_at": iso_days_ago(1)},
    ])
    add_items(settings, role_os["id"], "todos", [
        {"text": "Write onboarding docs for new workspaces", "status": "open", "created_at": iso_days_ago(2)},
    ])
    add_items(settings, role_os["id"], "notes", [
        {"text": "Treat this project as the dogfood test bed for every new Epic.", "created_at": iso_days_ago(30)},
    ])
    add_items(settings, role_os["id"], "prompts", [
        {"text": "Design a modular knowledge extraction pipeline for ChatGPT exports.", "created_at": iso_days_ago(90)},
    ])

    add_items(settings, role_master["id"], "decisions", [
        {"text": "Lock the master color palette and typography.", "status": "resolved", "created_at": iso_days_ago(40)},
        {"text": "Decide on a single canonical avatar style for 2026.", "status": "pending", "created_at": iso_days_ago(4)},
    ])
    add_items(settings, role_master["id"], "deliverables", [
        {"text": "Brand identity guide v1", "status": "delivered", "created_at": iso_days_ago(35)},
        {"text": "Master character prompt library", "status": "delivered", "created_at": iso_days_ago(25)},
    ])
    add_items(settings, role_master["id"], "todos", [
        {"text": "Refresh the avatar for the 2026 campaign", "status": "open", "created_at": iso_days_ago(3)},
    ])
    add_items(settings, role_master["id"], "assets", [
        {"name": "role_master_logo.png", "created_at": iso_days_ago(35)},
        {"name": "brand_style_guide.pdf", "created_at": iso_days_ago(35)},
    ])
    pdb.link_conversation(role_master["id"], "conv-1", settings=settings)

    add_items(settings, super_facil["id"], "decisions", [
        {"text": "Target Spanish-first UX for the initial release.", "status": "pending", "created_at": iso_days_ago(10)},
    ])
    add_items(settings, super_facil["id"], "deliverables", [
        {"text": "MVP app shell", "status": "delivered", "created_at": iso_days_ago(18)},
        {"text": "Public beta build", "status": "planned", "created_at": iso_days_ago(6)},
    ])
    add_items(settings, super_facil["id"], "todos", [
        {"text": "Finish onboarding flow", "status": "open", "created_at": iso_days_ago(16)},
        {"text": "Wire up push notifications", "status": "open", "created_at": iso_days_ago(15)},
        {"text": "Fix Android build", "status": "open", "created_at": iso_days_ago(9)},
    ])

    add_items(settings, role_valdez["id"], "decisions", [
        {"text": "Consolidate all public content under one consistent voice.", "status": "resolved", "created_at": iso_days_ago(50)},
    ])
    add_items(settings, role_valdez["id"], "deliverables", [
        {"text": "Personal website relaunch", "status": "planned", "created_at": iso_days_ago(12)},
    ])
    add_items(settings, role_valdez["id"], "todos", [
        {"text": "Record intro video", "status": "open", "created_at": iso_days_ago(7)},
    ])

    add_items(settings, kontoor["id"], "decisions", [
        {"text": "Decide whether to retire the legacy CMDB in favor of Device42.", "status": "pending", "created_at": iso_days_ago(50)},
        {"text": "Decide on the FY26 Freshservice licensing tier.", "status": "pending", "created_at": iso_days_ago(40)},
    ])
    add_items(settings, kontoor["id"], "deliverables", [
        {"text": "Q2 SAM compliance report", "status": "planned", "created_at": iso_days_ago(48)},
    ])
    add_items(settings, kontoor["id"], "todos", [
        {"text": "Close out Freshservice change approval backlog", "status": "open", "created_at": iso_days_ago(90)},
        {"text": "Reconcile Device42 CMDB drift", "status": "open", "created_at": iso_days_ago(85)},
        {"text": "Migrate Jet Reports to the new server", "status": "open", "created_at": iso_days_ago(80)},
        {"text": "Renew BarTender licenses", "status": "open", "created_at": iso_days_ago(78)},
        {"text": "Audit Power BI workspace access", "status": "open", "created_at": iso_days_ago(70)},
        {"text": "Rotate service account credentials", "status": "open", "created_at": iso_days_ago(65)},
    ])

    add_items(settings, unger["id"], "deliverables", [
        {"text": "Monthly ops report", "status": "delivered", "created_at": iso_days_ago(22)},
    ])
    add_items(settings, unger["id"], "todos", [
        {"text": "Fix Power BI refresh failures", "status": "open", "created_at": iso_days_ago(34)},
        {"text": "Document Business Central approval workflow", "status": "open", "created_at": iso_days_ago(30)},
        {"text": "Reconcile vendor invoice report", "status": "open", "created_at": iso_days_ago(28)},
    ])

    add_items(settings, charcos["id"], "decisions", [
        {"text": "Pick a stage name variant for the 2026 season.", "status": "pending", "created_at": iso_days_ago(72)},
    ])
    add_items(settings, charcos["id"], "todos", [
        {"text": "Write 3 new verses", "status": "open", "created_at": iso_days_ago(75)},
        {"text": "Book studio time", "status": "open", "created_at": iso_days_ago(71)},
    ])

    # -----------------------------------------------------------------
    # Capabilities (provided + consumed)
    # -----------------------------------------------------------------

    cap_brand_identity = pdb.create_capability(role_master["id"], "Brand Identity System", description="Logo, avatar, color palette, and typography.", category="brand", settings=settings)
    cap_character_prompts = pdb.create_capability(role_master["id"], "Master Character Prompts", description="Canonical prompt library for the ROLE character.", category="brand", settings=settings)
    pdb.create_capability(role_master["id"], "Visual Style Guide", description="Shared visual language across every ROLE surface.", category="brand", settings=settings)

    cap_graph_api = pdb.create_capability(role_os["id"], "Knowledge Graph API", description="Query and traverse the ROLE OS relationship graph.", category="platform", settings=settings)
    pdb.create_capability(role_os["id"], "Project Intelligence Engine", description="Workspaces, projects, capabilities, dependencies, health scoring.", category="platform", settings=settings)

    cap_personal_voice = pdb.create_capability(role_valdez["id"], "Personal Brand Voice", description="Consistent public voice and tone guidelines.", category="brand", settings=settings)

    pdb.consume_capability(cap_brand_identity["id"], super_facil["id"], settings=settings)
    pdb.consume_capability(cap_graph_api["id"], super_facil["id"], settings=settings)
    pdb.consume_capability(cap_character_prompts["id"], charcos["id"], settings=settings)
    pdb.consume_capability(cap_personal_voice["id"], charcos["id"], settings=settings)

    # -----------------------------------------------------------------
    # Dependencies
    # -----------------------------------------------------------------

    pdb.create_dependency(super_facil["id"], role_master["id"], note="Needs the finalized brand identity before launch.", settings=settings)
    pdb.create_dependency(super_facil["id"], role_os["id"], note="Runs on ROLE OS's knowledge engine.", settings=settings)
    pdb.create_dependency(charcos["id"], role_master["id"], note="Uses the master character system for the stage persona.", settings=settings)

    # -----------------------------------------------------------------
    # Related projects (linked both directions)
    # -----------------------------------------------------------------

    for a, b in [(role_os, role_master), (kontoor, unger), (role_valdez, charcos)]:
        pdb.link_related_project(a["id"], b["id"], settings=settings)
        pdb.link_related_project(b["id"], a["id"], settings=settings)

    # -----------------------------------------------------------------
    # Backdate activity for the projects that should look stale/neglected
    # -----------------------------------------------------------------

    force_updated_at(settings, kontoor["id"], iso_days_ago(95))
    force_updated_at(settings, unger["id"], iso_days_ago(35))
    force_updated_at(settings, charcos["id"], iso_days_ago(70))

    # -----------------------------------------------------------------
    # Recompute real Health Scores from the seeded data (never hand-set)
    # -----------------------------------------------------------------

    def conversation_dates(conversation_ids: list[str]) -> list[str]:
        dates: list[str] = []
        for conversation_id in conversation_ids:
            try:
                card = knowledge_db.get_card(conversation_id, settings)
            except knowledge_db.DatabaseUnavailableError:
                break
            if card and card.get("updated"):
                dates.append(card["updated"])
        return dates

    for project in pdb.list_projects(settings=settings):
        full = pdb.get_project(project["id"], settings=settings)
        dates = conversation_dates(full.get("conversations", []))
        result = compute_health_score(full, conversation_dates=dates)
        pdb.set_health_score(project["id"], result["score"], settings=settings)

    # -----------------------------------------------------------------
    # Generate a first batch of Advisor recommendations from this data
    # -----------------------------------------------------------------

    recs = advisor_engine.get_recommendations(settings=settings)

    print(f"Seeded 7 projects across 5 workspaces.")
    print(f"Generated {len(recs)} Advisor recommendation(s).")
    print("Done.")


if __name__ == "__main__":
    main()
