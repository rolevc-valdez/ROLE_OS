# ROLE OS Builder v0.3 — Knowledge Engine 2.0

Builds the ROLE Knowledge OS folder structure and SQLite knowledge base from a
ChatGPT conversations export, using a modular knowledge extraction pipeline
that enriches every Knowledge Card.

## Requirements

- Python 3.10+
- No third-party packages (see `requirements.txt`)

## Usage

From the `builder/` directory:

```bash
python builder.py "<path-to-chatgpt_export.zip-or-folder>" "<path-to-ROLE_KNOWLEDGE_OS-destination>" --clean
```

- First argument: a ChatGPT export ZIP, a folder containing it, or a folder/file
  with `conversations-*.json` files directly.
- Second argument: destination folder where the ROLE Knowledge OS will be generated.
- `--clean` (optional): wipes previously generated knowledge cards before rebuilding.

This CLI contract is unchanged since v0.2.

### Windows

Double-click `run_windows.bat` and follow the prompts, or run:

```bat
run_windows.bat
```

## The knowledge extraction engine

Every conversation is run through a pipeline of modular extractors under
`extractors/`, each responsible for one part of the Knowledge Card:

| Extractor              | Produces                                    |
|-------------------------|-----------------------------------------------|
| `extractors/summary.py`   | Summary                                      |
| `extractors/decisions.py` | Decisions, Deliverables                      |
| `extractors/todos.py`      | Open TODOs                                  |
| `extractors/prompts.py`     | Prompts (the user's own messages, in order) |
| `extractors/entities.py`     | People, Applications, Vendors, URLs, Files, project/category classification, Tags |
| `extractors/relationships.py` | Related conversations (corpus-level pass) |

`extractors/__init__.py` defines the `KnowledgeCard` dataclass and
`build_knowledge_card()`, which runs every per-conversation extractor and
merges their output into a single card. Relatedness is different from the
others: it needs the *entire* set of cards (not just one conversation), so
`builder.py` runs it as a second pass, after every card has been built:

1. Build a `KnowledgeCard` per conversation (summary, decisions, todos,
   deliverables, prompts, people, applications, vendors, urls, files, tags).
2. Run `attach_related_conversations()` over the full set of cards to link
   each conversation to up to 5 related conversations (weighted overlap of
   project, tags, people, and applications — no AI/embeddings involved yet).
3. Write the enriched cards to disk, rebuild the cross-reference indexes,
   and update the SQLite database.

`knowledge_extractor.py` is kept as a thin backward-compatible wrapper
(`build_card`) around `extractors.build_knowledge_card`, so any existing code
importing it keeps working unchanged.

## Output

Running the builder populates the destination folder with:

- `00_SYSTEM/MASTER_INDEX.md` — human-readable index of all conversations by project
- `00_SYSTEM/role_os.db` — SQLite database with a `knowledge_cards` table, updated automatically on every run
- `01_PROJECTS/<PROJECT>/README.md` — one folder per detected project
- `04_KNOWLEDGE/KNOWLEDGE_CARDS/*.json` — one enriched knowledge card per conversation
- `04_KNOWLEDGE/PROJECTS.json`, `PEOPLE.json`, `APPLICATIONS.json`, `VENDORS.json`, `TAGS.json`, `TIMELINE.json` — cross-reference indexes
- `README.md` — summary of the generated output

Each Knowledge Card now includes: `summary`, `decisions`, `deliverables`,
`todos`, `prompts`, `people`, `applications`, `vendors`, `urls`, `files`,
`tags`, and `related_conversations`. `assets` is kept as a deprecated alias
for `files` for backward compatibility with earlier consumers.

The dashboard app in `/dashboard` reads the same SQLite database
(`role_os.db`) to serve the knowledge base over HTTP — no dashboard changes
were required for Milestone 3, since the new fields pass through the
existing `/knowledge/{id}` response automatically.

## Files

```
builder/
  builder.py               # CLI entry point: orchestrates parsing, the enrichment
                              pipeline, index building, and SQLite writes
  knowledge_extractor.py     # Backward-compatible wrapper around extractors.build_knowledge_card
  extractors/
    __init__.py                # KnowledgeCard dataclass + build_knowledge_card() pipeline
    _util.py                    # Shared helpers (not an extractor)
    summary.py                   # Summary
    decisions.py                  # Decisions, Deliverables
    todos.py                       # Open TODOs
    prompts.py                      # Prompts
    entities.py                      # People, Applications, Vendors, URLs, Files, Tags, project classification
    relationships.py                  # Related conversations (corpus-level)
  tests/                        # Unit + integration regression tests (pytest)
  run_windows.bat             # Interactive Windows launcher
```

## Changelog

### v0.3 — Knowledge Engine 2.0

- Modular extraction pipeline under `extractors/`.
- New fields: `vendors` (real extraction, previously always empty), `files`
  (previously only exposed as `assets`), `related_conversations` (new).
- New `VENDORS.json` cross-reference index.
- SQLite (`role_os.db`) updated automatically with the enriched cards.
- `knowledge_extractor.build_card` kept as a backward-compatible alias.

### v0.2

- Improved classification
- One Knowledge Card per conversation
- SQLite knowledge table
- PROJECTS, PEOPLE, APPLICATIONS, TAGS and TIMELINE indexes
