# Quick Start

The fastest path from a fresh clone to using every part of ROLE OS: the
Builder, the Dashboard, the ChatGPT Importer, the Conversation Explorer,
the AI Advisor, the executive Dashboard page, and Settings. This walkthrough
uses the seeded Alpha demo data so there's something to explore
immediately — no ChatGPT export required to get started.

## 1. Clone

```bash
git clone https://github.com/rolevc-valdez/ROLE_OS.git
cd ROLE_OS
```

## 2. Install

Everything — virtual environment, dependencies, demo data, and the server
— is handled by one script. No manual `pip install` step is required for
this path.

**macOS / Linux:**
```bash
./scripts/run_alpha.sh
```

**Windows:**
```bat
scripts\run_alpha.bat
```

The first run creates a local `.venv`, installs `dashboard/requirements.txt`,
and seeds the Alpha demo data into `var/role_os_alpha/` (idempotent — safe
to re-run without duplicating data or resetting anything you've done in the
UI).

If you'd rather install manually (no demo data), see
[`INSTALLATION.md`](INSTALLATION.md).

## 3. Run

The script above starts the dashboard automatically at
**http://127.0.0.1:8000/**. Open that URL once the terminal prints
`Uvicorn running on http://127.0.0.1:8000`.

If you're running manually instead:

```bash
cd dashboard
uvicorn app.main:app --reload
```

## 4. Import conversations

The Alpha demo already has seeded projects, but you can also bring in your
own ChatGPT conversation history:

- In the UI: sidebar → **Knowledge**, use the "Import ChatGPT conversations"
  panel to upload your export's `conversations.json` (or the export ZIP).
- From the CLI:
  ```bash
  python scripts/import_chatgpt.py "<path-to-conversations.json>"
  ```

Re-importing the same file is safe — it never creates duplicates (see
[`dashboard/README.md`](dashboard/README.md#chatgpt-conversation-importer--conversation-explorer-domain-sprint-b1--b15)
for the deduplication rules).

## 5. Explore data

- Sidebar → **Explorer** — browse, search, filter, and inspect every
  imported conversation; open one and click **Extract Knowledge** to pull
  out Projects, People, Tasks, Decisions, Ideas, Documents, and Assets.
- Sidebar → **Knowledge Graph** — see imported conversations connected to
  what was extracted from them.
- Sidebar → **Projects** — open **Kontoor** to see a critical Health Score
  with a real breakdown, or **ROLE MASTER** for a healthy one (Alpha demo
  data).
- Sidebar → **Graph** — the full-screen Knowledge Graph over Projects,
  Capabilities, Dependencies, and more; try zoom/pan and **Impact
  analysis**.

## 6. Use the Advisor

Sidebar → **Advisor**:

- **Search Knowledge** at the top — keyword search across every imported
  conversation and extracted object, with *Open Conversation* / *Open
  Graph* actions on each result.
- Below that, the **Daily Brief** and recommendation cards grouped by
  workspace — each showing evidence, impact, estimated effort, and
  Dismiss / Mark completed actions.

## 7. Open the Dashboard

Sidebar → **Dashboard** — an executive summary: ten live count cards
(Conversations, Projects, People, Tasks, Decisions, Ideas, Documents,
Assets, Graph Nodes, Graph Edges), Recent Activity, System Status, and
Quick Actions to Import / Explorer / Knowledge Graph / Search Knowledge.

## 8. Open Settings

Sidebar → **Settings** — general configuration (app version, database
paths, search result limit), live system status (counts, database sizes,
last import/extraction dates), About (version, git commit, license), and
maintenance actions:

- **Export configuration** — download current settings as JSON.
- **Import configuration** — upload a configuration file to preview which
  environment variables it maps to (this never applies automatically —
  see [`dashboard/README.md`](dashboard/README.md#settings-domain-sprint-8)
  for why).
- **Rebuild graph** / **Clear cache** — maintenance actions.

## Next steps

- [`DEMO.md`](DEMO.md) — a deeper walkthrough of the seeded Alpha demo data.
- [`INSTALLATION.md`](INSTALLATION.md) — manual setup, environment
  variables, and troubleshooting.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how everything above fits
  together.
