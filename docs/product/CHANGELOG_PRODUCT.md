# Product Changelog

A product-facing summary of what ROLE OS can do at each stage — written
for someone deciding whether/how to use it, not for someone reading a
diff. For full engineering detail, see `CHANGELOG.md` at the repo root;
for the reasoning behind key choices, see [[DECISIONS]].

## Conversation Explorer (Sprint B1.5)

You can now browse, search, filter, inspect, and manage everything the
ChatGPT importer has brought in, from a dedicated Explorer page (sidebar →
Explorer). A metrics strip shows what's real today (imported conversation
count) and what's honestly still `0` (processing, knowledge objects,
projects, decisions, assets — none of that exists yet for imported
conversations). A search box matches title, message text, source, or
conversation id in one query; filters for source, status, and "imported
today/this week/this month" are built from whatever data actually exists
rather than a hard-coded list, so a future provider (Claude, Gemini,
Gmail, ...) becomes a filter option automatically the moment something
from it is imported. Opening a conversation shows its full message
timeline exactly as imported — never summarized, never modified — with
USER/ASSISTANT/SYSTEM visually distinguished, a search-within-conversation
box, a metadata panel, and Copy / Export JSON / Delete (delete requires
confirmation and is permanent). This sprint deliberately adds no AI,
extraction, project matching, or graph inference — it's strictly a window
onto imported data; see
[`dashboard/README.md`](../../dashboard/README.md) for the full API,
search/filter behavior, and known limitations.

## ChatGPT Conversation Importer (Sprint B1)

You can now bring ChatGPT conversations into ROLE OS directly — via the
Knowledge page, the API, or a CLI command — without regenerating the whole
knowledge base offline. It validates the export, normalizes each
conversation's metadata and content, and reports exactly what happened:
imported, updated, skipped (duplicate), or invalid. Re-running the same
import never creates duplicates. This sprint deliberately does not do any
AI knowledge extraction, project matching, or graph linking for imported
conversations — that stays the Builder's job; see
[`dashboard/README.md`](../../dashboard/README.md)
for the supported format, deduplication behavior, and known limitations.

## Alpha — one-command demo

You can now go from a fresh clone to a fully working, seeded instance of
ROLE OS in one command (`scripts/run_alpha.sh` / `run_alpha.bat`): seven
realistic demo projects across five workspaces, with real (not
hard-coded) Health Scores, Advisor recommendations, and a populated
Knowledge Graph, so the whole product can be explored before bringing
your own data. See `DEMO.md` for the full walkthrough.

## Command Center — a real product UI (Epic 4)

The dashboard was redesigned from a tab-based prototype into a proper
application: a persistent sidebar, a Home page that surfaces what to work
on today, a redesigned Project page, a full-screen interactive Knowledge
Graph with zoom/pan and impact analysis, and a dedicated Advisor page —
all dark-themed, framework-free, and instant (no build step). No backend
functionality changed to build it — it's a new coat of paint over
everything below, proving the product's data layer was already complete
enough to power a real UI.

## Knowledge Graph — see how everything connects (Epic 3)

ROLE OS can now answer "how does everything connect?" directly: 12 kinds
of entities (Projects, Knowledge Cards, People, Applications, Vendors,
Capabilities, Workspaces, Decisions, Deliverables, Prompts, Assets,
Conversations) and 12 kinds of relationships between them, browsable in an
interactive graph. You can click any node, expand its neighbors, search,
filter by type/workspace/relationship, find the shortest path between two
things, and run **impact analysis** — "if this project changes, what else
is affected, down to which Advisor recommendations exist because of it?"
Nothing about this graph is stored separately from your actual data; it's
always computed fresh, so it can never go stale.

## AI Advisor — know what to work on next (Epic 2)

ROLE OS now tells you what to do next, with a reason you can trust: eight
independent rules look at staleness, blocked dependencies, near-complete
projects, missing deliverables, overdue to-dos, critical health, inactive
high-priority work, and capability-reuse opportunities, and turn what they
find into ranked recommendations — each with the evidence behind it, a
suggested action, and the expected impact of taking it. A Daily Brief
rolls the most important ones up into one view. None of this calls an
external AI service; every recommendation is explainable because it's
built directly from your own project data, not generated.

## Project Intelligence — projects that actually track state (Epic 1)

Beyond browsing knowledge, ROLE OS now models real Projects: workspaces,
status, priority, notes, decisions, to-dos, deliverables, capabilities a
project offers or consumes, dependencies on other projects (in both
directions), and an explainable Health Score (0-100) built from real
signals like activity recency and open work — not a single opaque number.

## Knowledge Engine 2.0 (Milestone 3)

Every conversation you import is enriched further: real vendor detection,
file references, and up to five related conversations per card, so your
knowledge base starts connecting itself.

## First usable dashboard (Milestone 2)

ROLE OS became a browsable web app for the first time: global search, a
project list, recent knowledge cards, a timeline, and a card detail view
— all served locally, no external service required.

## Knowledge API (Milestone 1)

The foundation: turn a ChatGPT export into a searchable knowledge base
with a simple read-only API (`/health`, `/projects`, `/search`,
`/knowledge/{id}`) over a local SQLite database. No AI features.

## Where to go next

- [[DECISIONS]] — why key product choices were made.
- [[../architecture/07_ROADMAP]] — the engineering-level roadmap and open seams.
- `DEMO.md` (repo root) — try the Alpha demo yourself.
