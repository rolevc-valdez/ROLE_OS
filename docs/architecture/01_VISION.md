# 01 — Vision

## What ROLE OS is

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and has evolved from a Knowledge Browser into a
**Knowledge Operating System**:

- a read-only knowledge API and dashboard (Milestones 1–3),
- a first-class **Project Intelligence** layer — workspaces, projects,
  capabilities, dependencies, a Health Score engine (Epic 1),
- an explainable **AI Advisor** that recommends what to work on next
  (Epic 2),
- a **Knowledge Graph** engine that connects Projects, Knowledge Cards,
  People, Applications, Vendors, Capabilities, Workspaces, Decisions,
  Deliverables, Prompts, Assets, and Conversations into one queryable
  relationship graph, computed on demand with no separate graph database
  (Epic 3),
- and a **Command Center** UI — a persistent sidebar, a Home page, a
  redesigned Project page, a full-screen Graph page, and an Advisor page,
  built entirely in plain HTML/CSS/vanilla JS on top of the existing API
  (Epic 4).

## Why it exists

A ChatGPT export is a flat pile of transcripts. It has no notion of a
project, no memory of a decision once it scrolls off screen, and no way to
tell you what to work on next. ROLE OS exists to turn that pile into
something that behaves like an operating system for personal/professional
knowledge: projects that persist and evolve, decisions and deliverables
that are captured instead of lost, dependencies between projects that are
explicit, and recommendations about what matters right now — all derived
from data that already exists, without requiring the user to re-enter
anything.

## What "done" looks like for the core loop

1. Export your ChatGPT conversations.
2. Run the Builder — it produces a structured knowledge base and a SQLite
   database, no third-party packages required.
3. Serve it with the Dashboard — a FastAPI app that layers Project
   Intelligence, the Advisor, and the Knowledge Graph on top, with a
   Command Center UI over all of it.
4. Open the app and see: what's healthy, what's blocked, what to do next,
   and how everything connects — without manually curating any of it.

## Non-negotiable constraints on the vision

- **No external AI/LLM API is called anywhere in the system.** Every
  extractor, health signal, Advisor rule, and Graph relationship is
  rule-based and deterministic, not model-based. This is a product
  decision, not a temporary limitation — see [[06_DEVELOPMENT_RULES]] for
  the seams that exist for a future AI provider without changing this.
- **No data duplication.** The Advisor and the Knowledge Graph both
  recompute from the existing databases on every read rather than
  maintaining their own copies of Project Intelligence or Builder data.
- **Additive, non-breaking evolution.** Every Epic so far has been layered
  on top of the previous one's API surface without modifying or removing
  it. See [[07_ROADMAP]] for how each Epic built on the last.

## Where to go next

- [[02_PRINCIPLES]] — the design principles that fall out of this vision.
- [[03_ARCHITECTURE]] — how the system is actually built.
- [[07_ROADMAP]] — what's shipped and what's next.
