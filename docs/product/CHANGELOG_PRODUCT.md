# Product Changelog

A product-facing summary of what ROLE OS can do at each stage — written
for someone deciding whether/how to use it, not for someone reading a
diff. For full engineering detail, see `CHANGELOG.md` at the repo root;
for the reasoning behind key choices, see [[DECISIONS]].

## Executive Decision Engine (Sprint C10)

ROLE OS stops being a place you check for information and becomes a
system that tells you what to do. Open Mission Control and the very
first thing you see is a "TODAY" card: the one project ROLE OS
recommends working on right now, why (in plain evidence, never a guess),
the expected benefit, how much effort and time it should take, the next
concrete action, and the expected result. Below it, every adopted
project is ranked against every other one — a real competition, not a
list — each with its own short explanation of why it landed where it
did. Every score is built from facts ROLE OS already tracks: how urgent
Operational Intelligence says a project is, how commercially valuable it
is, how many other projects are waiting on it, how much risk changing it
carries, whether there's real pending work, how recently it's been
touched, and its health score — nothing invented, nothing hidden, and
never a tie between two projects. Search now understands this too:
typing "today," "decision," "recommend," or a project's own name surfaces
the current recommendation as a searchable card. No AI, no scheduling
engine, no calendar — just today's single highest-value next step,
explained.

## Impact Analysis Engine (Sprint C9)

ROLE OS can now answer "if I change this project, what else breaks?" Open
any project and you'll see a new Impact Analysis section: an overall risk
level (None through Critical), the specific other projects affected, the
top reasons why, and recommended next steps — "notify 2 dependent projects
before making breaking changes," "verify shared assets remain compatible."
Every risk level and every affected project is backed by real evidence you
can read, never a guess — and the analysis follows dependency chains
several hops deep (change ROLE OS, see that it reaches ROLE Commerce
Factory and, through it, RoleValdez.com), stopping cleanly rather than
looping forever if projects depend on each other in a cycle. Search
understands this too: searching a project's name now includes an "Impact
of changing X" result. Mission Control can now warn you before you start
a risky change — "Changing ROLE OS today will affect 3 projects — schedule
accordingly" — and Project Memory shows a compact "Potential Impact" line
so you see the blast radius the moment you resume a project. No diagrams;
just clear, evidence-backed cards.

## Project Ecosystem Engine (Sprint C8)

ROLE OS can now answer questions about how your projects connect to each
other — not just what each one is doing on its own. Open any project and
you'll see a new Ecosystem section: what it depends on, what depends on
it, what's blocking it (or what it's blocking), and what it shares with
other projects — the same reusable logo showing up in two places, a
README that mentions another project by name, a conversation touching on
work that spans projects. Every one of these is backed by real, visible
evidence — never a guess, never an AI inference. Search now understands
this too: searching a project's name shows you who's using it; searching
"shared assets" shows you which projects share files. And when Mission
Control recommends a project, it can now tell you when finishing that
project's work would unblock other projects waiting on it — "Complete
ROLE OS to unblock ROLE Commerce Factory, RoleValdez.com," with the real
dependency evidence behind that claim.

## Resume Work Refactor (Sprint C7.1)

Resume Work now does what it always should have: it resumes your
*project*, not just a leftover AI chat session. Clicking Resume Work
builds its prompt from the project's own memory — its current objective,
where you left off, what's still pending, its next action, and the
system's current recommendation for it — and only then finds (or starts)
the right conversation to continue in. Before this fix, a thin or
never-updated chat session could produce a thin, generic prompt, leaving
the assistant to ask what you were even working on; that can no longer
happen, because the project's real state is always the source, never the
chat session. When more than one conversation exists for a project, ROLE
OS picks the most sensible one to reopen (the one you were actively using,
then a pinned one, then your usual one, then simply the newest) and tells
you why. Every new session also gets a real name — "ROLE Commerce
Factory — Shopify Adapter," never "Untitled" or "Session 1" — and an old
session still carrying the placeholder name from before this fix gets
renamed automatically the next time you resume it. In Cockpit, the
project's memory is now the main thing you see; the list of AI sessions
is still there, just no longer front and center.

