# ROLE OS Builder v0.2

Builds the ROLE Knowledge OS folder structure and SQLite knowledge base from a
ChatGPT conversations export.

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

### Windows

Double-click `run_windows.bat` and follow the prompts, or run:

```bat
run_windows.bat
```

## Output

Running the builder populates the destination folder with:

- `00_SYSTEM/MASTER_INDEX.md` — human-readable index of all conversations by project
- `00_SYSTEM/role_os.db` — SQLite database with a `knowledge_cards` table
- `01_PROJECTS/<PROJECT>/README.md` — one folder per detected project
- `04_KNOWLEDGE/KNOWLEDGE_CARDS/*.json` — one knowledge card per conversation
- `04_KNOWLEDGE/PROJECTS.json`, `PEOPLE.json`, `APPLICATIONS.json`, `TAGS.json`, `TIMELINE.json` — cross-reference indexes
- `README.md` — summary of the generated output

The dashboard app in `/dashboard` reads the same SQLite database
(`role_os.db`) to serve the knowledge base over HTTP.

## Files

- `builder.py` — CLI entry point; orchestrates parsing, classification, index
  building, and SQLite writes.
- `knowledge_extractor.py` — classification rules and per-conversation
  knowledge card extraction.
- `run_windows.bat` — interactive Windows launcher.

## New in v0.2

- Improved classification
- One Knowledge Card per conversation
- SQLite knowledge table
- PROJECTS, PEOPLE, APPLICATIONS, TAGS and TIMELINE indexes
