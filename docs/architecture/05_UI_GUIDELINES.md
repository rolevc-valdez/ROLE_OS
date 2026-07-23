# 05 — UI Guidelines

The **Command Center** (Epic 4) is the current dashboard UI. It is served
at `/` and is a pure presentation layer: no new backend endpoint,
database, or business logic was introduced to build it — every page is
built entirely from the API described in [[03_ARCHITECTURE]].

## Stack

Plain HTML, CSS, and vanilla JavaScript. No frontend framework, no build
step, no CDN dependency. The app shell is `templates/index.html`
(Jinja2), rendered once; a small hash-based client-side router in
`static/js/app.js` swaps pages in and out of one `#view-root` element.

## Structure

- **Persistent shell**: an icon sidebar (Home, Projects, Knowledge,
  Advisor, Graph, Assets, Settings) and a header (global search, workspace
  selector, live date/time, quick actions) stay on screen at all times.
- **Hash routes**: `#/home`, `#/projects`, `#/project/{id}`, `#/knowledge`,
  `#/advisor`, `#/graph`, `#/assets`, `#/settings`. Navigating between them
  never triggers a full page reload or a new server route.

## Design system (`app/static/css/`)

Imported in this order by `style.css` (a 4-line `@import` entry point):

1. `colors.css` — every color as a CSS custom property: dark theme,
   status colors, priority colors, and one color per Knowledge Graph node
   type. No other file hard-codes a hex value.
2. `layout.css` — structural grid only: the app shell (sidebar + header +
   content), page containers, responsive breakpoints.
3. `components.css` — nav items, buttons, inputs, badges, cards, the
   health ring, the search dropdown, the graph detail panel.
4. `animations.css` — subtle transitions only (fade/rise-in on cards and
   sidebar items, a hover lift, health-ring transitions), and honors
   `prefers-reduced-motion`.

**No inline styles** in generated markup, with two narrow, deliberate
exceptions that are inherently per-instance runtime values: a health
ring's live conic-gradient percentage, and a graph node's live type-based
fill color.

When adding a UI feature: put color values in `colors.css`, not inline;
put structural layout in `layout.css`; put a new interactive element's
look in `components.css`; keep animations subtle and gated behind
`prefers-reduced-motion` like the existing ones.

## Pages

| Page | Built from | Notes |
|---|---|---|
| **Home** | `/advisor/recommendations`, `/pi/workspaces`, `/pi/projects`, `/graph`, `/advisor/recommendations`, `/ui/timeline`, `/graph/search` | Today's Focus, Workspace Overview, animated Health Dashboard, Recent Activity, Knowledge Graph Preview, grouped Quick Search |
| **Project** | `/pi/projects/{id}` (full detail incl. collections), Advisor + Graph endpoints | Three-column layout: left (health/status/priority/advisor summary), center (overview/notes/decisions/todos/deliverables), right (capabilities/dependencies/related projects/advisor/graph preview) |
| **Graph** | `/graph`, `/graph/neighbors/{id}`, `/graph/impact/{id}`, `/graph/search` | Full-screen; zoom (wheel) + pan (drag) via SVG viewport transform; shares `createGraphView()` with the Home and Project previews |
| **Advisor** | `/advisor/daily-brief`, `/advisor/recommendations` | Daily Brief at top, recommendation cards grouped by workspace |
| **Assets** | `/graph?node_type=Asset` | Lists every Asset graph node |
| **Settings** | `/health` | Read-only system status |

## The `createGraphView()` factory

The graph rendering code (SVG layout, click/expand/collapse, search,
filters, highlight modes, zoom/pan) lives in one reusable factory in
`app.js`, shared by the Home preview, the Project page preview, and the
full Graph page. **Any new graph interaction or bug fix belongs here**,
not duplicated per-view — that duplication is exactly what this factory
exists to prevent.

## Performance rule: no N+1 from the UI

The Home page and project lists read each project's already-persisted
`health_score` field from `/pi/projects` rather than calling
`/pi/projects/{id}/health` once per project. The Graph page only fetches
graph data when the user navigates to it or expands/searches within it.
When adding a list or overview view, follow this pattern: fetch a
collection once, read fields already present on it, and avoid a
per-item follow-up request.

## Adding a page or view

1. Confirm the data you need is already served by an existing endpoint
   (`/pi/*`, `/advisor/*`, `/graph/*`, `/ui/*`). If it isn't, that's a
   backend change, not a UI one — see [[06_DEVELOPMENT_RULES]].
2. Add a route in the hash router and a render function in `app.js`.
3. Reuse `createGraphView()` if the view shows a graph in any form.
4. Style with the existing four CSS files; don't introduce a new stylesheet
   or inline colors.
5. Add a UI test under `dashboard/tests/test_ui.py` confirming the new
   markup is served and that it calls only pre-existing API endpoints.

## Where to go next

- [[03_ARCHITECTURE]] — the API surface every page is built from.
- [[06_DEVELOPMENT_RULES]] — testing and PR expectations for UI changes.