## Operational Intelligence Engine (Sprint C6)

ROLE OS no longer just tells you what's happening — it explains what
should happen next, and always answers why. Every recommendation you see
across Mission Control, Advisor, and Explorer now comes from one shared
engine that reasons over real, already-computed evidence about your
projects: health, git status, recent commits, snapshots, pending work,
next actions, roadmap/TODO presence, commercial readiness, business
priority, dependencies, capabilities, assets, documentation, recent
activity, and — new this sprint — how fresh your imported Knowledge Graph
is and how fresh your last Discovery scan is. No AI model, no embeddings,
no external API is involved anywhere in this — every recommendation traces
back to a deterministic rule you can point to, with the concrete evidence
behind it, a plain-English expected benefit, and a suggested next action.
Two rule sets that already existed (the git/health-driven Workspace Advisor
and the dependency/TODO-driven Project Intelligence Advisor) are combined
into this one engine rather than replaced, so nothing you relied on before
changed — Advisor's dismiss/complete history is untouched — you're just no
longer choosing between two different opinions.

## Mission Control (Sprint C5)

Opening ROLE OS now answers, in one screen and within seconds: what should
I work on today, where did I leave off, what changed since I last worked,
what needs attention, and what's closest to actually shipping. Mission
Control is the new default page (previously Home) — one dominant card
recommends a project to continue, with the real reason why (recent
activity, an open next action, business value) and a one-click **Resume
Work**; up to three other things worth your attention today; what's
changed since your last Daily Session (or the last 24 hours, honestly
labeled, if you've never started one); the most important unresolved
issues, most serious first; whichever project is genuinely closest to
launch (only shown when the evidence — health score and commercial
readiness — actually supports it, never a guess); a compact overview of
every project; recent activity; today's Daily Session status; a prompt to
save a snapshot before switching projects; and quick actions to the pages
you use daily. Nothing here is a new recommendation engine — every
number and ranking reuses what Home, the Workspace Advisor, and Dashboard
already compute, just organized around "what do I do next" instead of
"what does the portfolio look like." Dashboard is unchanged and still
available for the deeper, report-style view.

## Workspace Adoption (Discovery Engine Sprint 2)

ROLE OS can now tell you what you're actually working on without being
asked to type it in. A new sidebar page, **Workspace**, lists every real
project folder found on disk (name, folder path, type, git branch/status,
health score, confidence, and move risk), computed by the read-only
Discovery Engine (Sprint 1) — click **Rescan Workspace** any time to
refresh it. For each one you can **Adopt** it (bring it into ROLE OS,
optionally setting priority, business value, status, and tags), **Ignore**
it (hide something that isn't really a project, e.g. an app-data folder),
or **Review** it (see the full discovery detail: languages, docs, tests,
assets, and why it got the move-risk/recommendation it did). Adopting
never copies the folder's data into a database record — name, git status,
and health stay live, read straight from disk every time; ROLE OS only
remembers the handful of things you decided (priority, business value,
status, tags, notes, and whether you've adopted or ignored it). The
Projects page now shows adopted projects alongside manually-created ones,
labeled "Discovered" — creating a Project by hand still works exactly as
before. See [`08_IMPORT_ENGINE_PROPOSAL.md`](../architecture/08_IMPORT_ENGINE_PROPOSAL.md)
for the full architecture and what's still to come (Advisor/Health/Mission
Control wiring, in later sprints).

## Dashboard (Sprint 7)

ROLE OS now has a proper executive Dashboard (sidebar → Dashboard): ten
summary cards (Conversations, Projects, People, Tasks, Decisions, Ideas,
Documents, Assets, Graph Nodes, Graph Edges), Recent Activity (the latest
imported conversations and the latest extracted knowledge objects),
System Status (when you last imported and last extracted, whether the
Knowledge Graph has data, whether the databases are reachable), and Quick
Actions to jump straight to importing a conversation, the Conversation
Explorer, the Knowledge Graph, or Search Knowledge. Every number on this
page is real — read directly from data ROLE OS already computed, nothing
recalculated, nothing new stored, nothing AI-generated. This is a second,
separate landing page from the original Home (which still covers Project
Intelligence, the Advisor's recommendations, and the Epic 3 Graph) — the
Dashboard is specifically the mission-control view for everything the
Importer → Explorer → Extraction → Knowledge Graph → Advisor Search
pipeline has built. See [`dashboard/README.md`](../../dashboard/README.md)
for exactly which existing endpoint backs each card.

## Advisor Search (Sprint 6)

The Advisor page can now answer "where is everything about X?" — type
into the new Search Knowledge box (top of the Advisor page) and get
matching conversations, Projects, People, Tasks, Decisions, Ideas,
Documents, and Assets back immediately, live as you type. Filter to just
one type — pick "Projects" with an empty search box and get every
extracted Project; type "GitHub" with no filter and get every
conversation and object mentioning it. Every result shows what it is,
its name, its source conversation, when it was created, and a confidence
score where one exists, plus one-click actions to open the full
conversation or jump to its place in the Knowledge Graph. This is
deliberately not AI: no chat, no LLM, no semantic search, no embeddings,
no recommendations — just fast, honest keyword matching over knowledge
ROLE OS already extracted. See
[`dashboard/README.md`](../../dashboard/README.md) for the full query
semantics and known limitations.

## Knowledge Graph (Sprint 5)

ROLE OS can now show you how your imported conversations and the
knowledge extracted from them actually connect — a new **Knowledge
Graph** page (sidebar → Knowledge Graph) alongside the existing Graph
page. Every imported conversation appears as a node; every Project,
Person, Task, Decision, Idea, Document, and Asset extracted from it
appears as its own node, connected back to that conversation. Click any
node to see its details — a conversation's title, source, and message
count, or a knowledge object's value, confidence, and source conversation
— with zoom, pan, and reset-view, plus filters for conversation and node
type. From the Conversation Explorer, "View in Knowledge Graph" jumps
straight to a conversation's subgraph; from the graph, "Open in
Conversation Explorer" jumps back. This is a second, independent graph
from the existing Graph page (which covers Projects/Advisor/Builder data)
— not a replacement or extension of it. Nothing here is inferred or
AI-generated: the only relationship shown is the one the extraction
pipeline already recorded (a conversation contains the objects extracted
from it); see [`dashboard/README.md`](../../dashboard/README.md) for the
full node/relationship vocabulary, how the graph is generated, and known
limitations.

## Knowledge Extraction (Sprint 4)

Every imported conversation can now be turned into structured knowledge:
open it in the Explorer and click "Extract Knowledge" to pull out exactly
seven kinds of objects — **Projects, People, Tasks, Decisions, Ideas,
Documents, Assets** — each shown with a confidence score and a Delete
action. This is deliberately not AI: extraction is deterministic pattern
matching (keyword lines for Projects/Tasks/Decisions/Ideas, capitalized
name detection for People, file-extension detection for Documents/Assets)
— the same rule-based approach the Builder has always used, just applied
to imported conversations without regenerating the whole knowledge base.
Re-running extraction on the same conversation never creates duplicates:
new objects are added, changed ones are updated, unchanged ones are left
alone. The Explorer's dashboard metrics now show real counts for all
seven types plus a Knowledge Objects total, instead of the placeholder
zeros from Sprint B1.5. This sprint adds no AI chat, no knowledge graph
linking, no Advisor recommendations, and no summarization — see
[`dashboard/README.md`](../../dashboard/README.md) for the full detection
rules, deduplication behavior, and known limitations.

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
