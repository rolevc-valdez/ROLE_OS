from __future__ import annotations

import argparse
import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from knowledge_extractor import attach_related_conversations, build_card

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger("role-os")


def text_from_message(msg: dict) -> str:
    content = (msg or {}).get("content") or {}
    parts = content.get("parts") or []
    return "\n".join(x for x in parts if isinstance(x, str)).strip()


def load_conversations(source: Path):
    keep = None
    if source.is_file() and source.suffix.lower() == ".zip":
        keep = tempfile.TemporaryDirectory()
        root = Path(keep.name)
        with zipfile.ZipFile(source) as z:
            names = [n for n in z.namelist() if Path(n).name.startswith("conversations-") and n.endswith(".json")]
            if not names:
                raise FileNotFoundError("The ZIP does not contain conversations-*.json files")
            for name in names:
                z.extract(name, root)
        files = sorted(root.rglob("conversations-*.json"))
    elif source.is_dir():
        files = sorted(source.rglob("conversations-*.json"))
    elif source.is_file():
        files = [source]
    else:
        raise FileNotFoundError(f"Source not found: {source}")

    conversations = []
    for file in files:
        LOG.info("Reading %s", file.name)
        with file.open(encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                conversations.extend(data)
    return conversations, keep


def ordered_messages(conversation: dict) -> list[tuple[str, str]]:
    messages = []
    for node in (conversation.get("mapping") or {}).values():
        message = node.get("message") or {}
        text = text_from_message(message)
        if not text:
            continue
        role = ((message.get("author") or {}).get("role") or "unknown")
        created = message.get("create_time") or 0
        messages.append((created, role, text))
    messages.sort(key=lambda x: x[0])
    return [(role, text) for _, role, text in messages]


def safe_name(value: str) -> str:
    clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in value).strip("_")
    return clean[:90] or "UNTITLED"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_indices(cards: list[dict], knowledge: Path) -> None:
    projects: dict[str, list[dict]] = defaultdict(list)
    people: dict[str, list[str]] = defaultdict(list)
    apps: dict[str, list[str]] = defaultdict(list)
    vendors: dict[str, list[str]] = defaultdict(list)
    tags: dict[str, list[str]] = defaultdict(list)

    for card in cards:
        mini = {"id": card["conversation_id"], "title": card["title"], "date": card["date"], "status": card["status"]}
        projects[card["project"]].append(mini)
        for item in card["people"]:
            people[item].append(card["conversation_id"])
        for item in card["applications"]:
            apps[item].append(card["conversation_id"])
        for item in card.get("vendors", []):
            vendors[item].append(card["conversation_id"])
        for item in card["tags"]:
            tags[item].append(card["conversation_id"])

    write_json(knowledge / "PROJECTS.json", projects)
    write_json(knowledge / "PEOPLE.json", people)
    write_json(knowledge / "APPLICATIONS.json", apps)
    write_json(knowledge / "VENDORS.json", vendors)
    write_json(knowledge / "TAGS.json", tags)
    write_json(knowledge / "TIMELINE.json", sorted([
        {"id": c["conversation_id"], "date": c["date"], "updated": c["updated"], "title": c["title"], "project": c["project"]}
        for c in cards
    ], key=lambda x: x["date"] or ""))


def write_database(cards: list[dict], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS knowledge_cards(
      conversation_id TEXT PRIMARY KEY,
      title TEXT, project TEXT, category TEXT, status TEXT,
      date TEXT, updated TEXT, summary TEXT, card_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cards_project ON knowledge_cards(project);
    CREATE INDEX IF NOT EXISTS idx_cards_date ON knowledge_cards(date);
    DELETE FROM knowledge_cards;
    """)
    db.executemany(
        "INSERT OR REPLACE INTO knowledge_cards VALUES(?,?,?,?,?,?,?,?,?)",
        [(c["conversation_id"], c["title"], c["project"], c["category"], c["status"], c["date"], c["updated"], c["summary"], json.dumps(c, ensure_ascii=False)) for c in cards],
    )
    db.commit()
    db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ROLE Knowledge OS from a ChatGPT export")
    parser.add_argument("source", help="ChatGPT export ZIP or folder containing conversations-*.json")
    parser.add_argument("output", help="Destination ROLE_KNOWLEDGE_OS folder")
    parser.add_argument("--clean", action="store_true", help="Replace generated knowledge cards and indexes")
    args = parser.parse_args()

    source, output = Path(args.source), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    system = output / "00_SYSTEM"
    projects_root = output / "01_PROJECTS"
    knowledge = output / "04_KNOWLEDGE"
    cards_dir = knowledge / "KNOWLEDGE_CARDS"

    if args.clean and cards_dir.exists():
        shutil.rmtree(cards_dir)
    cards_dir.mkdir(parents=True, exist_ok=True)
    projects_root.mkdir(parents=True, exist_ok=True)

    conversations, keep = load_conversations(source)

    # Pass 1: build a KnowledgeCard for every conversation independently.
    cards: list[dict] = []
    for conversation in conversations:
        messages = ordered_messages(conversation)
        card = build_card(conversation, messages).to_dict()
        cards.append(card)

    # Pass 2: link related conversations now that every card is classified
    # and tagged (relatedness needs the full corpus, not a single card).
    attach_related_conversations(cards)

    # Pass 3: persist. Card files, indexes, and SQLite all reflect the fully
    # enriched cards, including related_conversations.
    grouped: dict[str, list[dict]] = defaultdict(list)
    for index, card in enumerate(cards, start=1):
        grouped[card["project"]].append(card)
        write_json(cards_dir / f"{index:05d}_{safe_name(card['title'])}.json", card)

    build_indices(cards, knowledge)
    write_database(cards, system / "role_os.db")

    master = [
        "# ROLE OS — MASTER INDEX", "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Conversations indexed: {len(cards)}", "",
    ]
    for project, items in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        pdir = projects_root / project
        pdir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {project}", "", f"Conversations: {len(items)}", ""]
        for item in sorted(items, key=lambda x: x.get("updated") or "", reverse=True):
            lines.append(f"- {item['title']} — {item['status']}")
        (pdir / "README.md").write_text("\n".join(lines), encoding="utf-8")
        master.extend([f"## {project} ({len(items)})", ""] + [f"- {x['title']}" for x in items[:50]] + [""])

    system.mkdir(parents=True, exist_ok=True)
    (system / "MASTER_INDEX.md").write_text("\n".join(master), encoding="utf-8")
    (output / "README.md").write_text(
        f"# ROLE KNOWLEDGE OS\n\nGenerated from ChatGPT export.\n\nConversations indexed: {len(cards)}\n",
        encoding="utf-8",
    )

    result = {
        "status": "ok",
        "version": "0.3",
        "conversations": len(cards),
        "projects": {k: len(v) for k, v in sorted(grouped.items())},
        "knowledge_cards": len(cards),
        "output": str(output),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if keep:
        keep.cleanup()


if __name__ == "__main__":
    main()
