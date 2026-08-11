"use strict";

/*
 * ROLE OS Command Center (Epic 4)
 *
 * A single-page app shell: persistent sidebar + header, with a small
 * hash-based router swapping "pages" in and out of #view-root. This file
 * is UI-only -- every function below just calls the existing, unmodified
 * REST API (Milestone 1's knowledge API, Epic 1's /pi/*, Epic 2's
 * /advisor/*, and Epic 3's /graph/*). No new backend endpoint is
 * introduced or assumed anywhere in this file.
 */

(function () {
  const viewRoot = document.getElementById("view-root");
  if (!viewRoot) return; // template not present (shouldn't happen)

  const detailOverlay = document.getElementById("detail-overlay");
  const detailBody = document.getElementById("detail-body");
  const detailClose = document.getElementById("detail-close");

  // ---------------------------------------------------------------------
  // Small shared helpers
  // ---------------------------------------------------------------------

  async function fetchJSON(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const body = await resp.json();
        detail = body.detail || detail;
      } catch (_) {
        /* ignore */
      }
      const error = new Error(detail);
      error.status = resp.status;
      throw error;
    }
    if (resp.status === 204) return null;
    return resp.json();
  }

  function postJSON(url, payload, method = "POST") {
    return fetchJSON(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  // ===========================================================================
  // Centralized null-safe formatters -- the single place that decides what a
  // missing/undefined/null value looks like when rendered, instead of each
  // renderer inventing its own ad hoc `?? ""` / `|| ""` fallback (which is how
  // `a.summary.replace(...)` on Home's Recent Assets card ended up calling a
  // string method on `undefined`: the fallback was simply missing there).
  // Every renderer that touches a possibly-partial discovered/adopted project
  // object (Home portfolio, Discovered Project Detail, Advisor, Projects page)
  // should route display values through these rather than reaching for the
  // raw field directly.
  // ===========================================================================
  function fmtText(value) {
    if (value === null || value === undefined || value === "") return "Not yet defined";
    return String(value);
  }

  function fmtDate(value) {
    if (value === null || value === undefined || value === "") return "Unknown";
    return String(value);
  }

  function safeArr(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeObj(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function debounce(fn, wait) {
    let t = null;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  // Sprint C1B (Rewiring): these thresholds must match
  // `app.project_context.health.HEALTHY_THRESHOLD`/`WARNING_THRESHOLD`
  // exactly -- Sprint C1 left this function using 70/40 while the backend
  // used 80/50, so a score of 75 was "healthy" via the API and "warning"
  // here. Every call site that already has a `project_context` embedded
  // (Cockpit, Workspace/Projects rows, Advisor, Home) should pass its
  // `.health` tier as `tierOverride` instead of relying on this
  // recomputing one from the raw score -- this function only computes a
  // tier itself as a fallback for the few payloads that don't carry one
  // yet (kept in sync with the backend rather than removed, since forcing
  // every legacy call site to plumb a tier through was out of scope for
  // this sprint).
  function healthTier(score) {
    if (score >= 80) return "healthy";
    if (score >= 50) return "warning";
    return "critical";
  }

  function healthColorVar(score, tierOverride) {
    const tier = tierOverride || healthTier(score);
    return tier === "healthy" ? "var(--status-healthy)" : tier === "warning" ? "var(--status-warning)" : "var(--status-critical)";
  }

  function healthRingHtml(score, size, tierOverride) {
    const cls = size === "sm" ? "health-ring health-ring-sm" : "health-ring";
    const style = `--ring-value:${Math.max(0, Math.min(100, score))}; --ring-color:${healthColorVar(score, tierOverride)};`;
    return `<div class="${cls}" style="${style}"><span class="health-ring-value">${score}</span></div>`;
  }

  function priorityBadge(priority) {
    const p = (priority || "medium").toLowerCase();
    return `<span class="badge badge-priority-${escapeHtml(p)}">${escapeHtml(p)}</span>`;
  }

  // Generic presentation-only badge helper (Sprint C1B §3): every status/
  // tier badge in this file now funnels its HTML through this one
  // function -- the *values* (which tier, which variant) must still come
  // from the backend; this only ever turns "healthy"/"active"/etc. into
  // markup.
  function badgeHtml(label, variant) {
    const cls = variant ? `badge badge-${variant}` : "badge";
    return `<span class="${cls}">${escapeHtml(label)}</span>`;
  }

  function healthBadge(score, tierOverride) {
    const tier = tierOverride || healthTier(score);
    return badgeHtml(tier, tier);
  }

  function formatDateTime(date) {
    return date.toLocaleString(undefined, {
      weekday: "short", year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function animateCount(el, target) {
    const duration = 500;
    const start = performance.now();
    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      el.textContent = Math.round(target * progress);
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // ---------------------------------------------------------------------
  // Router
  // ---------------------------------------------------------------------

  const routes = {
    // Sprint C5: Mission Control is now the primary Home experience (the
    // decision-and-continuation screen); Dashboard remains the deeper
    // executive analytics view (see docs/product/DECISIONS.md). The old
    // Home ("Command Center") render function is kept below for the pages
    // that still link into its sub-sections, but no nav item/route points
    // at it anymore.
    home: renderMissionControlPage,
    "mission-control": renderMissionControlPage,
    dashboard: renderDashboardPage,
    session: renderSessionPage,
    cockpit: renderCockpitPage,
    projects: renderProjectsList,
    project: renderProjectDetail,
    dproject: renderDiscoveredProjectDetail,
    workspace: renderWorkspacePage,
    knowledge: renderKnowledge,
    explorer: renderExplorerPage,
    phub: renderProjectHubPage,
    advisor: renderAdvisorPage,
    graph: renderGraphPage,
    "conversation-graph": renderConversationGraphPage,
    assets: renderAssetsPage,
    settings: renderSettingsPage,
  };

  function parseHash() {
    const raw = (window.location.hash || "").replace(/^#\/?/, "");
    const [view, param] = raw.split("/").filter(Boolean);
    return { view: view || "home", param };
  }

  function navigate(view, param) {
    window.location.hash = param ? `#/${view}/${encodeURIComponent(param)}` : `#/${view}`;
  }

  function updateActiveNav(view) {
    document.querySelectorAll(".nav-item[data-nav]").forEach((el) => {
      el.classList.toggle("active", el.dataset.nav === view);
    });
  }

  async function route() {
    const { view, param } = parseHash();
    updateActiveNav(view);
    const renderFn = routes[view] || renderMissionControlPage;
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading...</p>';
    try {
      await renderFn(param);
    } catch (err) {
      viewRoot.innerHTML = `<p class="error-box">Something went wrong: ${escapeHtml(err.message)}</p>`;
    }
  }

  window.addEventListener("hashchange", route);

  document.querySelectorAll("[data-nav]").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.nav));
  });

  // Event delegation for links rendered into view content.
  viewRoot.addEventListener("click", (e) => {
    // Unlike the sidebar's [data-nav] items (listeners attached once, at
    // boot, directly on those fixed elements), content rendered into
    // #view-root is replaced on every navigation, so [data-nav] elements
    // inside it (e.g. a discovered-project card linking to the Workspace
    // page) are handled here via delegation instead.
    const navLink = e.target.closest("[data-nav]");
    if (navLink) {
      e.preventDefault();
      navigate(navLink.dataset.nav, navLink.dataset.navParam);
      return;
    }
    const projectLink = e.target.closest("[data-open-project]");
    if (projectLink) {
      e.preventDefault();
      navigate("project", projectLink.dataset.openProject);
      return;
    }
    const cardLink = e.target.closest("[data-open-card]");
    if (cardLink) {
      e.preventDefault();
      openCardDetail(cardLink.dataset.openCard);
      return;
    }
    const cockpitLink = e.target.closest("[data-open-cockpit]");
    if (cockpitLink) {
      e.preventDefault();
      navigate("cockpit", cockpitLink.dataset.openCockpit);
    }
  });

  // ---------------------------------------------------------------------
  // Header: workspace selector + live clock + global search
  // ---------------------------------------------------------------------

  const workspaceSelect = document.getElementById("header-workspace-select");
  const datetimeEl = document.getElementById("header-datetime");
  const searchInput = document.getElementById("global-search-input");
  const searchResults = document.getElementById("global-search-results");

  let workspacesCache = null;

  async function loadHeaderWorkspaces() {
    try {
      const workspaces = await fetchJSON("/pi/workspaces");
      workspacesCache = workspaces;
      const current = workspaceSelect.value;
      workspaceSelect.innerHTML =
        '<option value="">All workspaces</option>' +
        workspaces.map((w) => `<option value="${escapeHtml(w.name)}">${escapeHtml(w.name)}</option>`).join("");
      workspaceSelect.value = current;
    } catch (err) {
      console.error("Could not load workspaces", err);
    }
  }

  workspaceSelect.addEventListener("change", () => {
    const { view } = parseHash();
    if (view === "home" || view === "mission-control") renderMissionControlPage();
  });

  function tickClock() {
    datetimeEl.textContent = formatDateTime(new Date());
  }
  setInterval(tickClock, 1000 * 30);

  const GROUPED_SEARCH_TYPES = ["Project", "KnowledgeCard", "Person", "Application", "Vendor", "Asset"];

  function groupSearchResults(nodes) {
    const groups = {};
    GROUPED_SEARCH_TYPES.forEach((t) => (groups[t] = []));
    nodes.forEach((n) => {
      if (groups[n.type]) groups[n.type].push(n);
    });
    return groups;
  }

  function searchResultsHtml(groups) {
    const labels = {
      Project: "Projects", KnowledgeCard: "Knowledge Cards", Person: "People",
      Application: "Applications", Vendor: "Vendors", Asset: "Assets",
    };
    let any = false;
    const html = GROUPED_SEARCH_TYPES.map((type) => {
      const items = groups[type];
      if (!items.length) return "";
      any = true;
      const rows = items
        .slice(0, 8)
        .map(
          (n) =>
            `<div class="search-result-item" data-node-id="${escapeHtml(n.id)}" data-node-type="${escapeHtml(n.type)}"><span>${escapeHtml(n.label)}</span><span class="badge">${escapeHtml(type)}</span></div>`
        )
        .join("");
      return `<div class="search-results-group"><h4>${labels[type]}</h4>${rows}</div>`;
    }).join("");
    return any ? html : '<div class="search-results-group muted">No matches</div>';
  }

  function bindSearchResultClicks(container) {
    container.querySelectorAll("[data-node-id]").forEach((el) => {
      el.addEventListener("click", () => {
        const type = el.dataset.nodeType;
        const id = el.dataset.nodeId;
        if (type === "Project") {
          navigate("project", id.replace(/^project:/, ""));
        } else if (type === "KnowledgeCard") {
          openCardDetail(id.replace(/^knowledgecard:/, ""));
        } else {
          pendingGraphFocus = id;
          navigate("graph");
        }
      });
    });
  }

  const runGlobalSearch = debounce(async (q) => {
    if (!q) {
      searchResults.hidden = true;
      return;
    }
    try {
      const nodes = await fetchJSON(`/graph/search?q=${encodeURIComponent(q)}&limit=60`);
      const groups = groupSearchResults(nodes);
      searchResults.innerHTML = searchResultsHtml(groups);
      searchResults.hidden = false;
      bindSearchResultClicks(searchResults);
    } catch (err) {
      searchResults.innerHTML = `<div class="search-results-group error-box">${escapeHtml(err.message)}</div>`;
      searchResults.hidden = false;
    }
  }, 250);

  searchInput.addEventListener("input", () => runGlobalSearch(searchInput.value.trim()));
  // Sprint C3: the header search bar opens Explorer's universal search
  // results directly on Enter -- Explorer is "the Google of ROLE OS," so
  // pressing Enter here should behave like pressing Enter in any search
  // engine's own box, not stay confined to this small dropdown.
  searchInput.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const q = searchInput.value.trim();
    if (!q) return;
    searchResults.hidden = true;
    navigate("explorer", q);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".header-search")) searchResults.hidden = true;
  });

  // ---------------------------------------------------------------------
  // Knowledge card detail overlay (ported from Milestone 2)
  // ---------------------------------------------------------------------

  async function openCardDetail(conversationId) {
    detailOverlay.hidden = false;
    detailBody.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const card = await fetchJSON(`/knowledge/${encodeURIComponent(conversationId)}`);
      detailBody.innerHTML = cardDetailHtml(card);
    } catch (err) {
      detailBody.innerHTML = `<p class="error-box">Could not load card: ${escapeHtml(err.message)}</p>`;
    }
  }

  function listOrNone(items) {
    if (!items || !items.length) return '<p class="muted">None recorded</p>';
    return `<ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`;
  }

  function cardDetailHtml(card) {
    return `
      <h2 id="detail-title">${escapeHtml(card.title)}</h2>
      <p class="card-muted">${escapeHtml(card.project)} &middot; ${escapeHtml(card.category)} &middot; ${escapeHtml(card.status)}</p>
      <p>${escapeHtml(card.summary)}</p>
      <h4>Decisions</h4>${listOrNone(card.decisions)}
      <h4>Deliverables</h4>${listOrNone(card.deliverables)}
      <h4>To-dos</h4>${listOrNone(card.todos)}
      <h4>People</h4>${listOrNone(card.people)}
      <h4>Applications</h4>${listOrNone(card.applications)}
      <h4>Tags</h4>${listOrNone(card.tags)}
    `;
  }

  detailClose.addEventListener("click", () => {
    detailOverlay.hidden = true;
  });
  detailOverlay.addEventListener("click", (e) => {
    if (e.target === detailOverlay) detailOverlay.hidden = true;
  });

  // =======================================================================
  // HOME (Command Center)
  // =======================================================================

  async function renderHome() {
    viewRoot.innerHTML = `
      <div class="page-section">
        <div class="section-heading"><h2>Your Projects</h2><button type="button" class="link-btn" data-nav="workspace">Open Workspace &rarr;</button></div>
        <div id="home-portfolio" class="card-grid-wide"><p class="muted loading-pulse">Loading real project data…</p></div>
      </div>

      <div class="page-section">
        <div class="section-heading"><h2>Today's Focus</h2></div>
        <div id="home-focus" class="card-grid-wide"><p class="muted loading-pulse">Loading recommendations…</p></div>
      </div>

      <div class="home-grid">
        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Workspace Overview</h2></div>
            <div id="home-workspaces" class="card-grid"><p class="muted loading-pulse">Loading workspaces…</p></div>
          </div>

          <div class="page-section">
            <div class="section-heading"><h2>Health Dashboard</h2></div>
            <div id="home-health-dashboard" class="health-dashboard-grid"></div>
          </div>

          <div class="page-section">
            <div class="section-heading"><h2>Knowledge Graph Preview</h2><button class="link-btn" data-nav="graph">Open full graph &rarr;</button></div>
            <div id="home-graph-preview-wrap"><svg id="home-graph-canvas" viewBox="0 0 640 280"></svg></div>
          </div>
        </div>

        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Recent Activity</h2></div>
            <div id="home-activity"><p class="muted loading-pulse">Loading activity…</p></div>
          </div>

          <div class="page-section card quick-search-box">
            <h3 class="card-title">Quick Search</h3>
            <input id="quick-search-input" type="search" placeholder="Search projects, cards, people, apps, vendors, assets..." />
            <div id="quick-search-results"></div>
          </div>
        </div>
      </div>
    `;

    document.querySelectorAll("#view-root [data-nav]").forEach((el) => {
      el.addEventListener("click", () => navigate(el.dataset.nav));
    });

    const workspaceFilter = workspaceSelect.value;

    const [recs, workspaces, projects, graphFull, timeline] = await Promise.all([
      fetchJSON(`/advisor/recommendations${workspaceFilter ? `?workspace=${encodeURIComponent(workspaceFilter)}` : ""}`),
      fetchJSON("/pi/workspaces"),
      fetchJSON("/pi/projects"),
      fetchJSON("/graph"),
      fetchJSON("/ui/timeline?limit=8").catch(() => []),
    ]);

    renderTodaysFocus(recs.slice(0, 3), projects);
    renderWorkspaceOverview(workspaces, projects);
    renderHealthDashboard(projects, graphFull, recs);
    renderRecentActivity(projects, timeline);
    renderHomeGraphPreview(graphFull);
    setupQuickSearch();
    renderHomePortfolio();
  }

  // =======================================================================
  // HOME PORTFOLIO (Sprint 4 §4): real discovered/adopted project signals,
  // additive to Home's existing Project-Intelligence-pipeline sections
  // above -- fetched separately so a Workspace-domain hiccup can never
  // break the rest of Home.
  // =======================================================================

  function homeProjectMiniCardHtml(label, project, extra) {
    const p = safeObj(project);
    if (!project || !p.id) {
      return `<div class="card"><p class="card-muted">${escapeHtml(label)}</p><p class="muted">Not yet defined</p></div>`;
    }
    return `
      <div class="card u-clickable" data-nav="dproject" data-nav-param="${escapeHtml(p.id)}">
        <p class="card-muted">${escapeHtml(label)}</p>
        <p class="card-title">${escapeHtml(fmtText(p.name))}</p>
        ${extra || ""}
      </div>`;
  }

  async function renderHomePortfolio() {
    const el = document.getElementById("home-portfolio");
    if (!el) return;
    try {
      const home = await fetchJSON("/workspace/home");
      if (!home.total_projects) {
        el.innerHTML = `
          <div class="card">
            <p class="card-muted">No adopted projects yet.</p>
            <button type="button" class="btn btn-sm btn-primary" data-nav="workspace">Open Workspace to adopt one &rarr;</button>
          </div>`;
        return;
      }

      const attention = safeArr(home.projects_needing_attention)
        .map((r) => {
          const rec = safeObj(r);
          return `<li><a href="${escapeHtml(rec.action_link || "#")}" data-inapp-link>${escapeHtml(fmtText(rec.project))}</a>: ${escapeHtml(fmtText(rec.recommendation))}</li>`;
        })
        .join("") || "<li class=\"muted\">Nothing needs attention right now.</li>";

      const commits = safeArr(home.recent_commits)
        .map((c) => {
          const commit = safeObj(c);
          return `<li>${escapeHtml(fmtText(commit.project_name))}: ${escapeHtml(fmtText(commit.summary))}</li>`;
        })
        .join("") || "<li class=\"muted\">None yet.</li>";

      const assets = safeArr(home.recent_assets)
        .map((a) => {
          const asset = safeObj(a);
          return `<li>${escapeHtml(fmtText(asset.project))}: ${escapeHtml(fmtText(asset.filename))}</li>`;
        })
        .join("") || "<li class=\"muted\">None yet.</li>";

      // Sprint 5 §4: Quick Resume always resolves to the canonical
      // Project Identity -- clicking it triggers Resume Work directly
      // (locate/start the AI Session, copy the prompt, open the
      // assistant, land on Cockpit for the resolved canonical project),
      // it does not just navigate to a detail page.
      const qr = safeObj(home.quick_resume);
      // Sprint C1B: `action_text`/`resume_state` are now sourced from the
      // canonical `ProjectContext` (see `routers/workspace.py::get_home_
      // portfolio`), not computed ad hoc in `portfolio.build_home_
      // portfolio`. The button disables itself when the canonical resume
      // orchestration says resuming isn't available yet.
      const qrResumeAvailable = !qr.resume_state || qr.resume_state.available !== false;
      const quickResume = home.quick_resume
        ? `<div class="card">
             <p class="card-muted">Quick Resume</p>
             <p class="card-title">${escapeHtml(fmtText(qr.project_name))}</p>
             <p class="u-mt-1">${escapeHtml(fmtText(qr.action_text))}</p>
             <button type="button" class="btn btn-sm btn-primary u-mt-2" data-resume-work-item="${escapeHtml(qr.item_id || "")}" ${qrResumeAvailable ? "" : "disabled"}>Resume Work &rarr;</button>
           </div>`
        : `<div class="card"><p class="card-muted">Quick Resume</p><p class="muted">Not yet defined</p></div>`;

      const session = safeObj(home.latest_ai_session);
      const latestSessionText = home.latest_ai_session
        ? fmtText(session.title || session.assistant)
        : "Not yet defined";

      el.innerHTML = `
        ${homeProjectMiniCardHtml("Last Active Project", home.last_active_project)}
        ${homeProjectMiniCardHtml("Most Recently Modified", home.most_recently_modified_project)}
        ${quickResume}
        <div class="card">
          <p class="card-muted">Projects Needing Attention</p>
          <ul class="u-mt-1">${attention}</ul>
        </div>
        <div class="card">
          <p class="card-muted">Recent Commits</p>
          <ul class="u-mt-1">${commits}</ul>
        </div>
        <div class="card">
          <p class="card-muted">Recent Assets</p>
          <ul class="u-mt-1">${assets}</ul>
        </div>
        <div class="card">
          <p class="card-muted">Latest AI Session</p>
          <p class="${home.latest_ai_session ? "" : "muted"}">${escapeHtml(latestSessionText)}</p>
        </div>`;
      el.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
        btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
      });
    } catch (err) {
      el.innerHTML = `<p class="error-box">Could not load portfolio data: ${escapeHtml(err.message)}</p>`;
    }
  }

  function renderTodaysFocus(recs, projects) {
    const el = document.getElementById("home-focus");
    if (!recs.length) {
      el.innerHTML = '<p class="muted">Nothing needs attention right now.</p>';
      return;
    }
    const byId = Object.fromEntries(projects.map((p) => [p.id, p]));
    el.innerHTML = recs
      .map((rec) => {
        const project = byId[rec.project_id];
        const name = project ? project.name : rec.project_id;
        const score = project ? project.health_score : 0;
        const priority = project ? project.priority : "medium";
        // Sprint C1B: `/pi/projects` now embeds `project_context`; render
        // its tier rather than recomputing one from the raw score.
        const tier = project && project.project_context ? project.project_context.health : null;
        return `
        <div class="card rec-card">
          <div class="rec-card-header">
            <div>
              <p class="rec-card-title">${escapeHtml(name)}</p>
              <div class="rec-card-meta">
                ${healthBadge(score, tier)}
                ${priorityBadge(priority)}
                <span class="badge">Effort: ${escapeHtml(rec.estimated_effort)}</span>
              </div>
            </div>
            ${healthRingHtml(score, "sm", tier)}
          </div>
          <div class="rec-card-body">
            <p><strong>${escapeHtml(rec.title)}</strong></p>
            <p>${escapeHtml(rec.summary)}</p>
            <p><strong>Suggested action:</strong> ${escapeHtml(rec.suggested_action)}</p>
            <p><strong>Expected impact:</strong> ${escapeHtml(rec.impact)}</p>
          </div>
          <div class="rec-card-actions">
            <button type="button" class="btn btn-primary btn-sm" data-open-project="${escapeHtml(rec.project_id)}">Open Project</button>
          </div>
        </div>`;
      })
      .join("");
  }

  function renderWorkspaceOverview(workspaces, projects) {
    const el = document.getElementById("home-workspaces");
    el.innerHTML = workspaces
      .map((ws) => {
        const wsProjects = projects.filter((p) => p.workspace === ws.name);
        // Sprint C1B: prefer the embedded `project_context.health` tier;
        // fall back to computing one only if it's missing.
        const tierOf = (p) => (p.project_context && p.project_context.health) || healthTier(p.health_score);
        const healthy = wsProjects.filter((p) => tierOf(p) === "healthy").length;
        const warning = wsProjects.filter((p) => tierOf(p) === "warning").length;
        const critical = wsProjects.filter((p) => tierOf(p) === "critical").length;
        return `
        <div class="card workspace-card">
          <p class="card-title">${escapeHtml(ws.name)}</p>
          <p class="card-muted">${wsProjects.length} project${wsProjects.length === 1 ? "" : "s"}</p>
          <div class="workspace-card-counts">
            <div class="count-pill badge-healthy"><strong>${healthy}</strong>Healthy</div>
            <div class="count-pill badge-warning"><strong>${warning}</strong>Warning</div>
            <div class="count-pill badge-critical"><strong>${critical}</strong>Critical</div>
          </div>
        </div>`;
      })
      .join("");
  }

  function renderHealthDashboard(projects, graphFull, recs) {
    const el = document.getElementById("home-health-dashboard");
    const knowledgeCardCount = graphFull.nodes.filter((n) => n.type === "KnowledgeCard").length;
    const indicators = [
      { label: "Projects", value: projects.length },
      { label: "Knowledge Cards", value: knowledgeCardCount },
      { label: "Advisor Recommendations", value: recs.length },
      { label: "Graph Nodes", value: graphFull.nodes.length },
      { label: "Graph Relationships", value: graphFull.edges.length },
    ];
    el.innerHTML = indicators
      .map(
        (ind, i) => `
      <div class="card u-text-center">
        <div class="card-muted u-fs-12 u-mb-2">${escapeHtml(ind.label)}</div>
        <div id="health-indicator-${i}" class="u-fs-26">0</div>
      </div>`
      )
      .join("");
    indicators.forEach((ind, i) => animateCount(document.getElementById(`health-indicator-${i}`), ind.value));
  }

  function renderRecentActivity(projects, timeline) {
    const el = document.getElementById("home-activity");
    const decisions = [];
    const deliverables = [];
    projects.forEach((p) => {
      (p.decisions || []).forEach((d) => decisions.push({ ...d, project: p.name, project_id: p.id }));
      (p.deliverables || []).forEach((d) => deliverables.push({ ...d, project: p.name, project_id: p.id }));
    });
    decisions.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    deliverables.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));

    function section(title, items, renderItem) {
      const body = items.length
        ? `<ul class="activity-list">${items.slice(0, 5).map(renderItem).join("")}</ul>`
        : '<p class="muted">None yet</p>';
      return `<div class="card u-mb-3"><p class="card-title">${title}</p>${body}</div>`;
    }

    el.innerHTML =
      section("Timeline", timeline, (t) => `<li data-open-card="${escapeHtml(t.conversation_id)}" class="u-clickable">${escapeHtml(t.title)} <span class="card-muted">— ${escapeHtml(t.project)}</span></li>`) +
      section("Recent Decisions", decisions, (d) => `<li>${escapeHtml(d.text || "(untitled)")} <span class="card-muted">— ${escapeHtml(d.project)}</span></li>`) +
      section("Recent Deliverables", deliverables, (d) => `<li>${escapeHtml(d.text || d.name || "(untitled)")} <span class="card-muted">— ${escapeHtml(d.project)}</span></li>`) +
      section("Recent Conversations", timeline, (t) => `<li data-open-card="${escapeHtml(t.conversation_id)}" class="u-clickable">${escapeHtml(t.title)}</li>`);
  }

  function renderHomeGraphPreview(graphFull) {
    const svg = document.getElementById("home-graph-canvas");
    const projectNodes = graphFull.nodes.filter((n) => n.type === "Project").slice(0, 14);
    const ids = new Set(projectNodes.map((n) => n.id));
    const edges = graphFull.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const view = createGraphView(svg, { width: 640, height: 280, interactive: false });
    view.setNodes(projectNodes, edges);
    document.getElementById("home-graph-preview-wrap").addEventListener("click", () => navigate("graph"));
    document.getElementById("home-graph-preview-wrap").style.cursor = "pointer";
  }

  function setupQuickSearch() {
    const input = document.getElementById("quick-search-input");
    const results = document.getElementById("quick-search-results");
    const run = debounce(async (q) => {
      if (!q) {
        results.innerHTML = "";
        return;
      }
      try {
        const nodes = await fetchJSON(`/graph/search?q=${encodeURIComponent(q)}&limit=60`);
        results.innerHTML = searchResultsHtml(groupSearchResults(nodes));
        bindSearchResultClicks(results);
      } catch (err) {
        results.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
      }
    }, 250);
    input.addEventListener("input", () => run(input.value.trim()));
  }

  // =======================================================================
  // DASHBOARD 2.0 (Sprint C2) -- the executive dashboard. Replaces the
  // legacy Dashboard (which showed `/import/metrics`, Explorer's own
  // extracted-knowledge-object counts -- honestly zero whenever no ChatGPT
  // conversations had been imported, even though the real workspace
  // already has adopted projects/commits/sessions). Everything below is
  // presentation-only: it reads already-shaped fields off `GET /dashboard/
  // summary` (health tier, next_action, resume_state, recommendation
  // priority are all computed server-side by `ProjectContext`/`workspace.
  // advisor`/`workspace.portfolio`) and renders them -- no client-side
  // recalculation of any of those values.
  // =======================================================================

  function dashProjectRef(ref) {
    if (!ref) return "";
    return ref.item_id
      ? `data-nav="dproject" data-nav-param="${escapeHtml(ref.item_id)}"`
      : `data-nav="project" data-nav-param="${escapeHtml(ref.id)}"`;
  }

  function dashCardsHtml(cards) {
    return [
      { label: "Adopted Projects", value: cards.adopted_projects },
      { label: "Healthy", value: cards.healthy_projects, cls: "badge-healthy" },
      { label: "Needs Attention", value: cards.projects_needing_attention, cls: "badge-warning" },
      { label: "Dirty Repositories", value: cards.dirty_repositories, cls: "badge-warning" },
      { label: "With Next Action", value: cards.projects_with_next_action },
      { label: "Active AI Sessions", value: cards.active_ai_sessions },
      { label: "Recent Snapshots", value: cards.recent_snapshots },
      { label: "Reusable Assets", value: cards.reusable_assets },
      { label: "Knowledge Cards", value: cards.knowledge_cards },
      { label: "Recent Commits", value: cards.recent_commits },
    ];
  }

  function renderDashCards(cards) {
    const el = document.getElementById("dash-cards");
    const indicators = dashCardsHtml(cards);
    el.innerHTML = indicators
      .map(
        (ind, i) => `
      <div class="card u-text-center">
        <div class="card-muted u-fs-12 u-mb-2">${escapeHtml(ind.label)}</div>
        <div id="dash-card-${i}" class="u-fs-26 ${ind.cls || ""}">0</div>
      </div>`
      )
      .join("");
    indicators.forEach((ind, i) => animateCount(document.getElementById(`dash-card-${i}`), ind.value || 0));
  }

  function renderDashPortfolioStatus(status) {
    const el = document.getElementById("dash-portfolio-status");
    const groups = [
      { key: "healthy", label: "Healthy", cls: "badge-healthy" },
      { key: "critical", label: "Critical", cls: "badge-critical" },
      { key: "warning", label: "Warning", cls: "badge-warning" },
      { key: "active", label: "Active", cls: "badge-info" },
      { key: "inactive", label: "Inactive", cls: "" },
      { key: "launch_ready", label: "Launch-ready", cls: "badge-healthy" },
    ];
    el.innerHTML = groups
      .map((g) => {
        const items = status[g.key] || [];
        return `
        <div class="card">
          <div class="u-flex-between">
            <p class="card-muted">${escapeHtml(g.label)}</p>
            <span class="badge ${g.cls}">${items.length}</span>
          </div>
          ${
            items.length
              ? `<ul class="u-mt-1">${items
                  .slice(0, 6)
                  .map((p) => `<li class="u-clickable" ${dashProjectRef(p)}>${escapeHtml(p.display_name)}</li>`)
                  .join("")}</ul>`
              : '<p class="muted u-fs-12">None</p>'
          }
        </div>`;
      })
      .join("");
  }

  function renderDashContinueWork(continueWork) {
    const el = document.getElementById("dash-continue-work");
    if (!continueWork || !continueWork.project_context) {
      el.innerHTML = '<div class="card"><p class="muted">Not yet defined -- no project has an open next action yet.</p></div>';
      return;
    }
    const ctx = continueWork.project_context;
    const na = ctx.next_action || {};
    const snapshot = ctx.latest_snapshot;
    const reasons = continueWork.reasons || [];
    const resumeAvailable = ctx.resume_state && ctx.resume_state.available;
    el.innerHTML = `
      <div class="card">
        <div class="u-flex-between">
          <p class="card-title u-clickable" ${dashProjectRef({ item_id: ctx.item_id, id: ctx.id, display_name: ctx.display_name })}>${escapeHtml(ctx.display_name)}</p>
          ${ctx.health ? healthBadge(ctx.health_score, ctx.health) : ""}
        </div>
        <p class="card-muted u-mt-1">Next Action</p>
        <p>${escapeHtml(na.text || NOT_YET_DEFINED)}</p>
        <p class="card-muted u-mt-2">Last Activity</p>
        <p>${formatDate(ctx.latest_activity)}</p>
        <p class="card-muted u-mt-2">Latest Snapshot</p>
        <p>${snapshot ? escapeHtml(snapshot.summary || snapshot.accomplishments || "") : NOT_YET_DEFINED}</p>
        ${
          reasons.length
            ? `<p class="card-muted u-mt-2">Why this project</p><ul class="u-fs-12">${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>`
            : ""
        }
        <button type="button" class="btn btn-primary btn-sm u-mt-3" data-resume-work-item="${escapeHtml(ctx.item_id || "")}" ${resumeAvailable ? "" : "disabled"}>Resume Work &rarr;</button>
      </div>`;
    el.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
      if (btn.dataset.resumeWorkItem) btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
    });
  }

  function renderDashNeedsAttention(recs) {
    const el = document.getElementById("dash-needs-attention");
    if (!recs.length) {
      el.innerHTML = '<p class="muted">Nothing needs attention right now.</p>';
      return;
    }
    el.innerHTML = `<ul class="activity-list">${recs
      .slice(0, 10)
      .map(
        (r) => `
        <li>
          <span class="u-clickable" ${dashProjectRef(r.project_context || { item_id: r.item_id })}>${escapeHtml(r.project)}</span>:
          ${escapeHtml(r.recommendation)}
          <span class="card-muted u-fs-12">— ${escapeHtml(r.reason)}</span>
        </li>`
      )
      .join("")}</ul>`;
  }

  function dashActivityIcon(type) {
    const icons = {
      git_commit: "&#9654;",
      ai_session: "&#128172;",
      ai_snapshot: "&#128203;",
      asset_discovered: "&#128247;",
      adopted: "&#9733;",
      filesystem_modified: "&#128221;",
    };
    return icons[type] || "&#8226;";
  }

  function activityListHtml(activity, limit) {
    if (!activity.length) return '<p class="muted">No recent activity yet.</p>';
    return `<ul class="activity-list">${activity
      .slice(0, limit || activity.length)
      .map(
        (e) =>
          `<li><span aria-hidden="true">${dashActivityIcon(e.type)}</span> ${escapeHtml(e.project_name)}: ${escapeHtml(e.summary)} <span class="card-muted u-fs-12">— ${formatDate(e.timestamp)}</span></li>`
      )
      .join("")}</ul>`;
  }

  function renderDashRecentActivity(activity) {
    document.getElementById("dash-recent-activity").innerHTML = activityListHtml(activity, 15);
  }

  function renderDashRecentAssets(assets) {
    const el = document.getElementById("dash-recent-assets");
    if (!assets.length) {
      el.innerHTML = '<p class="muted">No reusable assets detected.</p>';
      return;
    }
    el.innerHTML = `<ul class="activity-list">${assets
      .map(
        (a) =>
          `<li><span class="badge">${escapeHtml(a.category)}</span> ${escapeHtml(a.filename)} <span class="card-muted u-fs-12">— ${escapeHtml(a.project)} · ${formatDate(a.modified_at)}</span></li>`
      )
      .join("")}</ul>`;
  }

  function renderDashRecentKnowledge(knowledge) {
    const el = document.getElementById("dash-recent-knowledge");
    if (!knowledge.total_count) {
      el.innerHTML = '<p class="muted">Knowledge has not been imported yet.</p>';
      return;
    }
    const cards = knowledge.recent_cards || [];
    el.innerHTML = `
      <p class="card-muted u-mb-2">${knowledge.total_count} knowledge card(s) total</p>
      ${
        cards.length
          ? `<ul class="activity-list">${cards
              .map((c) => `<li>${escapeHtml(c.title)} <span class="card-muted u-fs-12">— ${escapeHtml(c.project || "")}</span></li>`)
              .join("")}</ul>`
          : ""
      }`;
  }

  function renderDashFreshnessBanner(freshness) {
    if (!freshness || !freshness.is_stale) return "";
    const age = freshness.hours_since_scan != null ? `${Math.round(freshness.hours_since_scan)}h old` : "no scan recorded yet";
    return `<div class="card u-mb-3"><span class="badge badge-warning">Stale discovery data</span> <span class="card-muted">Workspace scan is ${escapeHtml(age)} — rescan on the Workspace page to refresh.</span></div>`;
  }

  // =======================================================================
  // MISSION CONTROL (Sprint C5): the primary Home experience. One fetch
  // (`GET /mission-control`), already-shaped -- this file only renders it,
  // it never joins, ranks, or dedupes anything itself (§15).
  // =======================================================================

  // Sprint C10: the Executive Decision Engine's "TODAY" card -- the
  // single highest-value recommendation, explained. Renders above
  // Today's Focus; everything else on this page is now supporting
  // information for this one decision, never a competing headline.
  function mcExecutiveDecisionHtml(decision) {
    if (!decision || !decision.recommended_project) {
      return `
        <div class="card mc-primary-card">
          <p class="card-title">No recommendation yet</p>
          <p class="muted u-mt-1">${escapeHtml(decision && decision.reason ? decision.reason : "Adopt a project on the Workspace page first.")}</p>
        </div>`;
    }
    const project = decision.recommended_project;
    const plan = (decision.today_plan || [])[0];
    return `
      <div class="card mc-primary-card">
        <p class="card-muted">TODAY</p>
        <div class="u-flex-between u-mt-1">
          <p class="card-title u-fs-20 u-clickable" ${mcProjectRef(project)}>${escapeHtml(project.display_name)}</p>
          <span class="badge">${decision.decision_score} pts &middot; ${Math.round(decision.confidence * 100)}% confidence</span>
        </div>
        <p class="card-muted u-mt-2">Reason</p>
        <p>${escapeHtml(decision.reason)}</p>
        <p class="card-muted u-mt-2">Expected Benefit</p>
        <p>${escapeHtml(decision.expected_benefit || "Not yet defined")}</p>
        <div class="u-flex-between u-mt-2">
          <div>
            <p class="card-muted">Estimated Effort</p>
            <p>${escapeHtml(decision.estimated_effort || "Not yet defined")}</p>
          </div>
          <div>
            <p class="card-muted">Estimated Duration</p>
            <p>${escapeHtml(decision.estimated_duration || "Not yet defined")}</p>
          </div>
        </div>
        ${
          plan
            ? `<p class="card-muted u-mt-2">Next Action</p>
               <p>${escapeHtml(plan.action)}</p>
               <p class="card-muted u-mt-2">Expected Result</p>
               <p>${escapeHtml(decision.expected_result || "Not yet defined")}</p>
               <p class="card-muted u-mt-2">Dependencies</p>
               <p>${escapeHtml(plan.dependencies_status)}</p>`
            : ""
        }
        <p class="card-muted u-mt-2">Evidence</p>
        <ul class="u-fs-12">${(decision.evidence || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("")}</ul>
      </div>`;
  }

  // Sprint C10: Portfolio Ranking -- every adopted project competing for
  // today's slot, ranked, each with its own top reasons. Below the
  // decision card, above the rest of the (now supporting) operational
  // cards.
  function mcPortfolioRankingHtml(rankedProjects) {
    if (!rankedProjects || !rankedProjects.length) {
      return '<p class="muted">No adopted projects to rank yet.</p>';
    }
    return `<div class="card-grid">${rankedProjects
      .map(
        (rp) => `
      <div class="card">
        <p class="card-title">#${rp.rank} <span class="u-clickable" ${mcProjectRef(rp.project)}>${escapeHtml(rp.project.display_name)}</span></p>
        <p class="card-muted u-mt-1">${rp.decision_score} pts &middot; ${Math.round(rp.confidence * 100)}% confidence</p>
        <ul class="u-fs-12 u-mt-1">${rp.top_reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>
      </div>`
      )
      .join("")}</div>`;
  }

  function mcProjectRef(ref) {
    if (!ref) return "";
    if (ref.item_id) return `data-nav="dproject" data-nav-param="${escapeHtml(ref.item_id)}"`;
    if (ref.canonical_project_id) return `data-nav="project" data-nav-param="${escapeHtml(ref.canonical_project_id)}"`;
    return "";
  }

  function mcPrimaryFocusHtml(focus) {
    if (!focus || !focus.available) {
      const action = focus && focus.best_action;
      return `
        <div class="card">
          <p class="card-title">Nothing to recommend yet</p>
          <p class="muted u-mt-1">${escapeHtml((focus && focus.message) || "Not yet defined")}</p>
          ${
            action && action.action_link
              ? `<button type="button" class="btn btn-sm btn-primary u-mt-3" data-nav="${escapeHtml(action.action_link.replace(/^#\//, "").split("/")[0])}">${escapeHtml(action.label)}</button>`
              : action
                ? `<button type="button" class="btn btn-sm btn-primary u-mt-3" data-mc-action="${escapeHtml(action.action)}">${escapeHtml(action.label)}</button>`
                : ""
          }
        </div>`;
    }
    const ctx = focus.project_context || {};
    const na = ctx.next_action || {};
    const snapshot = ctx.latest_snapshot;
    const session = ctx.latest_ai_session;
    const resumeAvailable = ctx.resume_state && ctx.resume_state.available;
    const reasons = focus.reasons || [];
    return `
      <div class="card mc-primary-card">
        <div class="u-flex-between">
          <div>
            <p class="card-muted">Continue Working On</p>
            <p class="card-title u-fs-20 u-clickable" ${mcProjectRef({ item_id: ctx.item_id, canonical_project_id: ctx.id })}>${escapeHtml(ctx.display_name)}</p>
          </div>
          ${ctx.health ? healthBadge(ctx.health_score, ctx.health) : ""}
        </div>
        <p class="card-muted u-mt-2">Status</p>
        <p>${escapeHtml(fmtText(ctx.status))}</p>
        <p class="card-muted u-mt-2">Next Action</p>
        <p>${escapeHtml(na.text || "Not yet defined")}</p>
        <p class="card-muted u-mt-2">Latest Snapshot</p>
        <p>${snapshot ? escapeHtml(snapshot.summary || snapshot.pending_work || "") : "Not yet defined"}</p>
        <p class="card-muted u-mt-2">Latest AI Session</p>
        <p>${session ? `${escapeHtml(session.title || "(untitled session)")} ${assistantBadge(session.assistant)}` : '<span class="muted">Not yet defined</span>'}</p>
        <p class="card-muted u-mt-2">Last Activity</p>
        <p>${formatDate(ctx.latest_activity)}</p>
        ${
          reasons.length
            ? `<p class="card-muted u-mt-2">Recommended because</p><ul class="u-fs-12">${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>`
            : ""
        }
        <button type="button" class="btn btn-primary u-mt-3" data-resume-work-item="${escapeHtml(ctx.item_id || "")}" ${resumeAvailable ? "" : "disabled"}>Resume Work &rarr;</button>
      </div>`;
  }

  function mcFocusItemCardHtml(item) {
    return `
      <div class="card">
        <p class="card-title u-clickable" ${mcProjectRef(item.project)}>${escapeHtml((item.project && item.project.display_name) || "Unknown project")}</p>
        <p class="u-mt-1">${escapeHtml(item.action)}</p>
        <p class="card-muted u-fs-12 u-mt-1">${escapeHtml(item.reason)}</p>
        ${item.expected_benefit ? `<p class="card-muted u-fs-12 u-mt-1">Benefit: ${escapeHtml(item.expected_benefit)}</p>` : ""}
        <div class="rec-card-meta u-mt-2">
          <span class="badge">priority ${item.priority}</span>
          <span class="badge">${Math.round((item.confidence || 0) * 100)}% confidence</span>
        </div>
      </div>`;
  }

  function mcNeedsAttentionListHtml(items) {
    if (!items.length) return '<p class="muted">Nothing needs attention right now.</p>';
    const variants = { critical: "critical", warning: "warning", info: "info" };
    return `<ul class="activity-list">${items
      .map(
        (i) => `
        <li>
          ${badgeHtml(i.severity, variants[i.severity])}
          ${i.project ? `<span class="u-clickable" ${mcProjectRef(i.project)}>${escapeHtml(i.project.display_name)}</span>:` : "Workspace:"}
          ${escapeHtml(i.suggested_action)}
          <span class="card-muted u-fs-12">— ${escapeHtml(i.reason)}${i.expected_benefit ? ` · ${escapeHtml(i.expected_benefit)}` : ""}</span>
        </li>`
      )
      .join("")}</ul>`;
  }

  function mcSinceLastTimeHtml(since) {
    const label = `<p class="card-muted u-mb-2">${escapeHtml(since.label)}</p>`;
    if (!since.events.length) {
      return label + '<p class="muted">Nothing new since then.</p>';
    }
    return (
      label +
      `<ul class="activity-list">${since.events
        .map(
          (e) =>
            `<li><span aria-hidden="true">${dashActivityIcon(e.type)}</span> ${escapeHtml(e.project_name)}: ${escapeHtml(e.summary)} <span class="card-muted u-fs-12">— ${formatDate(e.timestamp)}</span></li>`
        )
        .join("")}</ul>`
    );
  }

  function mcValueSignalHtml(signal) {
    if (!signal.available) {
      return `<div class="card"><p class="muted">${escapeHtml(signal.message)}</p></div>`;
    }
    return `
      <div class="card">
        <p class="card-title u-clickable" ${mcProjectRef(signal.project)}>${escapeHtml(signal.project.display_name)}</p>
        <p class="u-mt-1">${escapeHtml(signal.reason)}</p>
        <ul class="u-fs-12 u-mt-1">${(signal.evidence || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("")}</ul>
        ${signal.expected_benefit ? `<p class="card-muted u-fs-12 u-mt-1">Benefit: ${escapeHtml(signal.expected_benefit)}</p>` : ""}
      </div>`;
  }

  function mcPortfolioStripHtml(portfolio) {
    if (!portfolio.length) {
      return '<p class="muted">No adopted projects yet.</p>';
    }
    return portfolio
      .map(
        (p) => `
      <div class="card u-clickable" ${mcProjectRef({ item_id: p.item_id, canonical_project_id: p.canonical_project_id })}>
        <div class="u-flex-between">
          <p class="card-title">${escapeHtml(p.display_name)}</p>
          ${p.health ? healthBadge(null, p.health) : ""}
        </div>
        <p class="card-muted u-fs-12">${escapeHtml(fmtText(p.status))} &middot; ${formatDate(p.latest_activity)}</p>
        <div class="rec-card-meta u-mt-1">
          ${p.has_next_action ? badgeHtml("next action", "healthy") : ""}
          ${p.needs_attention ? badgeHtml("needs attention", "warning") : ""}
        </div>
      </div>`
      )
      .join("");
  }

  function mcQuickActionsHtml(actions) {
    return actions
      .map((a) =>
        a.action_link
          ? `<button type="button" class="btn btn-sm" data-nav="${escapeHtml(a.action_link.replace(/^#\//, ""))}">${escapeHtml(a.label)}</button>`
          : `<button type="button" class="btn btn-sm" data-mc-action="${escapeHtml(a.action)}">${escapeHtml(a.label)}</button>`
      )
      .join("");
  }

  function mcDailySessionHtml(daily) {
    if (daily.has_active_session) {
      const s = daily.session;
      return `
        <div class="card">
          <p class="card-muted">Today's Session</p>
          <p class="card-title">${escapeHtml(s.project_name)}</p>
          <p class="card-muted u-mt-1">Mode: ${escapeHtml(s.mode)} &middot; ${badgeHtml(s.status, s.status === "active" ? "healthy" : "")}</p>
          <p class="u-mt-2">${escapeHtml(s.objective)}</p>
          <p class="card-muted u-mt-1">Expected result</p>
          <p>${escapeHtml(s.expected_result)}</p>
          <button type="button" class="btn btn-sm btn-primary u-mt-3" data-mc-action="complete_session" data-mc-session-id="${escapeHtml(s.id)}">End My Day</button>
        </div>`;
    }
    const suggestion = daily.suggestion;
    return `
      <div class="card">
        <p class="card-muted">No session started today</p>
        ${
          suggestion
            ? `<p class="u-mt-1">Suggested project: <strong>${escapeHtml(suggestion.project_name)}</strong></p>
               <p class="card-muted u-fs-12 u-mt-1">${escapeHtml(suggestion.objective)}</p>`
            : '<p class="muted u-mt-1">No project to suggest yet.</p>'
        }
        <button type="button" class="btn btn-sm btn-primary u-mt-3" data-nav="session">Start My Day &rarr;</button>
      </div>`;
  }

  function mcSnapshotContinuityHtml(sc) {
    if (!sc.available) return "";
    if (!sc.has_snapshot) {
      return `<div class="card u-mt-2"><p class="muted">${escapeHtml(sc.message)}</p></div>`;
    }
    return `
      <div class="card u-mt-2">
        <p class="card-muted">Latest Snapshot</p>
        <p>${escapeHtml(sc.summary || "")}</p>
        <p class="card-muted u-fs-12 u-mt-1">Pending: ${escapeHtml(sc.pending_work || "None recorded")}</p>
        <p class="card-muted u-fs-12">${formatDate(sc.timestamp)}</p>
      </div>`;
  }

  async function wireMissionControlActions(data) {
    viewRoot.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
      if (btn.dataset.resumeWorkItem) btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
    });
    viewRoot.querySelectorAll("[data-mc-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const action = btn.dataset.mcAction;
        if (action === "rescan_workspace") {
          btn.disabled = true;
          btn.textContent = "Scanning…";
          try {
            await postJSON("/workspace/rescan", {});
            showToast("Workspace rescanned");
            await renderMissionControlPage();
          } catch (err) {
            showToast(`Rescan failed: ${err.message}`);
            btn.disabled = false;
          }
        } else if (action === "complete_session") {
          navigate("session");
        } else if (action === "start_session") {
          navigate("session");
        } else if (action === "create_snapshot") {
          const focus = data.primary_focus;
          if (focus && focus.available) {
            navigate("cockpit", focus.project_context.id);
          } else {
            navigate("projects");
          }
        } else if (action === "resume_work") {
          const focus = data.primary_focus;
          if (focus && focus.available) triggerResumeWork(focus.project_context.item_id);
        }
      });
    });
  }

  async function renderMissionControlPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Mission Control</h2></div>
      <div id="mc-freshness-banner"></div>
      <div id="mc-executive-decision" class="u-mb-4"><p class="muted loading-pulse">Loading…</p></div>

      <div class="page-section">
        <div class="section-heading"><h2>Portfolio Ranking</h2></div>
        <div id="mc-portfolio-ranking"><p class="muted loading-pulse">Loading…</p></div>
      </div>

      <div id="mc-primary-focus" class="u-mb-4"><p class="muted loading-pulse">Loading…</p></div>

      <div class="page-section">
        <div class="section-heading"><h2>Today's Focus</h2></div>
        <div id="mc-todays-focus" class="card-grid-wide"></div>
      </div>

      <div class="home-grid">
        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Since Last Time</h2></div>
            <div id="mc-since-last-time"></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Needs Attention</h2></div>
            <div id="mc-needs-attention"></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Recent Activity</h2></div>
            <div id="mc-recent-activity"></div>
          </div>
        </div>
        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Daily Session</h2></div>
            <div id="mc-daily-session"></div>
          </div>
          <div class="page-section">
            <div class="section-heading" id="mc-value-signal-heading"><h2>Value Signal</h2></div>
            <div id="mc-value-signal"></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Quick Actions</h2></div>
            <div id="mc-quick-actions" class="mc-quick-actions"></div>
          </div>
        </div>
      </div>

      <div class="page-section">
        <div class="section-heading"><h2>Portfolio</h2><button type="button" class="link-btn" data-nav="workspace">Open Workspace &rarr;</button></div>
        <div id="mc-portfolio" class="card-grid"></div>
      </div>
    `;

    let data;
    try {
      data = await fetchJSON("/mission-control");
    } catch (err) {
      viewRoot.innerHTML = `<p class="error-box">Could not load Mission Control: ${escapeHtml(err.message)}</p>`;
      return;
    }

    document.getElementById("mc-freshness-banner").innerHTML = renderDashFreshnessBanner(data.data_freshness);
    document.getElementById("mc-executive-decision").innerHTML = mcExecutiveDecisionHtml(data.executive_decision);
    document.getElementById("mc-portfolio-ranking").innerHTML = mcPortfolioRankingHtml(data.ranked_projects);
    document.getElementById("mc-primary-focus").innerHTML =
      mcPrimaryFocusHtml(data.primary_focus) + mcSnapshotContinuityHtml(data.snapshot_continuity);
    document.getElementById("mc-todays-focus").innerHTML = data.todays_focus.length
      ? data.todays_focus.map(mcFocusItemCardHtml).join("")
      : '<p class="muted">Nothing needs your attention today.</p>';
    document.getElementById("mc-since-last-time").innerHTML = mcSinceLastTimeHtml(data.since_last_time);
    document.getElementById("mc-needs-attention").innerHTML = mcNeedsAttentionListHtml(data.needs_attention);
    document.getElementById("mc-recent-activity").innerHTML = activityListHtml(data.recent_activity, 15);
    document.getElementById("mc-daily-session").innerHTML = mcDailySessionHtml(data.daily_session);
    document.getElementById("mc-value-signal-heading").innerHTML = `<h2>${escapeHtml(data.value_signal.label)}</h2>`;
    document.getElementById("mc-value-signal").innerHTML = mcValueSignalHtml(data.value_signal);
    document.getElementById("mc-quick-actions").innerHTML = mcQuickActionsHtml(data.quick_actions);
    document.getElementById("mc-portfolio").innerHTML = mcPortfolioStripHtml(data.portfolio);

    await wireMissionControlActions(data);
  }

  async function renderDashboardPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Dashboard</h2></div>
      <div id="dash-freshness-banner"></div>
      <div id="dash-cards" class="health-dashboard-grid u-mb-4"><p class="muted loading-pulse">Loading metrics…</p></div>

      <div class="page-section">
        <div class="section-heading"><h2>Portfolio Status</h2></div>
        <div id="dash-portfolio-status" class="card-grid"><p class="muted loading-pulse">Loading…</p></div>
      </div>

      <div class="home-grid">
        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Continue Work</h2></div>
            <div id="dash-continue-work"><p class="muted loading-pulse">Loading…</p></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Needs Attention</h2></div>
            <div id="dash-needs-attention"><p class="muted loading-pulse">Loading…</p></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Recent Activity</h2></div>
            <div id="dash-recent-activity"><p class="muted loading-pulse">Loading…</p></div>
          </div>
        </div>
        <div>
          <div class="page-section">
            <div class="section-heading"><h2>Recent Assets</h2></div>
            <div id="dash-recent-assets"><p class="muted loading-pulse">Loading…</p></div>
          </div>
          <div class="page-section">
            <div class="section-heading"><h2>Recent Knowledge</h2></div>
            <div id="dash-recent-knowledge"><p class="muted loading-pulse">Loading…</p></div>
          </div>
        </div>
      </div>
    `;

    try {
      const summary = await fetchJSON("/dashboard/summary");
      document.getElementById("dash-freshness-banner").innerHTML = renderDashFreshnessBanner(summary.data_freshness);
      renderDashCards(summary.cards);
      renderDashPortfolioStatus(summary.portfolio_status);
      renderDashContinueWork(summary.continue_work);
      renderDashNeedsAttention(summary.needs_attention);
      renderDashRecentActivity(summary.recent_activity);
      renderDashRecentAssets(summary.recent_assets);
      renderDashRecentKnowledge(summary.recent_knowledge);
    } catch (err) {
      viewRoot.innerHTML = `<p class="error-box">Could not load dashboard: ${escapeHtml(err.message)}</p>`;
    }
  }

  // =======================================================================
  // PROJECTS LIST + FIRST RUN EXPERIENCE
  //
  // Zero projects (checked against the TRUE, unfiltered total -- never
  // the current workspace filter, so a filter that simply matches
  // nothing doesn't get mistaken for a first-run/empty account) replaces
  // this page with a guided onboarding wizard instead of an empty grid.
  // Once at least one project exists, the normal grid is shown with a
  // permanent "+ New Project" button that reveals the same create form
  // inline. Both paths create the project through the existing,
  // unmodified POST /pi/projects, then navigate to the Cockpit for that
  // project, show a success toast, and suggest starting an AI Session.
  // =======================================================================

  function renderCreateProjectFieldsHtml() {
    const workspaceOptions = (workspacesCache || [])
      .map((w) => `<option value="${escapeHtml(w.name)}">${escapeHtml(w.name)}</option>`)
      .join("");
    return `
      <label>Project name<input type="text" name="name" required placeholder="e.g. ROLE Commerce Factory" /></label>
      <div class="field-row u-mt-2">
        <label>Workspace
          <select name="workspace" required>
            ${workspaceOptions || '<option value="Products">Products</option>'}
          </select>
        </label>
        <label>Priority
          <select name="priority">
            <option value="low">Low</option>
            <option value="medium" selected>Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </label>
      </div>
      <label class="u-mt-2">Description (optional)<textarea name="description" rows="2"></textarea></label>`;
  }

  async function handleCreateProjectSubmit(e, statusElId) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const payload = {
      name: (data.get("name") || "").trim(),
      workspace: data.get("workspace"),
      priority: data.get("priority") || "medium",
      description: data.get("description") || "",
    };
    const statusEl = document.getElementById(statusElId);

    if (!payload.name) {
      statusEl.innerHTML = '<p class="error-box">Project name is required.</p>';
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    statusEl.innerHTML = '<p class="muted loading-pulse">Creating project…</p>';
    try {
      const project = await postJSON("/pi/projects", payload);
      showToast("Project created. Let's start your first AI Session!");
      navigate("cockpit", project.id);
    } catch (err) {
      statusEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
      submitBtn.disabled = false;
    }
  }

  function renderFirstRunOnboardingHtml() {
    return `
      <div class="section-heading"><h2>Welcome to ROLE OS</h2></div>
      <div class="card" id="first-run-onboarding">
        <p class="card-title">Create your first Project</p>
        <p class="muted">Projects are how ROLE OS organizes health, AI Sessions, and everything else. Create your first one to get started.</p>
        <form id="first-run-wizard-form">
          ${renderCreateProjectFieldsHtml()}
          <div class="u-mt-3">
            <button type="submit" class="btn btn-sm btn-primary">Create your first Project</button>
          </div>
          <div id="first-run-wizard-status" class="u-mt-2"></div>
        </form>
      </div>`;
  }

  function renderNewProjectFormHtml() {
    return `
      <form id="new-project-form" class="card u-mt-3" hidden>
        <p class="card-title">New Project</p>
        ${renderCreateProjectFieldsHtml()}
        <div class="u-mt-3">
          <button type="submit" class="btn btn-sm btn-primary">Create</button>
          <button type="button" class="btn btn-sm" id="new-project-cancel-btn">Cancel</button>
        </div>
        <div id="new-project-status" class="u-mt-2"></div>
      </form>`;
  }

  function discoveredProjectCardHtml(p) {
    const na = p.next_action || {};
    const git = p.git_is_repo
      ? `${escapeHtml(p.git_branch || "?")}${p.git_is_dirty ? ' <span class="badge badge-warning">dirty</span>' : ' <span class="badge badge-healthy">clean</span>'}`
      : "—";
    const childCounts = [
      p.repository_count ? `${p.repository_count} repo(s)` : "",
      p.component_count ? `${p.component_count} component(s)` : "",
    ]
      .filter(Boolean)
      .join(", ") || "none";
    return `
      <div class="card u-clickable" data-nav="dproject" data-nav-param="${escapeHtml(p.id)}" title="Discovered from ${escapeHtml(p.root_path)}">
        <div class="u-flex-between">
          <div>
            <p class="card-title">${escapeHtml(p.name)} ${workspaceStatusBadge(p)}</p>
            <p class="card-muted">${escapeHtml(p.root_path)}</p>
            <div class="rec-card-meta u-mt-2">
              ${healthBadge(p.health_score)}
              ${workspaceRiskBadge(p.move_risk)}
              <span class="badge">${escapeHtml(p.classification)}</span>
              <span class="badge">${Math.round((p.confidence_score || 0) * 100)}% confidence</span>
            </div>
            <p class="card-muted u-mt-1">Git: ${git} &middot; Last commit: ${p.git_last_commit_date ? formatDate(p.git_last_commit_date) : "—"} &middot; Last modified: ${p.last_modified ? formatDate(p.last_modified) : "—"}</p>
            <p class="card-muted">Docs: ${escapeHtml(p.documentation_status || "Not yet defined")} &middot; Tests: ${escapeHtml(p.test_status || "Not yet defined")} &middot; Assets: ${p.asset_count ?? 0} &middot; Nested: ${escapeHtml(childCounts)}</p>
            ${na.text ? `<p class="card-muted u-mt-1">Next: ${escapeHtml(na.text)}</p>` : ""}
          </div>
          ${healthRingHtml(p.health_score, "sm")}
        </div>
      </div>`;
  }

  async function renderProjectsList() {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading…</p>';

    // Sprint 5 (Project Unification): a Project row with `discovery_item_id`
    // set *is* an adopted/discovered project -- it's already shown, richly,
    // via the discovered list below. Filtering it out of the manual grid
    // is what keeps "one Project" true for the user: never two cards for
    // the same real project.
    const isManualOnly = (p) => !p.discovery_item_id;
    const allProjectsUnfiltered = (await fetchJSON("/pi/projects")).filter(isManualOnly);
    // Discovered/adopted top-level projects (Workspace Adoption / Discovery
    // Engine) are additive to this page -- if that domain is ever
    // unavailable for any reason, the manually-created project list below
    // must still render normally.
    let discoveredProjects = [];
    try {
      discoveredProjects = await fetchJSON("/workspace/discovered?view=top_level");
    } catch (err) {
      console.error("Could not load discovered projects", err);
    }

    if (allProjectsUnfiltered.length === 0 && discoveredProjects.length === 0) {
      viewRoot.innerHTML = renderFirstRunOnboardingHtml();
      document.getElementById("first-run-wizard-form").addEventListener("submit", (e) =>
        handleCreateProjectSubmit(e, "first-run-wizard-status")
      );
      return;
    }

    const workspaceFilter = workspaceSelect.value;
    const projects = workspaceFilter
      ? (await fetchJSON(`/pi/projects?workspace=${encodeURIComponent(workspaceFilter)}`)).filter(isManualOnly)
      : allProjectsUnfiltered;
    // The workspace filter is a Project Intelligence concept (Personal,
    // Kontoor, ...); discovered projects aren't assigned to one, so they're
    // only shown when no filter is applied, alongside the unfiltered list.
    const discovered = workspaceFilter ? [] : discoveredProjects;

    viewRoot.innerHTML = `
      <div class="section-heading">
        <h2>Projects</h2>
        <button type="button" class="btn btn-sm btn-primary" id="new-project-toggle-btn">+ New Project</button>
      </div>
      ${renderNewProjectFormHtml()}
      <div id="projects-grid" class="card-grid">
        ${
          projects.length
            ? projects
                .map(
                  (p) => `
              <div class="card u-clickable" data-open-project="${escapeHtml(p.id)}">
                <div class="u-flex-between">
                  <div>
                    <p class="card-title">${escapeHtml(p.name)}</p>
                    <p class="card-muted">${escapeHtml(p.workspace)}</p>
                    <div class="rec-card-meta u-mt-2">
                      ${healthBadge(p.health_score)}
                      ${priorityBadge(p.priority)}
                      <span class="badge">${escapeHtml(p.status)}</span>
                    </div>
                  </div>
                  ${healthRingHtml(p.health_score, "sm")}
                </div>
              </div>`
                )
                .join("")
            : '<p class="muted">No projects match this workspace filter.</p>'
        }
        ${discovered.map(discoveredProjectCardHtml).join("")}
      </div>`;

    const newProjectForm = document.getElementById("new-project-form");
    document.getElementById("new-project-toggle-btn").addEventListener("click", () => {
      newProjectForm.hidden = !newProjectForm.hidden;
    });
    document.getElementById("new-project-cancel-btn").addEventListener("click", () => {
      newProjectForm.hidden = true;
      newProjectForm.reset();
    });
    newProjectForm.addEventListener("submit", (e) => handleCreateProjectSubmit(e, "new-project-status"));
  }

  // =======================================================================
  // PROJECT DETAIL
  // =======================================================================

  // =======================================================================
  // AI SESSIONS + COCKPIT (v1.4 "Context Engine"): replaces the v1.3 AI
  // Workspace single-record card with a collection of assistant sessions,
  // Session Snapshots, the Resume Engine, and the Project Timeline. The
  // v1.3 backend (/pi/projects/{id}/ai-workspace*) still exists and still
  // works -- this is a new UI over new endpoints
  // (/pi/projects/{id}/ai-sessions*, /pi/projects/{id}/timeline), not a
  // change to the old one. Reuses showToast() (v1.2/v1.3) for status
  // messages; opens URLs client-side via window.open, same as the AI
  // Launcher and AI Workspace before it -- no browser automation here.
  // =======================================================================

  function assistantBadge(assistant) {
    const label = assistant.charAt(0).toUpperCase() + assistant.slice(1);
    return `<span class="badge badge-info">${escapeHtml(label)}</span>`;
  }

  // AI Session status vocabulary: active/paused/completed/other.
  function aiSessionStatusBadge(status) {
    const variants = { active: "healthy", paused: "warning" };
    const label = status === "completed" ? "Completed" : status === "active" ? "Active" : status === "paused" ? "Paused" : status;
    return badgeHtml(label, variants[status]);
  }

  function renderAiSessionsSummaryCardHtml(projectId, sessions) {
    const top = sessions.slice(0, 3);
    return `
      <div class="card">
        <div class="u-flex-between">
          <p class="card-title">AI Sessions</p>
          <button type="button" class="link-btn" data-open-cockpit="${escapeHtml(projectId)}">Open Cockpit &rarr;</button>
        </div>
        ${
          top.length
            ? `<ul class="activity-list">${top
                .map(
                  (s) =>
                    `<li>${s.current ? "&#9679; " : ""}${escapeHtml(s.title || "(untitled session)")} ${assistantBadge(s.assistant)}${s.favorite ? " &#9733;" : ""}</li>`
                )
                .join("")}</ul>`
            : '<p class="muted">No AI sessions yet.</p>'
        }
      </div>`;
  }

  function timelineIcon(entryType) {
    // Session-started vs. snapshot get visually distinct markers in the
    // Project Timeline (requirement: "Timeline with icons").
    return entryType === "snapshot" ? "&#128203;" : "&#9654;";
  }

  // Cockpit/PI project status vocabulary: active/paused/on_hold/other --
  // a distinct vocabulary from AI Session status above (a project's own
  // `status` field, not a session's), so it keeps its own mapping rather
  // than being merged into one.
  function cockpitStatusBadge(status) {
    const s = (status || "").toLowerCase();
    const variants = { active: "healthy", paused: "warning", on_hold: "warning" };
    return badgeHtml(status || "—", variants[s]);
  }

  function renderCockpitSessionCardHtml(projectId, s) {
    return `
      <div class="card u-mt-3 ${s.current ? "cockpit-session-current" : ""}" data-session-card="${escapeHtml(s.id)}">
        <div class="u-flex-between">
          <p class="card-title">${s.current ? '<span class="badge badge-info">&#9679; Current</span> ' : ""}${escapeHtml(s.title || "(untitled session)")}</p>
          <div class="u-flex-between">
            ${assistantBadge(s.assistant)} ${aiSessionStatusBadge(s.status)}
            <button type="button" class="btn btn-sm btn-icon" data-overflow-toggle="${escapeHtml(s.id)}" aria-label="More actions">&#8942;</button>
          </div>
        </div>
        <table class="kv-table">
          <tr><th>Role</th><td>${escapeHtml(s.role || "—")}</td></tr>
          <tr><th>Preferred model</th><td>${escapeHtml(s.preferred_model || "—")}</td></tr>
          <tr><th>Conversation</th><td>${s.conversation_url ? '<span class="badge badge-healthy">Saved</span>' : '<span class="badge">Not saved</span>'}</td></tr>
          <tr><th>Last used</th><td>${formatDate(s.last_used_at)}</td></tr>
          <tr><th>Started</th><td>${formatDate(s.started_at)}</td></tr>
        </table>
        ${s.notes ? `<p class="card-muted u-fs-12">${escapeHtml(s.notes)}</p>` : ""}
        <div class="u-mt-2">
          <button type="button" class="btn btn-sm btn-primary" data-resume="${escapeHtml(s.id)}">Resume</button>
          <!-- Secondary actions live behind an overflow menu; only Resume
               stays visible at all times (requirement: "Hide secondary
               actions under an overflow menu"). -->
          <div class="overflow-menu" data-overflow-menu="${escapeHtml(s.id)}" hidden>
            <button type="button" class="btn btn-sm" data-open-session="${escapeHtml(s.id)}">Open</button>
            <button type="button" class="btn btn-sm" data-favorite="${escapeHtml(s.id)}" data-favorite-state="${s.favorite ? "1" : "0"}">${s.favorite ? "&#9733; Favorited" : "&#9734; Favorite"}</button>
            ${!s.current ? `<button type="button" class="btn btn-sm" data-set-current="${escapeHtml(s.id)}">Set current</button>` : ""}
            <button type="button" class="btn btn-sm" data-snapshot-toggle="${escapeHtml(s.id)}">Snapshot</button>
            <button type="button" class="btn btn-sm" data-delete-session="${escapeHtml(s.id)}">Delete</button>
          </div>
        </div>
        <div data-session-status="${escapeHtml(s.id)}" class="muted u-fs-12 u-mt-2"></div>
        <form data-snapshot-form="${escapeHtml(s.id)}" class="u-mt-3" hidden>
          <label>Accomplishments<textarea name="accomplishments" rows="2"></textarea></label>
          <label class="u-mt-2">Blockers<textarea name="blockers" rows="2"></textarea></label>
          <label class="u-mt-2">Pending work<textarea name="pending_work" rows="2"></textarea></label>
          <label class="u-mt-2">Next prompt<textarea name="next_prompt" rows="2"></textarea></label>
          <label class="u-mt-2">Decisions<textarea name="decisions" rows="2"></textarea></label>
          <label class="u-mt-2">Summary<textarea name="summary" rows="2"></textarea></label>
          <div class="u-mt-2"><button type="submit" class="btn btn-sm btn-primary">Save snapshot</button></div>
        </form>
      </div>`;
  }

  function renderProjectTimelineHtml(entries) {
    if (!entries.length) return '<p class="muted">No activity recorded yet.</p>';
    const mostRecentFirst = [...entries].reverse();
    return `<ol class="timeline-list">${mostRecentFirst
      .map(
        (e) =>
          `<li><span class="timeline-icon" aria-hidden="true">${timelineIcon(e.type)}</span> <span class="muted u-fs-12">${formatDate(e.timestamp)}</span> — ${e.type === "snapshot" ? "Snapshot" : "Started"} (${assistantBadge(e.assistant)} ${escapeHtml(e.session_title || "")}): ${escapeHtml(e.excerpt)}</li>`
      )
      .join("")}</ol>`;
  }

  // =======================================================================
  // PROJECT MEMORY (Sprint C7.1): Cockpit's primary card. The AI Session
  // is a transport, never the source of truth -- this card (backed by
  // `GET /pi/projects/{id}/memory`) is what Resume Work's prompt is built
  // from, and it's what a person should read first, before the AI
  // Sessions list below (now secondary).
  // =======================================================================

  function renderProjectMemoryCardHtml(memory) {
    if (!memory) {
      return `<div class="card u-mt-3"><p class="muted">Project Memory is not available yet.</p></div>`;
    }
    return `
      <div class="card u-mt-3" id="cockpit-project-memory-card">
        <p class="card-muted u-fs-12">Project Memory</p>
        <p class="card-title">${escapeHtml(fmtText(memory.current_objective))}</p>
        <p class="card-muted u-mt-2">Where We Left Off</p>
        <p>${escapeHtml(fmtText(memory.where_we_left_off))}</p>
        <p class="card-muted u-mt-2">Pending Work</p>
        <p>${escapeHtml(memory.pending_work || "None recorded.")}</p>
        <p class="card-muted u-mt-2">Next Action</p>
        <p>${escapeHtml(fmtText((memory.next_action || {}).text))}</p>
        ${renderRelatedProjectsHtml(memory.related_projects)}
        ${renderPotentialImpactHtml(memory.potential_impact)}
      </div>`;
  }

  // Sprint C9: a compact, one-line Potential Impact summary -- see the
  // full Impact Analysis section on the Project Hub page for evidence/
  // recommended actions.
  function renderPotentialImpactHtml(impact) {
    if (!impact || impact.overall_risk === "none" || !impact.affected_count) return "";
    const riskVariant = { critical: "critical", high: "critical", medium: "warning", low: "healthy" }[impact.overall_risk] || "";
    return `
      <p class="card-muted u-mt-2">Potential Impact</p>
      <p class="u-fs-12">${riskVariant ? badgeHtml(impact.overall_risk, riskVariant) : escapeHtml(impact.overall_risk)}
        &middot; ${impact.affected_count} project(s) affected${impact.affected_names.length ? `: ${impact.affected_names.map((n) => escapeHtml(n)).join(", ")}` : ""}</p>
    `;
  }

  // Sprint C8: a small, bounded section only -- top dependencies/
  // consumers/recent shared decisions, never a graph dump. See the full
  // Project Ecosystem section on the Project Hub page for everything else.
  function renderRelatedProjectsHtml(related) {
    if (!related) return "";
    const { dependencies, consumers, recent_shared_decisions } = related;
    if (!dependencies.length && !consumers.length && !recent_shared_decisions.length) return "";
    const list = (names) => names.map((n) => escapeHtml(n)).join(", ");
    return `
      <p class="card-muted u-mt-2">Related Projects</p>
      ${dependencies.length ? `<p class="u-fs-12">Dependencies: ${list(dependencies)}</p>` : ""}
      ${consumers.length ? `<p class="u-fs-12">Consumers: ${list(consumers)}</p>` : ""}
      ${recent_shared_decisions.length ? `<p class="u-fs-12">Recent shared decisions: ${list(recent_shared_decisions)}</p>` : ""}
    `;
  }

  async function renderCockpitPage(projectIdParam) {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading Cockpit…</p>';

    const allProjects = await fetchJSON("/pi/projects");
    if (!allProjects.length) {
      viewRoot.innerHTML = `
        <div class="section-heading"><h2>Cockpit</h2></div>
        <p class="muted">No projects yet — create one on the Projects page first.</p>`;
      return;
    }

    const projectId =
      projectIdParam && allProjects.some((p) => p.id === projectIdParam) ? projectIdParam : allProjects[0].id;
    const project = allProjects.find((p) => p.id === projectId);

    const [sessionsRaw, timeline, projectMemory] = await Promise.all([
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/ai-sessions`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/timeline`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/memory`).catch(() => null),
    ]);

    // Promote current AI sessions to the top of the list (requirement:
    // "Promote current AI sessions").
    const sessions = [...sessionsRaw].sort((a, b) => (b.current ? 1 : 0) - (a.current ? 1 : 0));
    const currentSession = sessions.find((s) => s.current) || sessions[0] || null;

    let latestSnapshot = null;
    if (currentSession) {
      const snapshots = await fetchJSON(
        `/pi/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(currentSession.id)}/snapshots`
      );
      latestSnapshot = snapshots[0] || null;
    }

    // Sprint C1B (Rewiring): `/pi/projects` embeds `project_context` per
    // project (see `routers/pi/projects.py`) -- Cockpit reads its
    // resume_state/health directly from that instead of a separate,
    // best-effort `/project-context/{id}` fetch. Sprint C7.1: the
    // objective/next-action/last-snapshot text Cockpit's primary card
    // shows now comes from Project Memory (`projectMemory`,
    // `renderProjectMemoryCardHtml`), not recomputed here.
    const context = project && project.project_context;
    // Resume Work is available whenever the canonical resume orchestration
    // says so (adopted project with -- or about to get -- an AI Session),
    // not just "does Cockpit already have a `currentSession` loaded".
    const resumeAvailable = context && context.resume_state ? context.resume_state.available : Boolean(currentSession);

    const lastActivity = [project && project.updated_at, currentSession && currentSession.last_used_at]
      .filter(Boolean)
      .sort()
      .pop();

    const projectOptions = allProjects
      .map((p) => `<option value="${escapeHtml(p.id)}" ${p.id === projectId ? "selected" : ""}>${escapeHtml(p.name)}</option>`)
      .join("");

    viewRoot.innerHTML = `
      <div class="cockpit-header card">
        <div class="cockpit-header-main">
          <h2>${escapeHtml((project && project.name) || "Cockpit")}</h2>
          <div class="cockpit-header-meta">
            <span class="badge">${escapeHtml((project && project.workspace) || "—")}</span>
            ${cockpitStatusBadge((context && context.status) || (project && project.status))}
            ${context && context.health ? healthBadge(context.health_score, context.health) : ""}
            <span class="muted u-fs-12">Last activity: ${formatDate(lastActivity)}</span>
          </div>
        </div>
        <div class="cockpit-header-actions">
          <button
            type="button"
            class="btn btn-primary btn-resume-work"
            id="cockpit-resume-work-btn"
            ${currentSession ? `data-resume="${escapeHtml(currentSession.id)}"` : ""}
            ${resumeAvailable ? "" : "disabled"}
          >&#9654; Resume Work</button>
          <!-- Secondary, page-level actions (switching projects) live
               behind an overflow menu next to the primary Resume Work
               button. -->
          <button type="button" class="btn btn-sm btn-icon" id="cockpit-overflow-toggle-btn" aria-label="More options">&#8942;</button>
        </div>
        <div class="overflow-menu" id="cockpit-overflow-menu" hidden>
          <label>Project<select id="cockpit-project-select">${projectOptions}</select></label>
        </div>
      </div>

      ${renderProjectMemoryCardHtml(projectMemory)}

      <div class="home-grid u-mt-4">
        <div>
          <div class="card u-mt-3" id="cockpit-new-session-card">
            <div class="u-flex-between">
              <p class="card-title">New AI Session</p>
              <button type="button" class="btn btn-sm btn-primary" id="cockpit-new-session-toggle-btn">+ New AI Session</button>
            </div>
            <form id="cockpit-new-session-form" hidden>
              <div class="field-row">
                <label>Assistant
                  <select name="assistant" required>
                    <option value="claude">Claude</option>
                    <option value="chatgpt">ChatGPT</option>
                    <option value="gemini">Gemini</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label>Title<input type="text" name="title" placeholder="e.g. Refactor auth flow" /></label>
              </div>
              <label class="u-mt-2">Conversation URL (optional)<input type="url" name="conversation_url" placeholder="https://…" /></label>
              <div class="field-row u-mt-2">
                <label>Role<input type="text" name="role" placeholder="Engineer, Architect, Reviewer…" /></label>
                <label>Preferred model<input type="text" name="preferred_model" /></label>
              </div>
              <label class="u-mt-2">Notes<textarea name="notes" rows="2"></textarea></label>
              <div class="u-mt-3"><button type="submit" class="btn btn-sm btn-primary">Create session</button></div>
              <div id="cockpit-new-session-status" class="u-mt-2"></div>
            </form>
          </div>

          <div class="page-section">
            <div class="section-heading"><h2>AI Sessions</h2></div>
            ${
              sessions.length
                ? sessions.map((s) => renderCockpitSessionCardHtml(projectId, s)).join("")
                : '<p class="muted">No AI sessions for this project yet.</p>'
            }
          </div>
        </div>

        <div>
          <div class="card">
            <p class="card-title">Project Timeline</p>
            ${renderProjectTimelineHtml(timeline)}
          </div>
        </div>
      </div>`;

    wireCockpitPage(projectId);
  }

  function wireCockpitPage(projectId) {
    document.getElementById("cockpit-project-select").addEventListener("change", (e) => {
      navigate("cockpit", e.target.value);
    });

    const headerOverflowBtn = document.getElementById("cockpit-overflow-toggle-btn");
    const headerOverflowMenu = document.getElementById("cockpit-overflow-menu");
    headerOverflowBtn.addEventListener("click", () => {
      headerOverflowMenu.hidden = !headerOverflowMenu.hidden;
    });

    document.querySelectorAll("[data-overflow-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const menu = document.querySelector(`[data-overflow-menu="${btn.dataset.overflowToggle}"]`);
        menu.hidden = !menu.hidden;
      });
    });

    // "New AI Session" is collapsed by default and only expands when the
    // user explicitly clicks "+ New AI Session" (requirements 3 and 4).
    const newSessionForm = document.getElementById("cockpit-new-session-form");
    document.getElementById("cockpit-new-session-toggle-btn").addEventListener("click", () => {
      newSessionForm.hidden = !newSessionForm.hidden;
    });

    newSessionForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(e.currentTarget);
      const payload = {
        assistant: data.get("assistant"),
        title: data.get("title") || "",
        conversation_url: data.get("conversation_url") || "",
        role: data.get("role") || "",
        preferred_model: data.get("preferred_model") || "",
        notes: data.get("notes") || "",
      };
      const statusEl = document.getElementById("cockpit-new-session-status");
      statusEl.innerHTML = '<span class="muted loading-pulse">Creating…</span>';
      try {
        await postJSON(`/pi/projects/${encodeURIComponent(projectId)}/ai-sessions`, payload);
        // Auto-collapse the form after a successful creation (requirement 5).
        document.getElementById("cockpit-new-session-form").hidden = true;
        showToast("AI Session created.");
        await renderCockpitPage(projectId);
      } catch (err) {
        statusEl.innerHTML = `<span class="error-box">${escapeHtml(err.message)}</span>`;
      }
    });

    const sessionBase = (sessionId) => `/pi/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}`;

    document.querySelectorAll("[data-resume]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sessionId = btn.dataset.resume;
        const statusEl = document.querySelector(`[data-session-status="${sessionId}"]`);
        statusEl.textContent = "Resuming…";
        try {
          const result = await fetchJSON(`${sessionBase(sessionId)}/resume`);
          try {
            await navigator.clipboard.writeText(result.prompt);
          } catch (clipErr) {
            statusEl.innerHTML = `<span class="error-box">Could not copy automatically: ${escapeHtml(clipErr.message)}</span>`;
            return;
          }
          if (result.url) window.open(result.url, "_blank");
          statusEl.textContent = "";
          showToast(result.used_saved_conversation ? "Prompt copied. Press Ctrl+V and Enter." : "No conversation saved yet.");
          await renderCockpitPage(projectId);
        } catch (err) {
          statusEl.innerHTML = `<span class="error-box">${escapeHtml(err.message)}</span>`;
        }
      });
    });

    document.querySelectorAll("[data-open-session]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sessionId = btn.dataset.openSession;
        const statusEl = document.querySelector(`[data-session-status="${sessionId}"]`);
        try {
          const result = await postJSON(`${sessionBase(sessionId)}/open`, {});
          if (result.url) window.open(result.url, "_blank");
          if (result.message) showToast(result.message);
          statusEl.textContent = "";
        } catch (err) {
          statusEl.innerHTML = `<span class="error-box">${escapeHtml(err.message)}</span>`;
        }
      });
    });

    document.querySelectorAll("[data-favorite]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sessionId = btn.dataset.favorite;
        const isFavorite = btn.dataset.favoriteState === "1";
        try {
          await postJSON(sessionBase(sessionId), { favorite: !isFavorite }, "PATCH");
          await renderCockpitPage(projectId);
        } catch (err) {
          showToast(`Could not update favorite: ${err.message}`);
        }
      });
    });

    document.querySelectorAll("[data-set-current]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await postJSON(`${sessionBase(btn.dataset.setCurrent)}/set-current`, {});
          await renderCockpitPage(projectId);
        } catch (err) {
          showToast(`Could not set current: ${err.message}`);
        }
      });
    });

    document.querySelectorAll("[data-snapshot-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const form = document.querySelector(`[data-snapshot-form="${btn.dataset.snapshotToggle}"]`);
        form.hidden = !form.hidden;
      });
    });

    document.querySelectorAll("[data-snapshot-form]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const sessionId = form.dataset.snapshotForm;
        const data = new FormData(form);
        const payload = {
          accomplishments: data.get("accomplishments") || "",
          blockers: data.get("blockers") || "",
          pending_work: data.get("pending_work") || "",
          next_prompt: data.get("next_prompt") || "",
          decisions: data.get("decisions") || "",
          summary: data.get("summary") || "",
        };
        try {
          await postJSON(`${sessionBase(sessionId)}/snapshots`, payload);
          showToast("Snapshot saved.");
          await renderCockpitPage(projectId);
        } catch (err) {
          showToast(`Could not save snapshot: ${err.message}`);
        }
      });
    });

    document.querySelectorAll("[data-delete-session]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sessionId = btn.dataset.deleteSession;
        if (!window.confirm("Delete this AI session and its snapshots? This cannot be undone.")) return;
        try {
          await fetchJSON(sessionBase(sessionId), { method: "DELETE" });
          await renderCockpitPage(projectId);
        } catch (err) {
          showToast(`Could not delete: ${err.message}`);
        }
      });
    });
  }

  async function renderProjectDetail(projectId) {
    if (!projectId) {
      navigate("projects");
      return;
    }
    const [project, allProjects, capabilities, consumed, dependencies, dependents, recs, aiSessions] = await Promise.all([
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}`),
      fetchJSON("/pi/projects"),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities/consumed`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependencies`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependents`),
      fetchJSON(`/advisor/recommendations?project_id=${encodeURIComponent(projectId)}`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/ai-sessions`),
    ]);

    const projectsById = Object.fromEntries(allProjects.map((p) => [p.id, p]));
    const relatedNames = (project.related_projects || []).map((rid) => projectsById[rid]?.name || rid);

    viewRoot.innerHTML = `
      <div class="section-heading">
        <h2>${escapeHtml(project.name)}</h2>
        <button class="link-btn" data-nav="projects">&larr; All projects</button>
      </div>
      <div class="project-layout">
        <div class="project-col">
          <div class="card u-text-center">
            ${healthRingHtml(project.health_score)}
            <p class="u-mt-3">${healthBadge(project.health_score)}</p>
          </div>
          <div class="card">
            <table class="kv-table">
              <tr><th>Status</th><td>${escapeHtml(project.status)}</td></tr>
              <tr><th>Workspace</th><td>${escapeHtml(project.workspace)}</td></tr>
              <tr><th>Priority</th><td>${priorityBadge(project.priority)}</td></tr>
              <tr><th>Owner</th><td>${escapeHtml(project.owner || "—")}</td></tr>
            </table>
          </div>
          <div class="card">
            <p class="card-title">Advisor Summary</p>
            ${recs.length ? `<p>${escapeHtml(recs[0].title)}</p><p class="card-muted">${escapeHtml(recs[0].summary)}</p>` : '<p class="muted">No open recommendations.</p>'}
          </div>
          ${renderAiSessionsSummaryCardHtml(projectId, aiSessions)}
        </div>

        <div class="project-col">
          <div class="card">
            <p class="card-title">Overview</p>
            <p>${escapeHtml(project.description || "No description yet.")}</p>
            <div class="rec-card-meta">${(project.tags || []).map((t) => `<span class="badge">${escapeHtml(t)}</span>`).join("")}</div>
          </div>
          <div class="card">
            <p class="card-title">Notes</p>
            ${listOrNone((project.notes || []).map((n) => n.text))}
          </div>
          <div class="card">
            <p class="card-title">Recent Decisions</p>
            ${listOrNone((project.decisions || []).map((d) => d.text))}
          </div>
          <div class="card">
            <p class="card-title">Open TODOs</p>
            ${listOrNone((project.todos || []).filter((t) => t.status !== "done").map((t) => t.text))}
          </div>
          <div class="card">
            <p class="card-title">Deliverables</p>
            ${listOrNone((project.deliverables || []).map((d) => `${d.text || d.name} ${d.status ? `(${d.status})` : ""}`))}
          </div>
        </div>

        <div class="project-col">
          <div class="card">
            <p class="card-title">Capabilities</p>
            <p class="card-muted u-fs-12">Provides</p>
            ${listOrNone(capabilities.map((c) => c.name))}
            <p class="card-muted u-fs-12">Consumes</p>
            ${listOrNone(consumed.map((c) => `${c.name} (from ${c.provider_project_name})`))}
          </div>
          <div class="card">
            <p class="card-title">Dependencies</p>
            <p class="card-muted u-fs-12">Depends on</p>
            ${listOrNone(dependencies.map((d) => d.depends_on_project_name))}
            <p class="card-muted u-fs-12">Depended on by</p>
            ${listOrNone(dependents.map((d) => d.dependent_project_name))}
          </div>
          <div class="card">
            <p class="card-title">Related Projects</p>
            ${listOrNone(relatedNames)}
          </div>
          <div class="card">
            <p class="card-title">Advisor</p>
            ${recs.length ? `<ul>${recs.map((r) => `<li>${escapeHtml(r.title)} <span class="badge">${r.priority_score}</span></li>`).join("")}</ul>` : '<p class="muted">Nothing outstanding.</p>'}
          </div>
          <div class="card">
            <p class="card-title">Knowledge Graph Preview</p>
            <svg id="project-graph-preview" viewBox="0 0 280 200" class="u-full-width u-clickable"></svg>
          </div>
        </div>
      </div>
    `;

    document.querySelectorAll("#view-root [data-nav]").forEach((el) => {
      el.addEventListener("click", () => navigate(el.dataset.nav));
    });

    try {
      const subgraph = await fetchJSON(`/graph/project/${encodeURIComponent(projectId)}?depth=1`);
      const svg = document.getElementById("project-graph-preview");
      const view = createGraphView(svg, { width: 280, height: 200, interactive: false });
      view.setNodes(subgraph.nodes, subgraph.edges);
      svg.addEventListener("click", () => {
        pendingGraphFocus = `project:${projectId}`;
        navigate("graph");
      });
    } catch (err) {
      console.error("Could not load project graph preview", err);
    }
  }

  // =======================================================================
  // KNOWLEDGE (ported from Milestone 2)
  // =======================================================================

  async function renderKnowledge() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Knowledge</h2></div>
      <div class="card page-section" id="import-panel">
        <p class="card-title">Import ChatGPT conversations</p>
        <p class="muted">Upload a ChatGPT export (<code>conversations.json</code> or the export ZIP) to bring conversations into ROLE OS. Re-importing the same file will not create duplicates.</p>
        <form id="import-form">
          <input type="file" id="import-file-input" accept=".json,.zip" required />
          <button type="submit" class="btn btn-sm" id="import-submit-btn">Import</button>
        </form>
        <div id="import-status" class="u-mt-4"></div>
      </div>
      <div class="home-grid">
        <div>
          <div class="card">
            <p class="card-title">Recent knowledge cards</p>
            <ul id="knowledge-card-list" class="activity-list"><li class="muted">Loading…</li></ul>
          </div>
        </div>
        <div>
          <div class="card">
            <p class="card-title">Knowledge Areas</p>
            <ul id="knowledge-project-list" class="activity-list"><li class="muted">Loading…</li></ul>
          </div>
          <div class="card u-mt-4">
            <p class="card-title">Timeline</p>
            <ol id="knowledge-timeline-list" class="timeline-list"><li class="muted">Loading…</li></ol>
          </div>
        </div>
      </div>
    `;

    const [cards, projects, timeline] = await Promise.all([
      fetchJSON("/ui/recent?limit=15"),
      fetchJSON("/projects"),
      fetchJSON("/ui/timeline?limit=40"),
    ]);

    document.getElementById("knowledge-card-list").innerHTML = cards
      .map((c) => `<li data-open-card="${escapeHtml(c.conversation_id)}" class="u-clickable">${escapeHtml(c.title)} <span class="card-muted">— ${escapeHtml(c.project)}</span></li>`)
      .join("") || '<li class="muted">No cards yet.</li>';

    document.getElementById("knowledge-project-list").innerHTML = projects
      .map((p) => `<li>${escapeHtml(p.project)} <span class="badge">${p.count}</span></li>`)
      .join("") || '<li class="muted">No projects yet.</li>';

    document.getElementById("knowledge-timeline-list").innerHTML = timeline
      .map((t) => `<li data-open-card="${escapeHtml(t.conversation_id)}" class="u-clickable">${escapeHtml(t.date || "")} — ${escapeHtml(t.title)}</li>`)
      .join("") || '<li class="muted">No entries yet.</li>';

    wireImportPanel();
  }

  // =======================================================================
  // CHATGPT CONVERSATION IMPORTER (Sprint B1)
  // =======================================================================

  function wireImportPanel() {
    const form = document.getElementById("import-form");
    const fileInput = document.getElementById("import-file-input");
    const submitBtn = document.getElementById("import-submit-btn");
    const statusEl = document.getElementById("import-status");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const file = fileInput.files[0];
      if (!file) return;

      submitBtn.disabled = true;
      submitBtn.textContent = "Importing…";
      statusEl.innerHTML = '<p class="muted loading-pulse">Importing conversations…</p>';

      const body = new FormData();
      body.append("file", file);

      try {
        const result = await fetchJSON("/import/chatgpt", { method: "POST", body });
        statusEl.innerHTML = `
          <p class="u-mt-0"><strong>Import completed</strong> — ${escapeHtml(file.name)}</p>
          <table class="kv-table">
            <tr><th>Total found</th><td>${result.total_found}</td></tr>
            <tr><th>Imported</th><td>${result.imported}</td></tr>
            <tr><th>Updated</th><td>${result.updated}</td></tr>
            <tr><th>Skipped (duplicates)</th><td>${result.skipped}</td></tr>
            <tr><th>Invalid</th><td>${result.invalid}</td></tr>
          </table>
        `;
      } catch (err) {
        statusEl.innerHTML = `<p class="error-box">Import failed: ${escapeHtml(err.message)}</p>`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Import";
        form.reset();
      }
    });
  }

  // =======================================================================
  // CONVERSATION DETAIL OVERLAY (Sprint B1.5, kept)
  //
  // Sprint C3.1 (Explorer 2.0 hardening): the Sprint B1.5 Conversation
  // Explorer -- its own metrics grid (`/import/metrics`, the same legacy
  // zero-centric counters Dashboard 2.0 already removed), source/status/
  // imported-date filters (`/import/facets`), and paginated table
  // (`/import/conversations?page=...`) -- has been removed from the
  // Explorer page entirely, not merely hidden underneath the universal
  // search. Explorer's primary (and now only) experience is `GET
  // /explorer/search` (see `renderExplorerPage` below); "Conversation" is
  // one of its 13 result types, reusing `app.imports.db.list_
  // conversations_page` for search only -- no separate browsing dashboard.
  // The one piece still kept from Sprint B1.5 is this detail overlay
  // (`openConversationDetail` and its helpers below): a search result's
  // "Open Conversation" action, and the Knowledge Graph page's "Open in
  // Conversation Explorer" action, both still need somewhere to show one
  // conversation's full content -- that is a detail view, not a browsing
  // dashboard, and is shared with pages beyond Explorer.
  // =======================================================================

  // Set by the Knowledge Graph page's "Open in Conversation Explorer"
  // action (and by Explorer search results' "Open Conversation" action)
  // before navigating here, so the conversation detail overlay opens
  // automatically once the Explorer page has loaded.
  let pendingExplorerConversationFocus = null;

  // =======================================================================
  // EXPLORER 2.0 (Sprint C3): universal search over every domain ROLE OS
  // tracks -- Projects, AI Sessions, Snapshots, Commits, Knowledge,
  // Assets, Markdown, Decisions, Capabilities, Dependencies, Advisor
  // Recommendations, Conversations, Timeline Events. Presentation only:
  // every field rendered below (health tier, next action, resume
  // availability, ranking order, grouping) comes straight from `GET
  // /explorer/search` -- nothing is recomputed, re-ranked, or
  // deduplicated client-side. The pre-existing Conversation Explorer
  // (Sprint B1.5, below) is unchanged and still available underneath.
  // =======================================================================

  const EXPLORER_FILTER_TYPES = [
    { key: "", label: "All" },
    { key: "Project", label: "Projects" },
    { key: "AI Session", label: "Sessions" },
    { key: "Snapshot", label: "Snapshots" },
    { key: "Knowledge Card", label: "Knowledge" },
    { key: "Asset", label: "Assets" },
    { key: "Commit", label: "Commits" },
    { key: "Timeline Event", label: "Activity" },
    { key: "Recommendation", label: "Recommendations" },
    { key: "Markdown", label: "Markdown" },
  ];

  const EXPLORER_TYPE_ICONS = {
    Project: "\u{1F4C1}",
    "AI Session": "\u{1F4AC}",
    Snapshot: "\u{1F4CB}",
    Commit: "▶",
    "Knowledge Card": "\u{1F9E0}",
    Asset: "\u{1F5BC}",
    Conversation: "\u{1F4AC}",
    Markdown: "\u{1F4C4}",
    Decision: "⚖",
    Capability: "⚙",
    Dependency: "\u{1F517}",
    Recommendation: "\u{1F4A1}",
    "Timeline Event": "⏱",
    "Ecosystem Relationship": "\u{1F517}",
    Impact: "\u{1F4A5}",
    "Executive Decision": "\u{1F3AF}",
  };

  let explorerUniversalFilter = "";
  let explorerUniversalQuery = "";

  function explorerResultActionsHtml(actions) {
    return (actions || [])
      .map((a) => {
        if (a.action === "resume") {
          return a.param
            ? `<button type="button" class="btn btn-sm btn-primary" data-resume-work-item="${escapeHtml(a.param)}">${escapeHtml(a.label)}</button>`
            : "";
        }
        return `<button type="button" class="btn btn-sm" data-explorer-nav="${escapeHtml(a.nav || "")}" data-explorer-param="${escapeHtml(a.param || "")}">${escapeHtml(a.label)}</button>`;
      })
      .join("");
  }

  function explorerResultCardHtml(item) {
    const icon = EXPLORER_TYPE_ICONS[item.type] || "•";
    const titleNav = item.type === "Project" ? `data-explorer-nav="phub" data-explorer-param="${escapeHtml(item.project_id || "")}"` : "";
    return `
      <div class="card explorer-result-card">
        <div class="u-flex-between">
          <p class="card-title ${item.type === "Project" ? "u-clickable" : ""}" ${titleNav}>
            <span aria-hidden="true">${icon}</span> ${escapeHtml(item.title || "(untitled)")}
          </p>
          ${formatDate(item.date) !== "—" ? `<span class="card-muted u-fs-12">${formatDate(item.date)}</span>` : ""}
        </div>
        ${item.project ? `<p class="card-muted u-fs-12">${escapeHtml(item.project)}</p>` : ""}
        ${item.summary ? `<p class="u-fs-12">${escapeHtml(item.summary)}</p>` : ""}
        <p class="card-muted u-fs-12">${escapeHtml(item.origin || "")}</p>
        <div class="u-mt-2">${explorerResultActionsHtml(item.actions)}</div>
      </div>`;
  }

  function explorerGroupHtml(type, items) {
    if (!items.length) return "";
    const groupId = `explorer-group-${type.replace(/\s+/g, "-")}`;
    return `
      <div class="page-section explorer-result-group">
        <div class="section-heading u-clickable" data-explorer-toggle-group="${groupId}">
          <h3>${escapeHtml(type)} <span class="badge">${items.length}</span></h3>
          <span aria-hidden="true">▾</span>
        </div>
        <div id="${groupId}" class="card-grid">
          ${items.map(explorerResultCardHtml).join("")}
        </div>
      </div>`;
  }

  function renderExplorerUniversalResults(data) {
    const el = document.getElementById("explorer-universal-results");
    if (!el) return;
    if (!data.total) {
      el.innerHTML = data.query
        ? `<p class="muted">No results for "${escapeHtml(data.query)}".</p>`
        : '<p class="muted">Nothing tracked yet -- adopt a project on the Workspace page, or start an AI Session, to see it here.</p>';
      return;
    }
    const html = RESULT_TYPE_ORDER.map((type) => explorerGroupHtml(type, data.groups[type] || [])).join("");
    el.innerHTML = html || '<p class="muted">No results.</p>';
    el.querySelectorAll("[data-explorer-toggle-group]").forEach((heading) => {
      heading.addEventListener("click", () => {
        const group = document.getElementById(heading.dataset.explorerToggleGroup);
        if (group) group.classList.toggle("explorer-group-collapsed");
      });
    });
    el.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
      btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
    });
    el.querySelectorAll("[data-explorer-nav]").forEach((btn) => {
      btn.addEventListener("click", () => explorerHandleNav(btn.dataset.explorerNav, btn.dataset.explorerParam));
    });
  }

  const RESULT_TYPE_ORDER = [
    "Executive Decision",
    "Project",
    "AI Session",
    "Snapshot",
    "Timeline Event",
    "Commit",
    "Recommendation",
    "Knowledge Card",
    "Asset",
    "Markdown",
    "Decision",
    "Capability",
    "Dependency",
    "Conversation",
    "Ecosystem Relationship",
    "Impact",
  ];

  function explorerHandleNav(nav, param) {
    if (!nav) return;
    if (nav === "card") {
      openCardDetail(param);
      return;
    }
    if (nav === "explorer-conversation") {
      openConversationDetail(param);
      return;
    }
    if (nav === "asset") {
      // Sprint C4 §10: an Explorer asset result opens the same canonical
      // Asset Detail panel the Assets gallery uses -- never a second/
      // legacy file representation.
      openAssetDetail(param);
      return;
    }
    navigate(nav, param || undefined);
  }

  const runExplorerUniversalSearch = debounce(async (q) => {
    explorerUniversalQuery = q;
    const resultsEl = document.getElementById("explorer-universal-results");
    // Sprint C3.1: empty query is a real request too -- `GET /explorer/
    // search` with `q=""` returns a bounded browse of everything (see
    // `app.explorer.service.search`'s docstring), so Explorer always has
    // real content, never an empty page waiting for input.
    if (resultsEl) resultsEl.innerHTML = '<p class="muted loading-pulse">Searching…</p>';
    try {
      const params = new URLSearchParams({ q });
      if (explorerUniversalFilter) params.append("types", explorerUniversalFilter);
      const data = await fetchJSON(`/explorer/search?${params.toString()}`);
      renderExplorerUniversalResults(data);
    } catch (err) {
      if (resultsEl) resultsEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
    }
  }, 250);

  function wireExplorerUniversalSearch(initialQuery) {
    const input = document.getElementById("explorer-universal-search-input");
    const filterBar = document.getElementById("explorer-universal-filters");
    filterBar.innerHTML = EXPLORER_FILTER_TYPES.map(
      (f) =>
        `<button type="button" class="btn btn-sm ${f.key === explorerUniversalFilter ? "btn-primary" : ""}" data-explorer-filter="${escapeHtml(f.key)}">${escapeHtml(f.label)}</button>`
    ).join("");
    filterBar.querySelectorAll("[data-explorer-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        explorerUniversalFilter = btn.dataset.explorerFilter;
        wireExplorerUniversalSearch(input.value);
        runExplorerUniversalSearch(input.value.trim());
      });
    });
    input.addEventListener("input", () => runExplorerUniversalSearch(input.value.trim()));
    if (initialQuery) input.value = initialQuery;
  }

  async function renderExplorerPage(initialParam) {
    const initialQuery = initialParam ? decodeURIComponent(initialParam) : "";
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Explorer</h2></div>
      <div class="card page-section">
        <input id="explorer-universal-search-input" type="search" class="explorer-universal-input" placeholder="Search everything in ROLE OS: projects, sessions, snapshots, commits, knowledge, assets, README, TODO..." value="${escapeHtml(initialQuery)}" />
        <div id="explorer-universal-filters" class="workspace-filter-tabs u-mt-2"></div>
      </div>
      <div id="explorer-universal-results"></div>
    `;

    // Sprint C3.1: the universal search is the whole page now -- it runs
    // immediately on load (empty query = a bounded browse of everything
    // ProjectContext/Home/Advisor/Workspace/Cockpit already track), not
    // only once the user starts typing. There is no other content on this
    // page to fall back to.
    wireExplorerUniversalSearch(initialQuery);
    runExplorerUniversalSearch(initialQuery.trim());

    if (pendingExplorerConversationFocus) {
      const focusId = pendingExplorerConversationFocus;
      pendingExplorerConversationFocus = null;
      openConversationDetail(focusId);
    }
  }

  function exportConversation(id) {
    window.open(`/import/conversations/${encodeURIComponent(id)}/export`, "_blank");
  }

  async function deleteConversationWithConfirm(id, onDeleted) {
    if (!window.confirm("Delete this imported conversation? This cannot be undone.")) return;
    try {
      await fetchJSON(`/import/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (onDeleted) onDeleted();
    } catch (err) {
      window.alert(`Could not delete conversation: ${err.message}`);
    }
  }

  function roleLabel(role) {
    const known = ["user", "assistant", "system"];
    return known.includes(role) ? role.toUpperCase() : escapeHtml(role).toUpperCase();
  }

  function conversationMessagesHtml(content, filterText) {
    const needle = (filterText || "").toLowerCase();
    const visible = needle ? content.filter((m) => m.text.toLowerCase().includes(needle)) : content;
    if (!visible.length) return '<p class="muted">No messages match your search.</p>';
    return `<div class="message-list">${visible
      .map((m) => {
        const roleClass = ["user", "assistant", "system"].includes(m.role) ? `role-${m.role}` : "";
        return `
      <div class="message-item ${roleClass}">
        <div class="message-item-header"><span>${roleLabel(m.role)}</span><span>${m.created_at ? formatDate(m.created_at) : ""}</span></div>
        <div class="message-item-text">${escapeHtml(m.text)}</div>
      </div>`;
      })
      .join("")}</div>`;
  }

  function conversationDetailHtml(conv) {
    return `
      <h2 id="detail-title">${escapeHtml(conv.title)}</h2>
      <p class="card-muted">
        ${escapeHtml(conv.source)} &middot; ${conv.message_count} messages &middot;
        Conversation: ${formatDate(conv.created_at)} &middot; Imported: ${formatDate(conv.imported_at)}
      </p>
      <div class="graph-detail-actions u-mb-3">
        <button type="button" class="btn btn-sm" id="explorer-detail-copy-btn">Copy conversation</button>
        <button type="button" class="btn btn-sm" id="explorer-detail-export-btn">Export JSON</button>
        <button type="button" class="btn btn-sm" id="explorer-detail-delete-btn">Delete</button>
        <button type="button" class="btn btn-sm" id="explorer-detail-view-graph-btn">View in Knowledge Graph</button>
      </div>
      <input id="explorer-detail-search-input" type="search" class="u-full-width u-mb-3" placeholder="Search within this conversation..." />
      <div id="explorer-detail-messages">${conversationMessagesHtml(conv.content)}</div>
      <h4 class="u-mt-4">Metadata</h4>
      <table class="kv-table">
        <tr><th>Conversation ID</th><td>${escapeHtml(conv.id)}</td></tr>
        <tr><th>Fingerprint</th><td>${escapeHtml(conv.fingerprint)}</td></tr>
        <tr><th>Import Run</th><td>${escapeHtml(conv.import_run_id || "—")}</td></tr>
        <tr><th>Import Date</th><td>${formatDate(conv.imported_at)}</td></tr>
        <tr><th>Created</th><td>${formatDate(conv.created_at)}</td></tr>
        <tr><th>Updated</th><td>${formatDate(conv.updated_at)}</td></tr>
        <tr><th>Roles</th><td>${conv.roles.map(escapeHtml).join(", ") || "—"}</td></tr>
        <tr><th>Source File</th><td>${escapeHtml(conv.source_file || "—")}</td></tr>
        <tr><th>Message Count</th><td>${conv.message_count}</td></tr>
      </table>
      <h4 class="u-mt-4">Knowledge</h4>
      <div class="graph-detail-actions u-mb-3">
        <button type="button" class="btn btn-sm" id="explorer-detail-extract-btn">Extract Knowledge</button>
        <span id="explorer-detail-extract-status" class="muted"></span>
      </div>
      <div id="explorer-detail-knowledge"><p class="muted loading-pulse">Loading…</p></div>
    `;
  }

  // Object types the extractor supports, in display order, with the label
  // to render for each section -- Sprint 4 supports exactly these seven,
  // no more.
  const EXTRACTION_OBJECT_TYPES = [
    ["Project", "Projects"],
    ["Person", "People"],
    ["Task", "Tasks"],
    ["Decision", "Decisions"],
    ["Idea", "Ideas"],
    ["Document", "Documents"],
    ["Asset", "Assets"],
  ];

  function groupExtractedObjects(objects) {
    const groups = {};
    EXTRACTION_OBJECT_TYPES.forEach(([type]) => (groups[type] = []));
    objects.forEach((o) => {
      if (groups[o.object_type]) groups[o.object_type].push(o);
    });
    return groups;
  }

  function knowledgeSectionsHtml(objects) {
    const groups = groupExtractedObjects(objects);
    return EXTRACTION_OBJECT_TYPES.map(([type, label]) => {
      const items = groups[type];
      const body = items.length
        ? `<ul class="activity-list">${items
            .map(
              (o) => `
          <li class="u-flex-between">
            <span>${escapeHtml(o.title)}</span>
            <span><span class="badge">${Math.round(o.confidence * 100)}%</span>
              <button type="button" class="link-btn" data-extraction-delete="${escapeHtml(o.id)}">Delete</button></span>
          </li>`
            )
            .join("")}</ul>`
        : '<p class="muted">None found.</p>';
      return `<div class="page-section"><h5>${label} (${items.length})</h5>${body}</div>`;
    }).join("");
  }

  async function loadConversationKnowledge(conversationId) {
    const el = document.getElementById("explorer-detail-knowledge");
    if (!el) return;
    try {
      const objects = await fetchJSON(`/extraction/conversations/${encodeURIComponent(conversationId)}/objects`);
      el.innerHTML = knowledgeSectionsHtml(objects);
      el.querySelectorAll("[data-extraction-delete]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await fetchJSON(`/extraction/objects/${encodeURIComponent(btn.dataset.extractionDelete)}`, { method: "DELETE" });
            loadConversationKnowledge(conversationId);
          } catch (err) {
            window.alert(`Could not delete object: ${err.message}`);
          }
        });
      });
    } catch (err) {
      el.innerHTML = `<p class="error-box">Could not load knowledge: ${escapeHtml(err.message)}</p>`;
    }
  }

  async function openConversationDetail(conversationId) {
    detailOverlay.hidden = false;
    detailBody.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const conv = await fetchJSON(`/import/conversations/${encodeURIComponent(conversationId)}`);
      detailBody.innerHTML = conversationDetailHtml(conv);

      document.getElementById("explorer-detail-search-input").addEventListener(
        "input",
        debounce((e) => {
          document.getElementById("explorer-detail-messages").innerHTML = conversationMessagesHtml(conv.content, e.target.value.trim());
        }, 200)
      );
      document.getElementById("explorer-detail-copy-btn").addEventListener("click", async () => {
        await navigator.clipboard.writeText(JSON.stringify(conv, null, 2));
      });
      document.getElementById("explorer-detail-export-btn").addEventListener("click", () => exportConversation(conv.id));
      document.getElementById("explorer-detail-delete-btn").addEventListener("click", () => {
        deleteConversationWithConfirm(conv.id, () => {
          detailOverlay.hidden = true;
          if (parseHash().view === "explorer") runExplorerUniversalSearch(explorerUniversalQuery);
        });
      });
      document.getElementById("explorer-detail-view-graph-btn").addEventListener("click", () => {
        detailOverlay.hidden = true;
        navigate("conversation-graph", conv.id);
      });

      const extractBtn = document.getElementById("explorer-detail-extract-btn");
      const extractStatus = document.getElementById("explorer-detail-extract-status");
      extractBtn.addEventListener("click", async () => {
        extractBtn.disabled = true;
        extractBtn.textContent = "Extracting…";
        try {
          const run = await fetchJSON(`/extraction/conversations/${encodeURIComponent(conv.id)}/run`, { method: "POST" });
          extractStatus.textContent = `Found ${run.total_found} (new ${run.created}, updated ${run.updated}, unchanged ${run.unchanged})`;
          await loadConversationKnowledge(conv.id);
          if (parseHash().view === "explorer") runExplorerUniversalSearch(explorerUniversalQuery);
        } catch (err) {
          extractStatus.textContent = `Extraction failed: ${err.message}`;
        } finally {
          extractBtn.disabled = false;
          extractBtn.textContent = "Extract Knowledge";
        }
      });

      loadConversationKnowledge(conv.id);
    } catch (err) {
      detailBody.innerHTML = `<p class="error-box">Could not load conversation: ${escapeHtml(err.message)}</p>`;
    }
  }

  // =======================================================================
  // PROJECT HUB (Sprint C3): everything about one project -- Overview,
  // Sessions, Snapshots, Assets, Knowledge, Recent Activity, Commits,
  // Recommendations -- composed server-side from existing services (`GET
  // /explorer/project/{id}`, see `app.explorer.service.project_hub`).
  // Presentation only; no recomputation of anything shown here.
  // =======================================================================

  // Sprint C8 (Project Ecosystem Engine): clean cards, never a graph
  // visualization -- each name links to the related project via the
  // relationship's own `source_project`/`target_project` reference.
  function ecoProjectRefNav(ref) {
    if (!ref) return "";
    return ref.item_id
      ? `data-nav="dproject" data-nav-param="${escapeHtml(ref.item_id)}"`
      : `data-nav="project" data-nav-param="${escapeHtml(ref.canonical_project_id || "")}"`;
  }

  function ecoNameListHtml(rels, otherSideKey) {
    if (!rels.length) return '<p class="muted u-fs-12">None detected.</p>';
    const seen = new Set();
    const names = [];
    rels.forEach((r) => {
      const ref = r[otherSideKey];
      if (!ref || seen.has(ref.display_name)) return;
      seen.add(ref.display_name);
      names.push(ref);
    });
    return `<ul class="u-fs-12">${names.map((ref) => `<li class="u-clickable" ${ecoProjectRefNav(ref)}>${escapeHtml(ref.display_name)}</li>`).join("")}</ul>`;
  }

  function phubEcosystemSectionHtml(ecosystem) {
    if (!ecosystem) return "";
    const impact = ecosystem.impact_summary || {};
    const riskVariant = { high: "critical", medium: "warning", low: "healthy", none: "" }[impact.risk] || "";
    return `
      <div class="page-section">
        <div class="section-heading"><h3>Project Ecosystem</h3></div>
        <div class="card-grid">
          <div class="card">
            <p class="card-title">Dependencies</p>
            ${ecoNameListHtml(ecosystem.dependencies, "target_project")}
          </div>
          <div class="card">
            <p class="card-title">Consumers</p>
            ${ecoNameListHtml(ecosystem.consumers, "source_project")}
          </div>
          <div class="card">
            <p class="card-title">Blocked By</p>
            ${ecoNameListHtml(ecosystem.blocked_by, "target_project")}
          </div>
          <div class="card">
            <p class="card-title">Blocks</p>
            ${ecoNameListHtml(ecosystem.blocks, "target_project")}
          </div>
          <div class="card">
            <p class="card-title">Shared Assets</p>
            <p class="u-fs-26">${ecosystem.shared_assets.length}</p>
          </div>
          <div class="card">
            <p class="card-title">Shared Prompts</p>
            <p class="u-fs-26">${ecosystem.shared_prompts.length}</p>
          </div>
          <div class="card">
            <p class="card-title">Shared Knowledge</p>
            <p class="u-fs-26">${ecosystem.shared_knowledge.length}</p>
          </div>
          <div class="card">
            <p class="card-title">Shared Documentation</p>
            <p class="u-fs-26">${ecosystem.shared_documents.length}</p>
          </div>
          <div class="card">
            <p class="card-title">Impact</p>
            ${riskVariant ? badgeHtml(impact.risk, riskVariant) : '<span class="muted">none</span>'}
            <p class="card-muted u-fs-12 u-mt-1">${impact.affected_projects.length} affected project(s) &middot; ${Math.round((impact.confidence || 0) * 100)}% confidence</p>
          </div>
        </div>
      </div>`;
  }

  // Sprint C9 (Impact Analysis Engine): concise cards only, never a
  // diagram -- Overall Risk, Affected Projects, Top Reasons, Recommended
  // Actions, Evidence.
  function phubImpactAnalysisSectionHtml(impact) {
    if (!impact) return "";
    const riskVariant = { critical: "critical", high: "critical", medium: "warning", low: "healthy", none: "" }[impact.overall_risk] || "";
    const affected = impact.affected_projects || [];
    return `
      <div class="page-section">
        <div class="section-heading"><h3>Impact Analysis</h3></div>
        <div class="card-grid">
          <div class="card">
            <p class="card-title">Overall Risk</p>
            ${riskVariant ? badgeHtml(impact.overall_risk, riskVariant) : '<span class="muted">none</span>'}
            <p class="card-muted u-fs-12 u-mt-1">${Math.round((impact.confidence || 0) * 100)}% confidence</p>
          </div>
          <div class="card">
            <p class="card-title">Affected Projects <span class="badge">${affected.length}</span></p>
            ${
              affected.length
                ? `<ul class="u-fs-12">${affected.map((ref) => `<li class="u-clickable" ${ecoProjectRefNav(ref)}>${escapeHtml(ref.display_name)}</li>`).join("")}</ul>`
                : '<p class="muted u-fs-12">None detected.</p>'
            }
          </div>
          <div class="card">
            <p class="card-title">Top Reasons</p>
            ${
              (impact.evidence || []).length
                ? `<ul class="u-fs-12">${impact.evidence.slice(0, 3).map((e) => `<li>${escapeHtml(e)}</li>`).join("")}</ul>`
                : '<p class="muted u-fs-12">None recorded.</p>'
            }
          </div>
          <div class="card">
            <p class="card-title">Recommended Actions</p>
            <ul class="u-fs-12">${(impact.recommended_actions || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
          </div>
        </div>
      </div>`;
  }

  function phubListSectionHtml(title, items, renderItem, emptyText) {
    return `
      <div class="page-section">
        <div class="section-heading"><h3>${escapeHtml(title)} <span class="badge">${items.length}</span></h3></div>
        ${items.length ? `<ul class="activity-list">${items.map(renderItem).join("")}</ul>` : `<p class="muted">${escapeHtml(emptyText)}</p>`}
      </div>`;
  }

  async function renderProjectHubPage(projectId) {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading Project Hub…</p>';
    let hub;
    try {
      hub = await fetchJSON(`/explorer/project/${encodeURIComponent(projectId)}`);
    } catch (err) {
      viewRoot.innerHTML = `<p class="error-box">Could not load project: ${escapeHtml(err.message)}</p>`;
      return;
    }
    const ctx = hub.overview;
    const na = ctx.next_action || {};
    const resumeAvailable = ctx.resume_state && ctx.resume_state.available;

    viewRoot.innerHTML = `
      <div class="section-heading">
        <h2>${escapeHtml(ctx.display_name)} ${ctx.health ? healthBadge(ctx.health_score, ctx.health) : ""}</h2>
        <button type="button" class="btn btn-primary" data-resume-work-item="${escapeHtml(ctx.item_id || "")}" ${resumeAvailable ? "" : "disabled"}>&#9654; Resume Work</button>
      </div>
      <div class="card page-section">
        <p class="card-muted">Overview</p>
        <p><strong>Status:</strong> ${escapeHtml(ctx.status || "—")} &middot; <strong>Workspace:</strong> ${escapeHtml(ctx.workspace || "—")}</p>
        <p><strong>Next Action:</strong> ${na.text ? escapeHtml(na.text) : NOT_YET_DEFINED}</p>
        <p><strong>Last Activity:</strong> ${formatDate(ctx.latest_activity)}</p>
      </div>
      ${phubListSectionHtml(
        "Sessions",
        hub.sessions,
        (s) => `<li>${assistantBadge(s.assistant)} ${escapeHtml(s.title || "(untitled session)")} <span class="card-muted u-fs-12">— ${formatDate(s.last_used_at || s.started_at)}</span></li>`,
        "No AI Sessions yet."
      )}
      ${phubListSectionHtml(
        "Snapshots",
        hub.snapshots,
        (s) => `<li>${escapeHtml(s.summary || s.accomplishments || "(no summary)")} <span class="card-muted u-fs-12">— ${formatDate(s.created_at)}</span></li>`,
        "No snapshots yet."
      )}
      <div class="page-section">
        <div class="section-heading">
          <h3>Assets <span class="badge">${hub.assets_summary.count}</span></h3>
          <button type="button" class="link-btn" data-nav="assets" data-nav-param="${escapeHtml(ctx.id)}">Open in Assets &rarr;</button>
        </div>
        ${
          hub.assets_summary.count
            ? `<p class="card-muted u-fs-12">${hub.assets_summary.reusable_count} reusable &middot; ${Object.entries(hub.assets_summary.by_category).map(([cat, n]) => `${n} ${escapeHtml(cat)}`).join(", ")}</p>
               <ul class="activity-list">${hub.assets.slice(0, 5).map((a) => `<li class="u-clickable" data-asset-preview="${escapeHtml(a.asset_id)}"><span class="badge">${escapeHtml(a.category)}</span> ${escapeHtml(a.filename)}</li>`).join("")}</ul>`
            : '<p class="muted">No assets detected in adopted projects.</p>'
        }
      </div>
      ${phubListSectionHtml(
        "Knowledge",
        hub.knowledge,
        (k) => `<li>${escapeHtml(k.project)}: ${k.count} card(s)</li>`,
        "Knowledge has not been imported yet."
      )}
      ${phubListSectionHtml(
        "Recent Activity",
        hub.recent_activity,
        (e) => `<li>${escapeHtml(e.summary)} <span class="card-muted u-fs-12">— ${formatDate(e.timestamp)}</span></li>`,
        "No recent activity yet."
      )}
      ${phubListSectionHtml(
        "Commits",
        hub.commits,
        (c) => `<li>${escapeHtml((c.message || "").split("\n")[0])} <span class="card-muted u-fs-12">— ${formatDate(c.date)}</span></li>`,
        "No commits detected."
      )}
      ${phubListSectionHtml(
        "Recommendations",
        hub.recommendations,
        (r) => `<li>${escapeHtml(r.title)} <span class="card-muted u-fs-12">— ${escapeHtml(r.reason || "")}</span></li>`,
        "Nothing needs attention right now."
      )}
      ${phubEcosystemSectionHtml(hub.ecosystem)}
      ${phubImpactAnalysisSectionHtml(hub.impact_analysis)}
    `;
    viewRoot.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
      if (btn.dataset.resumeWorkItem) btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
    });
    viewRoot.querySelectorAll("[data-asset-preview]").forEach((el) => {
      el.addEventListener("click", () => openAssetDetail(el.dataset.assetPreview));
    });
  }

  // =======================================================================
  // ADVISOR PAGE
  // =======================================================================

  // Result types the Advisor's search (Sprint 6) supports, in display
  // order. Values match app.advisor.search_models.RESULT_TYPES exactly.
  const ADVISOR_SEARCH_TYPES = [
    ["Conversation", "Conversations"],
    ["Project", "Projects"],
    ["Person", "People"],
    ["Task", "Tasks"],
    ["Decision", "Decisions"],
    ["Idea", "Ideas"],
    ["Document", "Documents"],
    ["Asset", "Assets"],
  ];

  function advisorSearchResultHtml(r) {
    return `
      <div class="card u-mb-2">
        <div class="u-flex-between">
          <div>
            <span class="badge">${escapeHtml(r.object_type)}</span>
            <strong>${escapeHtml(r.name)}</strong>
          </div>
          <span class="card-muted">${formatDate(r.date)}</span>
        </div>
        ${r.conversation_title && r.object_type !== "Conversation" ? `<p class="card-muted">In: ${escapeHtml(r.conversation_title)}</p>` : ""}
        ${r.confidence != null ? `<p class="card-muted">Confidence: ${Math.round(r.confidence * 100)}%</p>` : ""}
        <div class="graph-detail-actions">
          ${r.conversation_id ? `<button type="button" class="btn btn-sm" data-advisor-open-conversation="${escapeHtml(r.conversation_id)}">Open Conversation</button>` : ""}
          <button type="button" class="btn btn-sm" data-advisor-open-graph="${escapeHtml(r.graph_node_id)}" data-advisor-conversation="${escapeHtml(r.conversation_id || "")}">Open Graph</button>
        </div>
      </div>`;
  }

  function wireAdvisorSearch() {
    const input = document.getElementById("advisor-search-input");
    const typeSelect = document.getElementById("advisor-search-type-select");
    const clearBtn = document.getElementById("advisor-search-clear-btn");
    const resultsEl = document.getElementById("advisor-search-results");

    async function runSearch() {
      const q = input.value.trim();
      const type = typeSelect.value;
      if (!q && !type) {
        resultsEl.innerHTML = '<p class="muted">Type a keyword, or choose a filter to list everything of that type.</p>';
        return;
      }
      resultsEl.innerHTML = '<p class="muted loading-pulse">Searching…</p>';
      try {
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (type) params.set("type", type);
        const data = await fetchJSON(`/advisor/search?${params.toString()}`);
        if (!data.results.length) {
          resultsEl.innerHTML = '<p class="muted">No matches found.</p>';
          return;
        }
        resultsEl.innerHTML = data.results.map(advisorSearchResultHtml).join("");
        resultsEl.querySelectorAll("[data-advisor-open-conversation]").forEach((btn) => {
          btn.addEventListener("click", () => {
            detailOverlay.hidden = true;
            navigate("explorer");
            pendingExplorerConversationFocus = btn.dataset.advisorOpenConversation;
          });
        });
        resultsEl.querySelectorAll("[data-advisor-open-graph]").forEach((btn) => {
          btn.addEventListener("click", () => {
            detailOverlay.hidden = true;
            navigate("conversation-graph", btn.dataset.advisorConversation || undefined);
          });
        });
      } catch (err) {
        resultsEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
      }
    }

    input.addEventListener("input", debounce(runSearch, 250));
    typeSelect.addEventListener("change", runSearch);
    clearBtn.addEventListener("click", () => {
      input.value = "";
      typeSelect.value = "";
      runSearch();
    });

    runSearch();
  }

  async function renderAdvisorPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Advisor</h2></div>
      <div class="card page-section">
        <p class="card-title">Search Knowledge</p>
        <div class="graph-toolbar">
          <input id="advisor-search-input" type="search" placeholder="Search projects, people, tasks, decisions, conversations..." />
          <select id="advisor-search-type-select">
            <option value="">All</option>
            ${ADVISOR_SEARCH_TYPES.map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
          </select>
          <button type="button" class="btn btn-sm" id="advisor-search-clear-btn">Clear</button>
        </div>
        <div id="advisor-search-results" class="advisor-search-results u-mt-3">
          <p class="muted">Type a keyword, or choose a filter to list everything of that type.</p>
        </div>
      </div>
      <div class="card page-section">
        <p class="card-title">Daily Brief</p>
        <pre id="advisor-brief" class="card-muted u-pre-wrap">Loading…</pre>
      </div>
      <div class="page-section">
        <div class="section-heading"><h3>Discovered Projects</h3></div>
        <div id="advisor-discovered-recs"><p class="muted loading-pulse">Loading…</p></div>
      </div>
      <div id="advisor-groups"><p class="muted loading-pulse">Loading recommendations…</p></div>
    `;

    wireAdvisorSearch();
    renderAdvisorDiscoveredRecs();

    const workspaceFilter = workspaceSelect.value;
    const [brief, recs] = await Promise.all([
      fetchJSON(`/advisor/daily-brief${workspaceFilter ? `?workspace=${encodeURIComponent(workspaceFilter)}` : ""}`),
      fetchJSON(`/advisor/recommendations${workspaceFilter ? `?workspace=${encodeURIComponent(workspaceFilter)}` : ""}`),
    ]);

    document.getElementById("advisor-brief").textContent = brief.greeting;

    const groups = {};
    recs.forEach((r) => {
      groups[r.workspace] = groups[r.workspace] || [];
      groups[r.workspace].push(r);
    });

    const groupsEl = document.getElementById("advisor-groups");
    const workspaceNames = Object.keys(groups).sort();
    if (!workspaceNames.length) {
      groupsEl.innerHTML = '<p class="muted">No recommendations right now — nothing needs attention.</p>';
      return;
    }
    groupsEl.innerHTML = workspaceNames
      .map(
        (ws) => `
      <div class="page-section">
        <div class="section-heading"><h3>${escapeHtml(ws)}</h3></div>
        <div class="card-grid-wide" id="advisor-group-${escapeHtml(ws).replace(/\W+/g, "_")}"></div>
      </div>`
      )
      .join("");

    workspaceNames.forEach((ws) => {
      const container = document.getElementById(`advisor-group-${ws.replace(/\W+/g, "_")}`);
      container.innerHTML = groups[ws].map(recommendationCardHtml).join("");
      container.querySelectorAll(".rec-card").forEach((card) => {
        const id = card.dataset.id;
        card.querySelector(".dismiss-btn").addEventListener("click", () => advisorAct(id, "dismiss", card));
        card.querySelector(".complete-btn").addEventListener("click", () => advisorAct(id, "complete", card));
      });
    });
  }

  // Workspace Advisor 2.0 (Sprint 4 §5) -- rule-based recommendations over
  // real discovered/adopted project evidence. A sibling section to the
  // Epic 2 recommendations above, not a replacement: different data
  // source (`/workspace/advisor`), different card shape (project/
  // recommendation/reason/evidence/priority/confidence/action_link
  // rather than Epic 2's RecommendationCandidate), same page.
  function discoveredRecommendationCardHtml(rec) {
    const evidence = (rec.evidence || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("");
    return `
      <div class="card rec-card">
        <div class="rec-card-header">
          <div>
            <p class="rec-card-title">${escapeHtml(rec.project)}: ${escapeHtml(rec.recommendation)}</p>
            <div class="rec-card-meta">
              <span class="badge">Priority ${rec.priority}</span>
              <span class="badge">Confidence ${rec.confidence}</span>
            </div>
          </div>
        </div>
        <div class="rec-card-body">
          <p><strong>Why:</strong> ${escapeHtml(rec.reason)}</p>
          <ul class="graph-detail-edges">${evidence}</ul>
        </div>
        <div class="rec-card-actions">
          <button type="button" class="btn btn-sm btn-primary" data-resume-work-item="${escapeHtml(rec.item_id)}">Resume Work &rarr;</button>
          <a class="link-btn" href="${rec.action_link}">Review &rarr;</a>
        </div>
      </div>`;
  }

  async function renderAdvisorDiscoveredRecs() {
    const el = document.getElementById("advisor-discovered-recs");
    if (!el) return;
    try {
      const recs = await fetchJSON("/workspace/advisor");
      el.innerHTML = recs.length
        ? `<div class="card-grid-wide">${recs.map(discoveredRecommendationCardHtml).join("")}</div>`
        : '<p class="muted">No recommendations right now — nothing needs attention.</p>';
      // Sprint 5 §5: every recommendation links directly to Resume Work.
      el.querySelectorAll("[data-resume-work-item]").forEach((btn) => {
        btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem));
      });
    } catch (err) {
      el.innerHTML = `<p class="error-box">Could not load discovered-project recommendations: ${escapeHtml(err.message)}</p>`;
    }
  }

  function recommendationCardHtml(rec) {
    const evidence = (rec.evidence || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("");
    return `
      <div class="card rec-card" data-id="${escapeHtml(rec.id)}">
        <div class="rec-card-header">
          <div>
            <p class="rec-card-title">${escapeHtml(rec.title)}</p>
            <div class="rec-card-meta">
              <span class="badge">${escapeHtml(rec.recommendation_type)}</span>
              <span class="badge">Effort: ${escapeHtml(rec.estimated_effort)}</span>
              <span class="badge">Priority ${rec.priority_score}</span>
              <span class="badge">Confidence ${rec.confidence_score}</span>
            </div>
          </div>
        </div>
        <div class="rec-card-body">
          <p>${escapeHtml(rec.summary)}</p>
          <p><strong>Why:</strong> ${escapeHtml(rec.reason)}</p>
          <p><strong>Suggested action:</strong> ${escapeHtml(rec.suggested_action)}</p>
          <p><strong>Impact:</strong> ${escapeHtml(rec.impact)}</p>
          <ul class="graph-detail-edges">${evidence}</ul>
        </div>
        <div class="rec-card-actions">
          <button type="button" class="btn btn-sm dismiss-btn">Dismiss</button>
          <button type="button" class="btn btn-sm btn-primary complete-btn">Mark completed</button>
        </div>
      </div>`;
  }

  async function advisorAct(id, action, card) {
    try {
      await fetchJSON(`/advisor/recommendations/${encodeURIComponent(id)}/${action}`, { method: "POST" });
      card.remove();
    } catch (err) {
      console.error(`Could not ${action} recommendation`, err);
    }
  }

  // =======================================================================
  // ASSETS PAGE
  // =======================================================================

  // Sprint 4 §6: a real discovery index (filename/project/path/type/size/
  // modified/category/reusable/duplicate hash) over every adopted
  // project's actual files -- no thumbnails yet, and never copies
  // anything; the filesystem stays the source of truth. Replaces the
  // earlier placeholder that rode on the generic `/graph?node_type=Asset`
  // endpoint (which was never wired to any real file).
  // =======================================================================
  // ASSETS OS (Sprint C4): a visual Asset Library over every real file
  // discovered inside adopted project roots. Presentation only -- every
  // category/reusable/duplicate-group/MIME classification decision is
  // already made server-side (`GET /assets`, `app.assets.service`); this
  // file only renders `AssetRecord` fields and lets the user filter/
  // search/page through an already-shaped response, or set the three
  // user-owned overrides (reusable/category/favorite) via `PATCH /assets/
  // {id}`. Nothing here ever reads a raw filesystem path itself.
  // =======================================================================

  const ASSET_FILTER_CHIPS = [
    { key: "all", label: "All" },
    { key: "reusable", label: "Reusable" },
    { key: "favorites", label: "Favorites" },
    { key: "logos", label: "Logos" },
    { key: "images", label: "Images" },
    { key: "videos", label: "Videos" },
    { key: "documents", label: "Documents" },
    { key: "fonts", label: "Fonts" },
    { key: "duplicates", label: "Duplicates" },
  ];

  const ASSET_TYPE_ICONS = {
    image: "\u{1F5BC}",
    video: "\u{1F3AC}",
    audio: "\u{1F3B5}",
    document: "\u{1F4C4}",
    "design-file": "\u{1F3A8}",
    font: "\u{1F520}",
    other: "\u{1F4E6}",
  };

  let assetsState = {
    q: "",
    filter: "all",
    projectId: "",
    sort: "modified_at",
    sortDir: "desc",
    page: 1,
    pageSize: 60,
    view: localStorage.getItem("roleos-assets-view") || "gallery",
  };
  let assetsAccumulated = [];

  function assetFilterToParams(state) {
    const params = new URLSearchParams({
      q: state.q,
      sort: state.sort,
      sort_dir: state.sortDir,
      page: state.page,
      page_size: state.pageSize,
    });
    if (state.projectId) params.set("project_id", state.projectId);
    if (state.filter === "reusable") params.set("reusable_only", "true");
    if (state.filter === "favorites") params.set("favorites_only", "true");
    if (state.filter === "duplicates") params.set("duplicates_only", "true");
    if (state.filter === "logos") params.set("category", "Logo");
    if (state.filter === "videos") params.set("asset_type", "video");
    if (state.filter === "documents") params.set("asset_type", "document");
    if (state.filter === "fonts") params.set("asset_type", "font");
    if (state.filter === "images") params.set("asset_type", "image");
    return params;
  }

  function assetThumbPlaceholderHtml(a) {
    return `<div class="asset-thumb asset-thumb-placeholder" aria-hidden="true">${ASSET_TYPE_ICONS[a.asset_type] || "\u{1F4E6}"}<span class="asset-thumb-ext">${escapeHtml(a.extension.replace(".", "").toUpperCase())}</span></div>`;
  }

  function assetThumbPlaceholderHtmlFragment(a, message) {
    const wrap = document.createElement("div");
    wrap.innerHTML = `${assetThumbPlaceholderHtml(a)}${message ? `<p class="muted u-fs-12">${escapeHtml(message)}</p>` : ""}`;
    const fragment = document.createDocumentFragment();
    while (wrap.firstChild) fragment.appendChild(wrap.firstChild);
    return fragment;
  }

  // A preview that fails server-side (e.g. an oversized/corrupt image --
  // see app.assets.preview's DecompressionBombError handling) degrades to
  // the same type placeholder client-side, never a broken-image icon.
  function handleAssetThumbError(imgEl, assetType, extension) {
    const placeholder = document.createElement("div");
    placeholder.className = "asset-thumb asset-thumb-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    placeholder.textContent = ASSET_TYPE_ICONS[assetType] || "\u{1F4E6}";
    const extSpan = document.createElement("span");
    extSpan.className = "asset-thumb-ext";
    extSpan.textContent = extension.replace(".", "").toUpperCase();
    placeholder.appendChild(extSpan);
    imgEl.replaceWith(placeholder);
  }

  function assetCardHtml(a) {
    const previewHtml = a.preview_available
      ? `<img src="${escapeHtml(a.preview_url)}" alt="${escapeHtml(a.filename)}" loading="lazy" class="asset-thumb" data-asset-type="${escapeHtml(a.asset_type)}" data-asset-ext="${escapeHtml(a.extension)}" />`
      : assetThumbPlaceholderHtml(a);
    const dims = a.width && a.height ? `${a.width}×${a.height}` : "";
    return `
      <div class="card asset-card" data-asset-card="${escapeHtml(a.asset_id)}">
        <div class="asset-thumb-wrap u-clickable" data-asset-preview="${escapeHtml(a.asset_id)}">
          ${previewHtml}
          ${a.duplicate_group_id ? '<span class="badge badge-warning asset-badge-duplicate">duplicate</span>' : ""}
          ${a.favorite ? '<span class="asset-badge-favorite" aria-label="Favorite">★</span>' : ""}
        </div>
        <p class="card-title u-fs-12 asset-filename" title="${escapeHtml(a.filename)}">${escapeHtml(a.filename)}</p>
        <p class="card-muted u-fs-12">${escapeHtml(a.project || "—")}</p>
        <div class="asset-card-meta u-fs-12">
          <span class="badge">${escapeHtml(a.category)}</span>
          ${a.reusable ? '<span class="badge badge-healthy">reusable</span>' : ""}
        </div>
        <p class="card-muted u-fs-12">${[dims, formatBytes(a.size_bytes), formatDate(a.modified_at)].filter(Boolean).join(" · ")}</p>
      </div>`;
  }

  function assetListRowHtml(a) {
    return `
      <tr data-asset-card="${escapeHtml(a.asset_id)}">
        <td class="u-clickable" data-asset-preview="${escapeHtml(a.asset_id)}">${escapeHtml(a.filename)}</td>
        <td>${escapeHtml(a.project || "—")}</td>
        <td><span class="badge">${escapeHtml(a.category)}</span></td>
        <td>${escapeHtml(a.asset_type)}</td>
        <td>${a.width && a.height ? `${a.width}×${a.height}` : "—"}</td>
        <td>${formatBytes(a.size_bytes)}</td>
        <td>${formatDate(a.modified_at)}</td>
        <td>${a.reusable ? "yes" : "no"}</td>
        <td>${a.duplicate_group_id ? '<span class="badge badge-warning">duplicate</span>' : "—"}</td>
      </tr>`;
  }

  function assetsEmptyStateHtml(state) {
    if (state.q || state.filter !== "all" || state.projectId) {
      return '<p class="muted">No assets match these filters.</p>';
    }
    return `
      <div class="card">
        <p class="muted">No assets detected in adopted projects.</p>
        <button type="button" class="btn btn-sm btn-primary u-mt-2" data-nav="workspace">Open Workspace to adopt one &rarr;</button>
      </div>`;
  }

  async function loadAssetsResults(append) {
    const resultsEl = document.getElementById("assets-results");
    const loadMoreWrap = document.getElementById("assets-load-more-wrap");
    if (!append) {
      assetsAccumulated = [];
      resultsEl.innerHTML = '<p class="muted loading-pulse">Loading…</p>';
    }
    try {
      const data = await fetchJSON(`/assets?${assetFilterToParams(assetsState).toString()}`);
      assetsAccumulated = append ? assetsAccumulated.concat(data.items) : data.items;
      if (!assetsAccumulated.length) {
        resultsEl.innerHTML = assetsEmptyStateHtml(assetsState);
        loadMoreWrap.innerHTML = "";
        return;
      }
      resultsEl.className = assetsState.view === "gallery" ? "asset-gallery-grid" : "";
      resultsEl.innerHTML =
        assetsState.view === "gallery"
          ? assetsAccumulated.map(assetCardHtml).join("")
          : `<table class="explorer-table"><thead><tr><th>Filename</th><th>Project</th><th>Category</th><th>Type</th><th>Dimensions</th><th>Size</th><th>Modified</th><th>Reusable</th><th>Duplicate</th></tr></thead><tbody>${assetsAccumulated.map(assetListRowHtml).join("")}</tbody></table>`;
      loadMoreWrap.innerHTML =
        data.page < data.total_pages
          ? `<button type="button" class="btn btn-sm" id="assets-load-more-btn">Load more (${assetsAccumulated.length} of ${data.total})</button>`
          : `<p class="muted u-fs-12">${data.total} asset${data.total === 1 ? "" : "s"}</p>`;
      const loadMoreBtn = document.getElementById("assets-load-more-btn");
      if (loadMoreBtn) {
        loadMoreBtn.addEventListener("click", () => {
          assetsState.page += 1;
          loadAssetsResults(true);
        });
      }
      wireAssetCardClicks(resultsEl);
    } catch (err) {
      resultsEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
    }
  }

  function wireAssetCardClicks(container) {
    container.querySelectorAll("[data-asset-preview]").forEach((el) => {
      el.addEventListener("click", () => openAssetDetail(el.dataset.assetPreview));
    });
    container.querySelectorAll("img.asset-thumb").forEach((img) => {
      img.addEventListener("error", () => handleAssetThumbError(img, img.dataset.assetType, img.dataset.assetExt), {
        once: true,
      });
    });
  }

  async function loadAssetsProjectFilterOptions() {
    const select = document.getElementById("assets-project-select");
    if (!select) return;
    try {
      const projects = await fetchJSON("/workspace/discovered?view=top_level");
      select.innerHTML =
        '<option value="">All projects</option>' +
        projects
          .filter((p) => p.adopted)
          .map((p) => `<option value="${escapeHtml(p.canonical_project_id || "")}">${escapeHtml(p.name)}</option>`)
          .join("");
    } catch (err) {
      console.error("Could not load projects for Assets filter", err);
    }
  }

  async function renderAssetsPage(initialProjectId) {
    assetsState = { ...assetsState, q: "", filter: "all", projectId: initialProjectId || "", page: 1 };
    viewRoot.innerHTML = `
      <div class="section-heading">
        <h2>Assets</h2>
        <div class="asset-view-toggle" role="group" aria-label="View mode">
          <button type="button" class="btn btn-sm ${assetsState.view === "gallery" ? "btn-primary" : ""}" id="assets-view-gallery-btn" aria-pressed="${assetsState.view === "gallery"}">Gallery</button>
          <button type="button" class="btn btn-sm ${assetsState.view === "list" ? "btn-primary" : ""}" id="assets-view-list-btn" aria-pressed="${assetsState.view === "list"}">List</button>
        </div>
      </div>
      <p class="card-muted u-mb-2">Real files discovered inside your adopted projects. Nothing is ever copied, moved, renamed, edited, or deleted.</p>
      <div class="card page-section">
        <input id="assets-search-input" type="search" placeholder="Search filename, category, project, extension, path..." aria-label="Search assets" />
        <div id="assets-filter-chips" class="workspace-filter-tabs u-mt-2" role="group" aria-label="Filter"></div>
        <div class="graph-toolbar u-mt-2">
          <select id="assets-project-select" aria-label="Filter by project"><option value="">All projects</option></select>
          <select id="assets-sort-select" aria-label="Sort by">
            <option value="modified_at">Sort: Modified</option>
            <option value="filename">Sort: Filename</option>
            <option value="size_bytes">Sort: Size</option>
            <option value="project">Sort: Project</option>
          </select>
        </div>
      </div>
      <div id="assets-results"><p class="muted loading-pulse">Loading…</p></div>
      <div id="assets-load-more-wrap" class="u-mt-3 u-text-center"></div>
    `;

    document.getElementById("assets-filter-chips").innerHTML = ASSET_FILTER_CHIPS.map(
      (f) =>
        `<button type="button" class="btn btn-sm ${f.key === assetsState.filter ? "btn-primary" : ""}" data-asset-filter="${f.key}">${escapeHtml(f.label)}</button>`
    ).join("");
    document.querySelectorAll("[data-asset-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        assetsState.filter = btn.dataset.assetFilter;
        assetsState.page = 1;
        document.querySelectorAll("[data-asset-filter]").forEach((b) => b.classList.toggle("btn-primary", b === btn));
        loadAssetsResults(false);
      });
    });

    document.getElementById("assets-search-input").addEventListener(
      "input",
      debounce((e) => {
        assetsState.q = e.target.value.trim();
        assetsState.page = 1;
        loadAssetsResults(false);
      }, 250)
    );
    document.getElementById("assets-project-select").addEventListener("change", (e) => {
      assetsState.projectId = e.target.value;
      assetsState.page = 1;
      loadAssetsResults(false);
    });
    document.getElementById("assets-sort-select").addEventListener("change", (e) => {
      assetsState.sort = e.target.value;
      assetsState.page = 1;
      loadAssetsResults(false);
    });
    document.getElementById("assets-view-gallery-btn").addEventListener("click", () => {
      assetsState.view = "gallery";
      localStorage.setItem("roleos-assets-view", "gallery");
      renderAssetsPage(assetsState.projectId);
    });
    document.getElementById("assets-view-list-btn").addEventListener("click", () => {
      assetsState.view = "list";
      localStorage.setItem("roleos-assets-view", "list");
      renderAssetsPage(assetsState.projectId);
    });

    if (initialProjectId) document.getElementById("assets-project-select").value = initialProjectId;

    loadAssetsProjectFilterOptions().then(() => {
      if (initialProjectId) document.getElementById("assets-project-select").value = initialProjectId;
    });
    await loadAssetsResults(false);
  }

  // -----------------------------------------------------------------------
  // Asset Detail panel -- shared by the Assets gallery and Explorer's
  // "Open Asset" action (§10: an Explorer asset result opens this same
  // panel, never a second/legacy representation).
  // -----------------------------------------------------------------------

  function assetDetailActionsHtml(a) {
    const openProjectAttrs = a.discovery_item_id
      ? `data-nav="dproject" data-nav-param="${escapeHtml(a.discovery_item_id)}"`
      : a.canonical_project_id
        ? `data-nav="project" data-nav-param="${escapeHtml(a.canonical_project_id)}"`
        : "";
    return `
      <div class="graph-detail-actions u-mt-3">
        <button type="button" class="btn btn-sm btn-primary" id="asset-detail-open-file-btn">Open File</button>
        <button type="button" class="btn btn-sm" id="asset-detail-open-folder-btn">Open Folder</button>
        <button type="button" class="btn btn-sm" id="asset-detail-copy-path-btn">Copy Path</button>
        ${openProjectAttrs ? `<button type="button" class="btn btn-sm" ${openProjectAttrs}>Open Project</button>` : ""}
      </div>`;
  }

  function assetDetailPreviewHtml(a) {
    if (a.extension === ".svg" || (a.preview_available && a.asset_type === "image")) {
      return `<img src="${escapeHtml(a.preview_url || `/assets/${a.asset_id}/file`)}" alt="${escapeHtml(a.filename)}" class="asset-detail-preview" />`;
    }
    if (a.asset_type === "video") {
      return `<video controls class="asset-detail-preview" src="/assets/${escapeHtml(a.asset_id)}/file"></video>`;
    }
    if (a.asset_type === "audio") {
      return `<audio controls class="u-full-width" src="/assets/${escapeHtml(a.asset_id)}/file"></audio>`;
    }
    return `<div class="asset-thumb asset-thumb-placeholder asset-detail-placeholder" aria-hidden="true">${ASSET_TYPE_ICONS[a.asset_type] || "\u{1F4E6}"}<span class="asset-thumb-ext">${escapeHtml(a.extension.replace(".", "").toUpperCase())}</span></div>
      <p class="muted u-fs-12">Preview unavailable for this format.</p>`;
  }

  function assetDetailHtml(a) {
    const dims = a.width && a.height ? `${a.width} × ${a.height}` : "Not available";
    const duration = a.duration_seconds ? `${Math.round(a.duration_seconds)}s` : "Not available";
    const dupMembers = a.duplicate_members || [];
    return `
      <h3 id="detail-title">${escapeHtml(a.filename)}</h3>
      ${assetDetailPreviewHtml(a)}
      ${assetDetailActionsHtml(a)}
      <table class="kv-table u-mt-3">
        <tr><th>Project</th><td>${escapeHtml(a.project || "—")}</td></tr>
        <tr><th>Category</th><td><span class="badge">${escapeHtml(a.category)}</span></td></tr>
        <tr><th>Type</th><td>${escapeHtml(a.asset_type)} (${escapeHtml(a.mime_type)})</td></tr>
        <tr><th>Dimensions</th><td>${dims}</td></tr>
        <tr><th>Duration</th><td>${duration}</td></tr>
        <tr><th>Size</th><td>${formatBytes(a.size_bytes)}</td></tr>
        <tr><th>Modified</th><td>${formatDate(a.modified_at)}</td></tr>
        <tr><th>Path</th><td class="card-muted u-fs-12">${escapeHtml(a.relative_path)}</td></tr>
        <tr><th>Reusable</th><td><label><input type="checkbox" id="asset-detail-reusable-toggle" ${a.reusable ? "checked" : ""} /> Reusable</label></td></tr>
        <tr><th>Favorite</th><td><label><input type="checkbox" id="asset-detail-favorite-toggle" ${a.favorite ? "checked" : ""} /> Favorite</label></td></tr>
      </table>
      ${
        dupMembers.length
          ? `<div class="u-mt-3"><p class="card-title u-fs-12">Duplicate of ${dupMembers.length} other file(s)</p><ul class="activity-list">${dupMembers.map((m) => `<li>${escapeHtml(m.filename)} <span class="card-muted u-fs-12">— ${escapeHtml(m.project || "")} · ${escapeHtml(m.relative_path)}</span></li>`).join("")}</ul></div>`
          : ""
      }
      <div id="asset-detail-status" class="muted u-fs-12 u-mt-2"></div>
    `;
  }

  async function openAssetDetail(assetId) {
    detailOverlay.hidden = false;
    detailBody.innerHTML = '<p class="muted">Loading…</p>';
    let asset;
    try {
      asset = await fetchJSON(`/assets/${encodeURIComponent(assetId)}`);
    } catch (err) {
      detailBody.innerHTML = `<p class="error-box">${escapeHtml(err.message === "Not Found" ? "Source file no longer exists or asset not found." : err.message)}</p>`;
      return;
    }
    detailBody.innerHTML = assetDetailHtml(asset);
    const previewImg = detailBody.querySelector("img.asset-detail-preview");
    if (previewImg) {
      previewImg.addEventListener(
        "error",
        () => {
          previewImg.replaceWith(assetThumbPlaceholderHtmlFragment(asset, "Preview unavailable for this format."));
        },
        { once: true }
      );
    }

    document.getElementById("asset-detail-open-file-btn").addEventListener("click", async () => {
      const statusEl = document.getElementById("asset-detail-status");
      try {
        await fetchJSON(`/assets/${encodeURIComponent(assetId)}/open-file`, { method: "POST" });
      } catch (err) {
        statusEl.textContent = `Could not open file: ${err.message}`;
      }
    });
    document.getElementById("asset-detail-open-folder-btn").addEventListener("click", async () => {
      const statusEl = document.getElementById("asset-detail-status");
      try {
        await fetchJSON(`/assets/${encodeURIComponent(assetId)}/open-folder`, { method: "POST" });
      } catch (err) {
        statusEl.textContent = `Could not open folder: ${err.message}`;
      }
    });
    document.getElementById("asset-detail-copy-path-btn").addEventListener("click", async () => {
      const statusEl = document.getElementById("asset-detail-status");
      try {
        await navigator.clipboard.writeText(asset.absolute_path);
        statusEl.textContent = "Path copied.";
      } catch (err) {
        statusEl.textContent = `Could not copy path: ${err.message}`;
      }
    });
    document.getElementById("asset-detail-reusable-toggle").addEventListener("change", async (e) => {
      try {
        await postJSON(`/assets/${encodeURIComponent(assetId)}`, { reusable: e.target.checked }, "PATCH");
      } catch (err) {
        document.getElementById("asset-detail-status").textContent = `Could not save: ${err.message}`;
      }
    });
    document.getElementById("asset-detail-favorite-toggle").addEventListener("change", async (e) => {
      try {
        await postJSON(`/assets/${encodeURIComponent(assetId)}`, { favorite: e.target.checked }, "PATCH");
      } catch (err) {
        document.getElementById("asset-detail-status").textContent = `Could not save: ${err.message}`;
      }
    });
  }

  // =======================================================================
  // SETTINGS PAGE
  // =======================================================================

  function formatBytes(bytes) {
    if (bytes === null || bytes === undefined) return "not found";
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB"];
    let value = bytes / 1024;
    let i = 0;
    while (value >= 1024 && i < units.length - 1) {
      value /= 1024;
      i += 1;
    }
    return `${value.toFixed(1)} ${units[i]}`;
  }

  async function renderSettingsPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Settings</h2></div>
      <div class="home-grid">
        <div>
          <div class="card">
            <p class="card-title">General</p>
            <table class="kv-table" id="settings-general"><tr><td class="muted">Loading…</td></tr></table>
          </div>
          <div class="card u-mt-4">
            <p class="card-title">System status</p>
            <table class="kv-table" id="settings-system"><tr><td class="muted">Loading…</td></tr></table>
          </div>
          <div class="card u-mt-4">
            <p class="card-title">About</p>
            <table class="kv-table" id="settings-about"><tr><td class="muted">Loading…</td></tr></table>
          </div>
        </div>
        <div>
          <div class="card" id="settings-export-panel">
            <p class="card-title">Export configuration</p>
            <p class="muted">Download the current general settings and version info as JSON.</p>
            <button type="button" class="btn btn-sm" id="settings-export-btn">Export</button>
          </div>
          <div class="card u-mt-4" id="settings-import-panel">
            <p class="card-title">Import configuration</p>
            <p class="muted">Upload a previously exported configuration file to preview which environment variables to set. ROLE OS cannot apply settings to a running server — you'll need to set them and restart.</p>
            <form id="settings-import-form">
              <input type="file" id="settings-import-file-input" accept=".json" required />
              <button type="submit" class="btn btn-sm" id="settings-import-submit-btn">Preview</button>
            </form>
            <div id="settings-import-status" class="u-mt-4"></div>
          </div>
          <div class="card u-mt-4">
            <p class="card-title">Maintenance</p>
            <table class="kv-table" id="settings-maintenance"><tr><td class="muted">Loading…</td></tr></table>
            <div class="u-mt-4">
              <button type="button" class="btn btn-sm" id="settings-rebuild-graph-btn">Rebuild graph</button>
              <button type="button" class="btn btn-sm" id="settings-clear-cache-btn">Clear cache</button>
            </div>
            <div id="settings-maintenance-status" class="u-mt-4"></div>
          </div>
        </div>
      </div>
      <p class="muted u-mt-4">
        ROLE OS Command Center is a UI-only layer over the existing Builder,
        Knowledge Engine, Project Intelligence, Advisor, and Knowledge Graph
        APIs — nothing here writes to a database directly.
      </p>
    `;

    const overview = await fetchJSON("/settings");

    document.getElementById("settings-general").innerHTML = `
      <tr><th>App name</th><td>${escapeHtml(overview.general.app_name)}</td></tr>
      <tr><th>Version</th><td>${escapeHtml(overview.general.app_version)}</td></tr>
      <tr><th>Default import path</th><td>${escapeHtml(overview.general.default_import_path || "not set")}</td></tr>
      <tr><th>Search result limit</th><td>${overview.general.search_result_limit}</td></tr>
      ${Object.entries(overview.general.database_paths)
        .map(([name, path]) => `<tr><th>${escapeHtml(name)} DB path</th><td>${escapeHtml(path)}</td></tr>`)
        .join("")}
    `;

    document.getElementById("settings-system").innerHTML = `
      <tr><th>Total conversations</th><td>${overview.system.total_conversations}</td></tr>
      <tr><th>Total extracted objects</th><td>${overview.system.total_extracted_objects}</td></tr>
      <tr><th>Database location</th><td>${escapeHtml(overview.system.database_location)}</td></tr>
      ${Object.entries(overview.system.database_sizes_bytes)
        .map(([name, size]) => `<tr><th>${escapeHtml(name)} DB size</th><td>${formatBytes(size)}</td></tr>`)
        .join("")}
      <tr><th>Last import</th><td>${escapeHtml(overview.system.last_import || "never")}</td></tr>
      <tr><th>Last extraction</th><td>${escapeHtml(overview.system.last_extraction || "never")}</td></tr>
    `;

    document.getElementById("settings-about").innerHTML = `
      <tr><th>Version</th><td>${escapeHtml(overview.about.version)}</td></tr>
      <tr><th>Commit</th><td>${escapeHtml(overview.about.commit || "unknown")}</td></tr>
      <tr><th>Build date</th><td>${escapeHtml(overview.about.build_date || "not stamped")}</td></tr>
      <tr><th>License</th><td>${escapeHtml(overview.about.license)}</td></tr>
    `;

    document.getElementById("settings-maintenance").innerHTML = `
      <tr><th>Settings cache</th><td>${overview.maintenance.cache_exists ? "Active" : "Empty"}</td></tr>
      <tr><th>Description</th><td>${escapeHtml(overview.maintenance.cache_description)}</td></tr>
    `;

    wireSettingsActions();
  }

  function wireSettingsActions() {
    document.getElementById("settings-export-btn").addEventListener("click", () => {
      window.location.href = "/settings/export";
    });

    const form = document.getElementById("settings-import-form");
    const fileInput = document.getElementById("settings-import-file-input");
    const submitBtn = document.getElementById("settings-import-submit-btn");
    const statusEl = document.getElementById("settings-import-status");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const file = fileInput.files[0];
      if (!file) return;

      submitBtn.disabled = true;
      submitBtn.textContent = "Validating…";
      statusEl.innerHTML = '<p class="muted loading-pulse">Validating configuration…</p>';

      const body = new FormData();
      body.append("file", file);

      try {
        const result = await fetchJSON("/settings/import", { method: "POST", body });
        const envRows = Object.entries(result.env_vars_to_set)
          .map(([name, value]) => `<tr><th>${escapeHtml(name)}</th><td>${escapeHtml(value)}</td></tr>`)
          .join("");
        statusEl.innerHTML = `
          <p class="u-mt-0">${escapeHtml(result.note)}</p>
          <table class="kv-table">${envRows || '<tr><td class="muted">No recognized fields found.</td></tr>'}</table>
        `;
      } catch (err) {
        statusEl.innerHTML = `<p class="error-box">Import failed: ${escapeHtml(err.message)}</p>`;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Preview";
        form.reset();
      }
    });

    const maintenanceStatusEl = document.getElementById("settings-maintenance-status");

    document.getElementById("settings-rebuild-graph-btn").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      maintenanceStatusEl.innerHTML = '<p class="muted loading-pulse">Rebuilding graph…</p>';
      try {
        const result = await fetchJSON("/settings/maintenance/rebuild-graph", { method: "POST" });
        maintenanceStatusEl.innerHTML = `<p class="u-mt-0">Rebuilt: ${result.nodes} nodes, ${result.edges} edges.</p>`;
      } catch (err) {
        maintenanceStatusEl.innerHTML = `<p class="error-box">Rebuild failed: ${escapeHtml(err.message)}</p>`;
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById("settings-clear-cache-btn").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      maintenanceStatusEl.innerHTML = '<p class="muted loading-pulse">Clearing cache…</p>';
      try {
        await fetchJSON("/settings/maintenance/clear-cache", { method: "POST" });
        maintenanceStatusEl.innerHTML = '<p class="u-mt-0">Cache cleared.</p>';
      } catch (err) {
        maintenanceStatusEl.innerHTML = `<p class="error-box">Clear cache failed: ${escapeHtml(err.message)}</p>`;
      } finally {
        btn.disabled = false;
      }
    });
  }

  // =======================================================================
  // GRAPH PAGE (full screen, zoom/pan, expand/collapse, path, impact, filters)
  // =======================================================================

  let pendingGraphFocus = null;

  async function renderGraphPage() {
    viewRoot.innerHTML = `
      <div class="graph-page">
        <div class="graph-toolbar">
          <input id="graph-search-input" type="search" placeholder="Search nodes..." />
          <select id="graph-node-type-select"><option value="">All node types</option></select>
          <select id="graph-workspace-select"><option value="">All workspaces</option></select>
          <select id="graph-relationship-select"><option value="">All relationships</option></select>
          <button id="graph-highlight-dependencies" type="button" class="btn btn-sm">Highlight dependencies</button>
          <button id="graph-highlight-capabilities" type="button" class="btn btn-sm">Highlight capabilities</button>
          <button id="graph-impact-btn" type="button" class="btn btn-sm">Impact analysis</button>
          <button id="graph-zoom-in" type="button" class="btn btn-sm">+</button>
          <button id="graph-zoom-out" type="button" class="btn btn-sm">-</button>
          <button id="graph-reset-btn" type="button" class="btn btn-sm">Reset view</button>
        </div>
        <div class="graph-page-body">
          <div class="graph-page-canvas-wrap">
            <svg id="graph-canvas"></svg>
            <p id="graph-empty-msg" class="muted" hidden>No graph data yet. Create some Projects to see them here.</p>
          </div>
          <aside id="graph-detail-panel" class="graph-page-sidebar graph-detail-panel">
            <p class="muted">Click a node to see its details, expand its neighbors, or use it as a path/impact endpoint.</p>
          </aside>
        </div>
        <div id="graph-path-bar" class="card muted u-pad-sm">Pick a source and target node (via the detail panel) to highlight the shortest path between them.</div>
      </div>
    `;

    const els = {
      svg: document.getElementById("graph-canvas"),
      emptyMsg: document.getElementById("graph-empty-msg"),
      detailPanel: document.getElementById("graph-detail-panel"),
      searchInput: document.getElementById("graph-search-input"),
      nodeTypeSelect: document.getElementById("graph-node-type-select"),
      workspaceSelect: document.getElementById("graph-workspace-select"),
      relationshipSelect: document.getElementById("graph-relationship-select"),
      highlightDepsBtn: document.getElementById("graph-highlight-dependencies"),
      highlightCapsBtn: document.getElementById("graph-highlight-capabilities"),
      impactBtn: document.getElementById("graph-impact-btn"),
      zoomInBtn: document.getElementById("graph-zoom-in"),
      zoomOutBtn: document.getElementById("graph-zoom-out"),
      resetBtn: document.getElementById("graph-reset-btn"),
      pathBar: document.getElementById("graph-path-bar"),
    };

    const view = createGraphView(els.svg, { width: 900, height: 560, interactive: true, emptyMsgEl: els.emptyMsg });

    let pathSource = null;
    let pathTarget = null;

    function renderDetailPanel(node, edges, id) {
      const dataRows = Object.entries(node.data || {})
        .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(JSON.stringify(v))}</td></tr>`)
        .join("");
      const edgeRows = edges
        .map((e) => {
          const otherId = e.source === id ? e.target : e.source;
          const otherNode = view.getNode(otherId);
          const label = otherNode ? otherNode.node.label : otherId;
          const arrow = e.source === id ? "&rarr;" : "&larr;";
          return `<li>${escapeHtml(e.type)} ${arrow} ${escapeHtml(label)}</li>`;
        })
        .join("");

      els.detailPanel.innerHTML = `
        <h3>${escapeHtml(node.label)}</h3>
        <p class="badge">${escapeHtml(node.type)}</p>
        <table class="graph-detail-table">${dataRows}</table>
        <h4>Relationships (${edges.length})</h4>
        <ul class="graph-detail-edges">${edgeRows || '<li class="muted">None</li>'}</ul>
        <div class="graph-detail-actions">
          <button type="button" class="btn btn-sm" id="graph-expand-btn">Expand neighbors</button>
          <button type="button" class="btn btn-sm" id="graph-collapse-btn">Collapse to selection</button>
          <button type="button" class="btn btn-sm" id="graph-set-source-btn">Set as path source</button>
          <button type="button" class="btn btn-sm" id="graph-set-target-btn">Set as path target</button>
          <button type="button" class="btn btn-sm" id="graph-impact-node-btn">Impact analysis</button>
          ${node.type === "Project" ? `<button type="button" class="btn btn-sm btn-primary" id="graph-open-project-btn">Open project page</button>` : ""}
        </div>
      `;

      document.getElementById("graph-expand-btn").addEventListener("click", async () => {
        const entries = await fetchJSON(`/graph/neighbors/${encodeURIComponent(id)}?depth=1`);
        view.addNodes(entries.map((e) => e.node), entries.map((e) => e.edge));
      });
      document.getElementById("graph-collapse-btn").addEventListener("click", () => view.collapseTo(id));
      document.getElementById("graph-set-source-btn").addEventListener("click", () => {
        pathSource = id;
        updatePathStatus();
        maybeComputePath();
      });
      document.getElementById("graph-set-target-btn").addEventListener("click", () => {
        pathTarget = id;
        updatePathStatus();
        maybeComputePath();
      });
      document.getElementById("graph-impact-node-btn").addEventListener("click", () => runImpactAnalysis(id));
      const openBtn = document.getElementById("graph-open-project-btn");
      if (openBtn) {
        openBtn.addEventListener("click", () => navigate("project", node.data.project_id || id.replace(/^project:/, "")));
      }
    }

    async function selectNode(id) {
      try {
        const data = await fetchJSON(`/graph/node/${encodeURIComponent(id)}`);
        renderDetailPanel(data.node, data.edges, id);
      } catch (err) {
        els.detailPanel.innerHTML = `<p class="error-box">Could not load node: ${escapeHtml(err.message)}</p>`;
      }
    }
    view.onNodeClick(selectNode);

    function updatePathStatus() {
      const sourceLabel = pathSource && view.getNode(pathSource) ? view.getNode(pathSource).node.label : "(none)";
      const targetLabel = pathTarget && view.getNode(pathTarget) ? view.getNode(pathTarget).node.label : "(none)";
      els.pathBar.textContent = `Source: ${sourceLabel} — Target: ${targetLabel}`;
    }

    async function maybeComputePath() {
      if (!pathSource || !pathTarget) return;
      try {
        const result = await fetchJSON(`/graph/path?source=${encodeURIComponent(pathSource)}&target=${encodeURIComponent(pathTarget)}`);
        if (!result.found) {
          els.pathBar.textContent += " — no path found within range.";
          return;
        }
        view.addNodes(result.nodes, result.edges);
        view.setHighlight("path", new Set(result.edges.map((e) => `${e.source}|${e.target}|${e.type}`)));
        els.pathBar.textContent += ` — path length ${result.edges.length} hop(s), highlighted.`;
      } catch (err) {
        console.error("Could not compute path", err);
      }
    }

    async function runImpactAnalysis(id) {
      try {
        const result = await fetchJSON(`/graph/impact/${encodeURIComponent(id)}`);
        const counts = Object.entries(result.affected_by_type)
          .filter(([, items]) => items.length)
          .map(([type, items]) => `<li>${escapeHtml(type)}: ${items.length}</li>`)
          .join("");
        els.detailPanel.innerHTML = `
          <h3>Impact analysis: ${escapeHtml(result.origin.label)}</h3>
          <p class="card-muted">${result.total_affected} node(s) reachable</p>
          <ul class="graph-detail-edges">${counts || '<li class="muted">Nothing affected</li>'}</ul>
          <h4>Live Advisor recommendations</h4>
          ${result.advisor_recommendations.length ? `<ul class="graph-detail-edges">${result.advisor_recommendations.map((r) => `<li>${escapeHtml(r.title)}</li>`).join("")}</ul>` : '<p class="muted">None</p>'}
        `;
        const allAffected = Object.values(result.affected_by_type).flat();
        view.addNodes(allAffected, []);
        view.setHighlight("impact", new Set(allAffected.map((n) => n.id)), true);
      } catch (err) {
        console.error("Impact analysis failed", err);
      }
    }
    els.impactBtn.addEventListener("click", () => {
      if (pathSource) runImpactAnalysis(pathSource);
    });

    async function loadMetaTypes() {
      const meta = await fetchJSON("/graph/meta/types");
      els.nodeTypeSelect.innerHTML =
        '<option value="">All node types</option>' + meta.node_types.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
      els.relationshipSelect.innerHTML =
        '<option value="">All relationships</option>' + meta.relationship_types.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
    }

    async function loadWorkspaceOptions() {
      const wsNodes = await fetchJSON("/graph?node_type=Workspace");
      els.workspaceSelect.innerHTML =
        '<option value="">All workspaces</option>' + wsNodes.nodes.map((n) => `<option value="${escapeHtml(n.label)}">${escapeHtml(n.label)}</option>`).join("");
    }

    async function loadFilteredView() {
      const params = new URLSearchParams();
      if (els.nodeTypeSelect.value) params.set("node_type", els.nodeTypeSelect.value);
      if (els.workspaceSelect.value) params.set("workspace", els.workspaceSelect.value);
      const data = await fetchJSON(`/graph?${params.toString()}`);
      let edges = data.edges;
      if (els.relationshipSelect.value) edges = edges.filter((e) => e.type === els.relationshipSelect.value);
      view.setNodes(data.nodes, edges);
    }

    els.nodeTypeSelect.addEventListener("change", loadFilteredView);
    els.workspaceSelect.addEventListener("change", loadFilteredView);
    els.relationshipSelect.addEventListener("change", loadFilteredView);
    els.searchInput.addEventListener(
      "input",
      debounce(async () => {
        const q = els.searchInput.value.trim();
        if (!q) return;
        const results = await fetchJSON(`/graph/search?q=${encodeURIComponent(q)}`);
        els.detailPanel.innerHTML =
          '<h3>Search results</h3><ul class="graph-detail-edges">' +
          results.map((n) => `<li><a href="#" data-id="${escapeHtml(n.id)}">${escapeHtml(n.label)} <span class="badge">${escapeHtml(n.type)}</span></a></li>`).join("") +
          "</ul>";
        els.detailPanel.querySelectorAll("a[data-id]").forEach((a) => {
          a.addEventListener("click", async (ev) => {
            ev.preventDefault();
            const id = a.dataset.id;
            const single = await fetchJSON(`/graph/node/${encodeURIComponent(id)}`);
            view.addNodes([single.node], []);
            selectNode(id);
          });
        });
      }, 250)
    );
    els.highlightDepsBtn.addEventListener("click", () => view.toggleHighlight("dependencies"));
    els.highlightCapsBtn.addEventListener("click", () => view.toggleHighlight("capabilities"));
    els.zoomInBtn.addEventListener("click", () => view.zoomBy(1.2));
    els.zoomOutBtn.addEventListener("click", () => view.zoomBy(1 / 1.2));
    els.resetBtn.addEventListener("click", () => {
      pathSource = null;
      pathTarget = null;
      els.pathBar.textContent = "Pick a source and target node (via the detail panel) to highlight the shortest path between them.";
      els.detailPanel.innerHTML = '<p class="muted">Click a node to see its details, expand its neighbors, or use it as a path/impact endpoint.</p>';
      els.nodeTypeSelect.value = "";
      els.workspaceSelect.value = "";
      els.relationshipSelect.value = "";
      view.resetZoom();
      loadFilteredView();
    });

    await loadMetaTypes();
    await loadWorkspaceOptions();
    await loadFilteredView();

    if (pendingGraphFocus) {
      const focusId = pendingGraphFocus;
      pendingGraphFocus = null;
      try {
        const single = await fetchJSON(`/graph/node/${encodeURIComponent(focusId)}`);
        view.addNodes([single.node], []);
        selectNode(focusId);
      } catch (err) {
        console.error("Could not focus requested node", err);
      }
    }
  }

  // =======================================================================
  // Graph rendering engine: a small, reusable SVG force-free layout with
  // optional zoom/pan and click interaction. Shared by the Home preview,
  // the Project page preview, and the full Graph page.
  // =======================================================================

  const NS = "http://www.w3.org/2000/svg";
  const NODE_COLOR_VARS = {
    Project: "--node-project", KnowledgeCard: "--node-knowledgecard", Person: "--node-person",
    Application: "--node-application", Vendor: "--node-vendor", Capability: "--node-capability",
    Workspace: "--node-workspace", Decision: "--node-decision", Deliverable: "--node-deliverable",
    Prompt: "--node-prompt", Asset: "--node-asset", Conversation: "--node-conversation",
    // Sprint 5 Knowledge Graph (conversation graph) node types -- lowercase,
    // a separate vocabulary from the Epic 3 types above. Project/Person/
    // Decision/Asset/Conversation intentionally reuse the same CSS vars as
    // their Epic 3 counterparts for consistent coloring across both graphs.
    conversation: "--node-conversation", project: "--node-project", person: "--node-person",
    task: "--node-task", decision: "--node-decision", idea: "--node-idea",
    document: "--node-document", asset: "--node-asset",
  };

  function nodeColor(type) {
    const varName = NODE_COLOR_VARS[type] || "--text-muted";
    return getComputedStyle(document.documentElement).getPropertyValue(varName) || "#999";
  }

  function edgeKey(edge) {
    return `${edge.source}|${edge.target}|${edge.type}`;
  }

  function createGraphView(svg, options) {
    const width = options.width || 900;
    const height = options.height || 560;
    const interactive = !!options.interactive;
    const emptyMsgEl = options.emptyMsgEl || null;

    let nodes = new Map();
    let edges = [];
    let clickHandler = null;
    let highlightMode = null;
    let highlightKeys = new Set();
    let scale = 1;
    let tx = 0;
    let ty = 0;

    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const viewport = document.createElementNS(NS, "g");
    viewport.setAttribute("id", "graph-viewport");
    svg.appendChild(viewport);

    function applyTransform() {
      viewport.setAttribute("transform", `translate(${tx}, ${ty}) scale(${scale})`);
    }

    if (interactive) {
      let dragging = false;
      let lastX = 0;
      let lastY = 0;
      svg.addEventListener("mousedown", (e) => {
        dragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
      });
      window.addEventListener("mouseup", () => (dragging = false));
      window.addEventListener("mousemove", (e) => {
        if (!dragging) return;
        tx += e.clientX - lastX;
        ty += e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        applyTransform();
      });
      svg.addEventListener("wheel", (e) => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
        scale = Math.max(0.2, Math.min(4, scale * factor));
        applyTransform();
      });
    }

    function layout() {
      const ids = Array.from(nodes.keys());
      const n = ids.length || 1;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) / 2 - 50;
      ids.forEach((id, i) => {
        const angle = (2 * Math.PI * i) / n;
        const entry = nodes.get(id);
        entry.x = cx + radius * Math.cos(angle);
        entry.y = cy + radius * Math.sin(angle);
      });
    }

    function render() {
      viewport.innerHTML = "";
      if (emptyMsgEl) emptyMsgEl.hidden = nodes.size > 0;
      if (!nodes.size) return;
      layout();

      edges.forEach((edge) => {
        const a = nodes.get(edge.source);
        const b = nodes.get(edge.target);
        if (!a || !b) return;
        const line = document.createElementNS(NS, "line");
        line.setAttribute("x1", a.x);
        line.setAttribute("y1", a.y);
        line.setAttribute("x2", b.x);
        line.setAttribute("y2", b.y);
        let cls = "graph-edge";
        const key = edgeKey(edge);
        if (highlightMode === "path" && highlightKeys.has(key)) cls += " graph-edge-highlight-path";
        else if (highlightMode === "dependencies" && (edge.type === "DEPENDS_ON" || edge.type === "UNBLOCKS")) cls += " graph-edge-highlight-deps";
        else if (highlightMode === "capabilities" && ["IMPLEMENTS", "USES", "SHARES_CAPABILITY"].includes(edge.type)) cls += " graph-edge-highlight-caps";
        else if (highlightMode === "impact" && highlightKeys.has(edge.source) && highlightKeys.has(edge.target)) cls += " graph-edge-highlight-impact";
        line.setAttribute("class", cls);
        viewport.appendChild(line);
      });

      nodes.forEach((entry, id) => {
        const g = document.createElementNS(NS, "g");
        g.setAttribute("class", "graph-node graph-node-entering");
        g.setAttribute("transform", `translate(${entry.x}, ${entry.y})`);

        const circle = document.createElementNS(NS, "circle");
        circle.setAttribute("r", 8);
        circle.setAttribute("fill", nodeColor(entry.node.type).trim() || "#999");
        g.appendChild(circle);

        const text = document.createElementNS(NS, "text");
        text.setAttribute("x", 11);
        text.setAttribute("y", 4);
        text.setAttribute("class", "graph-node-label");
        text.textContent = entry.node.label;
        g.appendChild(text);

        if (interactive && clickHandler) {
          g.style.cursor = "pointer";
          g.addEventListener("click", (e) => {
            e.stopPropagation();
            clickHandler(id);
          });
        }
        viewport.appendChild(g);
      });
    }

    return {
      setNodes(nodeList, edgeList) {
        nodes = new Map(nodeList.map((n) => [n.id, { node: n, x: 0, y: 0 }]));
        edges = edgeList.map((e) => ({ source: e.source, target: e.target, type: e.type }));
        render();
      },
      addNodes(nodeList, edgeList) {
        nodeList.forEach((n) => {
          if (!nodes.has(n.id)) nodes.set(n.id, { node: n, x: 0, y: 0 });
        });
        const existing = new Set(edges.map(edgeKey));
        edgeList.forEach((e) => {
          const key = edgeKey(e);
          if (!existing.has(key)) {
            existing.add(key);
            edges.push({ source: e.source, target: e.target, type: e.type });
          }
        });
        render();
      },
      collapseTo(id) {
        const keep = new Set([id]);
        edges.forEach((e) => {
          if (e.source === id) keep.add(e.target);
          if (e.target === id) keep.add(e.source);
        });
        nodes.forEach((_v, nodeId) => {
          if (!keep.has(nodeId)) nodes.delete(nodeId);
        });
        edges = edges.filter((e) => keep.has(e.source) && keep.has(e.target));
        render();
      },
      getNode(id) {
        return nodes.get(id);
      },
      onNodeClick(fn) {
        clickHandler = fn;
      },
      setHighlight(mode, keys) {
        highlightMode = mode;
        highlightKeys = keys;
        render();
      },
      toggleHighlight(mode) {
        highlightMode = highlightMode === mode ? null : mode;
        render();
      },
      zoomBy(factor) {
        scale = Math.max(0.2, Math.min(4, scale * factor));
        applyTransform();
      },
      resetZoom() {
        scale = 1;
        tx = 0;
        ty = 0;
        highlightMode = null;
        highlightKeys = new Set();
        applyTransform();
      },
    };
  }

  // =======================================================================
  // KNOWLEDGE GRAPH PAGE (Sprint 5) -- graph over imported conversations
  // and their extracted knowledge objects. Independent of the Epic 3
  // /graph page above: separate API (/conversation-graph), separate
  // vocabulary (8 node types, one "contains" relationship), but reuses the
  // same createGraphView() rendering engine and .graph-* CSS classes.
  // =======================================================================

  const CONVERSATION_GRAPH_NODE_TYPES = [
    "conversation", "project", "person", "task", "decision", "idea", "document", "asset",
  ];

  async function renderConversationGraphPage(conversationIdParam) {
    viewRoot.innerHTML = `
      <div class="graph-page">
        <div class="graph-toolbar">
          <select id="kg-conversation-select"><option value="">All conversations</option></select>
          <select id="kg-node-type-select">
            <option value="">All node types</option>
            ${CONVERSATION_GRAPH_NODE_TYPES.map((t) => `<option value="${t}">${t}</option>`).join("")}
          </select>
          <button id="kg-clear-filters-btn" type="button" class="btn btn-sm">Clear filters</button>
          <button id="kg-zoom-in" type="button" class="btn btn-sm">+</button>
          <button id="kg-zoom-out" type="button" class="btn btn-sm">-</button>
          <button id="kg-reset-btn" type="button" class="btn btn-sm">Reset view</button>
        </div>
        <div class="graph-page-body">
          <div class="graph-page-canvas-wrap">
            <svg id="kg-canvas"></svg>
            <p id="kg-loading-msg" class="muted loading-pulse">Loading knowledge graph…</p>
            <p id="kg-empty-msg" class="muted" hidden>No knowledge graph data yet. Import a conversation and extract knowledge (Explorer → open a conversation → Extract Knowledge) to see it here.</p>
          </div>
          <aside id="kg-detail-panel" class="graph-page-sidebar graph-detail-panel">
            <p class="muted">Click a node to see its details.</p>
          </aside>
        </div>
      </div>
    `;

    const els = {
      svg: document.getElementById("kg-canvas"),
      emptyMsg: document.getElementById("kg-empty-msg"),
      loadingMsg: document.getElementById("kg-loading-msg"),
      detailPanel: document.getElementById("kg-detail-panel"),
      conversationSelect: document.getElementById("kg-conversation-select"),
      nodeTypeSelect: document.getElementById("kg-node-type-select"),
      clearFiltersBtn: document.getElementById("kg-clear-filters-btn"),
      zoomInBtn: document.getElementById("kg-zoom-in"),
      zoomOutBtn: document.getElementById("kg-zoom-out"),
      resetBtn: document.getElementById("kg-reset-btn"),
    };

    const view = createGraphView(els.svg, { width: 900, height: 560, interactive: true, emptyMsgEl: els.emptyMsg });

    function renderDetailPanel(node) {
      const d = node.data || {};
      const isConversation = node.type === "conversation";
      const rows = isConversation
        ? [
            ["Title", node.label],
            ["Source", d.source || "—"],
            ["Created", formatDate(d.created_at)],
            ["Updated", formatDate(d.updated_at)],
            ["Message count", d.message_count ?? "—"],
          ]
        : [
            ["Type", node.type],
            ["Value", node.label],
            ["Confidence", d.confidence != null ? `${Math.round(d.confidence * 100)}%` : "—"],
            ["Created", formatDate(d.created_at)],
            ["Updated", formatDate(d.updated_at)],
            ["Source conversation", d.conversation_id || "—"],
          ];
      const rowsHtml = rows.map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(String(v))}</td></tr>`).join("");
      const conversationId = isConversation ? d.conversation_id : d.conversation_id;

      els.detailPanel.innerHTML = `
        <h3>${escapeHtml(node.label)}</h3>
        <p class="badge">${escapeHtml(node.type)}</p>
        <table class="graph-detail-table">${rowsHtml}</table>
        <div class="graph-detail-actions">
          ${conversationId ? `<button type="button" class="btn btn-sm" id="kg-open-conversation-btn">Open in Conversation Explorer</button>` : ""}
        </div>
      `;

      const openBtn = document.getElementById("kg-open-conversation-btn");
      if (openBtn) {
        openBtn.addEventListener("click", () => {
          navigate("explorer");
          pendingExplorerConversationFocus = conversationId;
        });
      }
    }

    async function selectNode(id) {
      try {
        const data = await fetchJSON(`/conversation-graph/nodes/${encodeURIComponent(id)}`);
        renderDetailPanel(data.node);
      } catch (err) {
        els.detailPanel.innerHTML = `<p class="error-box">Could not load node: ${escapeHtml(err.message)}</p>`;
      }
    }
    view.onNodeClick(selectNode);

    async function loadConversationOptions() {
      const result = await fetchJSON("/import/conversations?page=1&page_size=200&sort_by=title&sort_dir=asc");
      els.conversationSelect.innerHTML =
        '<option value="">All conversations</option>' +
        result.items.map((c) => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.title)}</option>`).join("");
    }

    async function loadFilteredView() {
      els.loadingMsg.hidden = false;
      try {
        const params = new URLSearchParams();
        if (els.conversationSelect.value) params.set("conversation_id", els.conversationSelect.value);
        if (els.nodeTypeSelect.value) params.set("node_type", els.nodeTypeSelect.value);
        const data = await fetchJSON(`/conversation-graph?${params.toString()}`);
        view.setNodes(data.nodes, data.edges);
        els.loadingMsg.hidden = true;
      } catch (err) {
        els.loadingMsg.hidden = true;
        els.emptyMsg.hidden = true;
        document.getElementById("kg-canvas").insertAdjacentHTML(
          "afterend",
          `<p class="error-box">Could not load knowledge graph: ${escapeHtml(err.message)}</p>`
        );
      }
    }

    els.conversationSelect.addEventListener("change", loadFilteredView);
    els.nodeTypeSelect.addEventListener("change", loadFilteredView);
    els.clearFiltersBtn.addEventListener("click", () => {
      els.conversationSelect.value = "";
      els.nodeTypeSelect.value = "";
      els.detailPanel.innerHTML = '<p class="muted">Click a node to see its details.</p>';
      view.resetZoom();
      loadFilteredView();
    });
    els.zoomInBtn.addEventListener("click", () => view.zoomBy(1.2));
    els.zoomOutBtn.addEventListener("click", () => view.zoomBy(1 / 1.2));
    els.resetBtn.addEventListener("click", () => view.resetZoom());

    await loadConversationOptions();
    if (conversationIdParam) {
      els.conversationSelect.value = conversationIdParam;
    }
    await loadFilteredView();
  }

  // =======================================================================
  // SESSION PAGE (ROLE OS Dashboard MVP: Start/End My Day, Claude prompt,
  // Obsidian daily record, project registry, recent ecosystem decisions)
  // =======================================================================

  let _sessionModesCache = null;

  async function getModesCached() {
    if (!_sessionModesCache) {
      _sessionModesCache = await fetchJSON("/session/modes");
    }
    return _sessionModesCache;
  }

  function todayISODate() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  // Daily Session status vocabulary: active/completed/not_started.
  function sessionStatusBadge(status) {
    const variants = { active: "healthy", completed: "info" };
    const label = status === "active" ? "Active" : status === "completed" ? "Completed" : "Not Started";
    return badgeHtml(label, variants[status]);
  }

  function registryDefaultTag(project) {
    if (project.is_authoritative) return '<span class="badge badge-info" title="Sourced from an actual ROLE Ecosystem document">documented</span>';
    if (project.user_edited) return '<span class="badge badge-healthy" title="Edited by you">edited</span>';
    return '<span class="badge" title="Placeholder value -- no authoritative source found yet">default</span>';
  }

  function renderRegistryCardHtml(projects) {
    const rows = projects
      .map(
        (p) => `
        <tr data-registry-row="${escapeHtml(p.id)}">
          <td>
            <strong>${escapeHtml(p.name)}</strong> ${registryDefaultTag(p)}<br/>
            <span class="muted u-fs-12">${escapeHtml(p.reference)}</span>
          </td>
          <td>${escapeHtml(p.status)}</td>
          <td>${escapeHtml(p.milestone)}</td>
          <td>${escapeHtml(p.next_action)}</td>
          <td><button type="button" class="btn btn-sm" data-registry-edit="${escapeHtml(p.id)}">Edit</button></td>
        </tr>
        <tr class="registry-edit-row" data-registry-edit-row="${escapeHtml(p.id)}" hidden>
          <td colspan="5">
            <form data-registry-form="${escapeHtml(p.id)}" class="field-row">
              <label>Status<input type="text" name="status" value="${escapeHtml(p.status)}" /></label>
              <label>Reference<input type="text" name="reference" value="${escapeHtml(p.reference)}" /></label>
              <label>Milestone<input type="text" name="milestone" value="${escapeHtml(p.milestone)}" /></label>
              <label>Next action<input type="text" name="next_action" value="${escapeHtml(p.next_action)}" /></label>
              <div class="u-mt-2">
                <button type="submit" class="btn btn-sm btn-primary">Save</button>
                <button type="button" class="btn btn-sm" data-registry-cancel="${escapeHtml(p.id)}">Cancel</button>
              </div>
              <div data-registry-status="${escapeHtml(p.id)}" class="muted u-fs-12 u-mt-1"></div>
            </form>
          </td>
        </tr>`
      )
      .join("");

    return `
      <div class="card">
        <p class="card-title">Active projects</p>
        <p class="muted u-fs-12">Local project registry. "default" values are placeholders -- edit them, or see the linked reference document.</p>
        <table class="kv-table">
          <tr><th>Project</th><th>Status</th><th>Milestone</th><th>Next action</th><th></th></tr>
          ${rows}
        </table>
      </div>`;
  }

  function renderDecisionsCardHtml(resp) {
    const items = resp.decisions
      .map((d) => `<li><strong>${escapeHtml(d.id)}</strong> (${escapeHtml(d.date)}) — ${escapeHtml(d.decision)} <span class="muted u-fs-12">[${escapeHtml(d.status)}]</span></li>`)
      .join("");
    const sourceNote = resp.source === "ecosystem"
      ? '<span class="badge badge-healthy">live</span>'
      : '<span class="badge" title="' + escapeHtml(resp.note) + '">fallback snapshot</span>';
    return `
      <div class="card">
        <div class="u-flex-between"><p class="card-title">Recent ecosystem decisions</p>${sourceNote}</div>
        <ul class="timeline-list">${items || '<li class="muted">No decisions available.</li>'}</ul>
      </div>`;
  }

  function renderStartFormHtml(modes, projects) {
    const projectOptions = projects
      .map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`)
      .join("");
    const modeOptions = modes.map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.name)}</option>`).join("");
    return `
      <div class="card" id="session-start-form">
        <p class="card-title">Start My Day</p>
        <form id="session-start-form-el">
          <div class="field-row">
            <label>Date<input type="date" name="date" value="${todayISODate()}" required /></label>
            <label>Project
              <select name="project_id" required>
                <option value="">Select a project…</option>
                ${projectOptions}
              </select>
            </label>
            <label>Mode
              <select name="mode" required>
                <option value="">Select a mode…</option>
                ${modeOptions}
              </select>
            </label>
          </div>
          <label class="u-mt-2">Today's objective<textarea name="objective" rows="2" required></textarea></label>
          <label class="u-mt-2">Expected result<textarea name="expected_result" rows="2" required></textarea></label>
          <label class="u-mt-2">Notes (optional)<textarea name="notes" rows="2"></textarea></label>
          <div class="u-mt-3">
            <button type="submit" class="btn btn-sm btn-primary">Start session</button>
          </div>
          <div id="session-start-status" class="u-mt-2"></div>
        </form>
      </div>`;
  }

  // ---------------------------------------------------------------------
  // AI Launcher (v1.2): one-click Start Claude / Start ChatGPT / Start Both.
  // Copies the assembled prompt to the clipboard and opens the target
  // site(s) in a new tab -- no typing automation, no browser automation
  // library, everything client-side in this file.
  // ---------------------------------------------------------------------

  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    // Force layout so the CSS transition below actually animates in,
    // rather than starting already-visible.
    void toast.offsetWidth;
    toast.classList.add("toast-visible");
    setTimeout(() => {
      toast.classList.remove("toast-visible");
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // =======================================================================
  // RESUME WORK (Sprint 5 §3) -- the one primary action for a Project.
  // Shared by the Discovered Project Detail page, Home's Quick Resume, and
  // Advisor's recommendation cards, so all three trigger the exact same
  // sequence: locate/start the AI Session server-side, then client-side
  // copy the prompt + open the assistant (no browser automation, same
  // no-OS-level-action contract as the existing per-session Resume button
  // in Cockpit), then land on the Cockpit for this project's canonical
  // identity.
  // =======================================================================

  // Hotfix (Session Intent no-action guard): ROLE OS refuses to silently
  // send Claude "Continue this project" when it has no trustworthy
  // evidence-backed action for today. `requires_user_objective: true`
  // means nothing was built server-side yet -- this modal collects the
  // user's own objective, then re-calls the same endpoint with it, the
  // same "ask once, never guess" contract §5 of the brief describes.
  const objectiveOverlay = document.getElementById("objective-overlay");
  const objectiveBody = document.getElementById("objective-body");
  document.getElementById("objective-close").addEventListener("click", () => {
    objectiveOverlay.hidden = true;
  });

  function promptForSessionObjective(itemId, projectName, message) {
    objectiveOverlay.hidden = false;
    objectiveBody.innerHTML = `
      <h3 id="objective-title">What do you want to accomplish?</h3>
      <p class="muted u-fs-12 u-mt-1">${escapeHtml(message || `ROLE OS could not derive a trustworthy next action for ${projectName} from existing evidence.`)}</p>
      <div class="field-row u-mt-3">
        <label for="objective-requested-action">Objective (required)</label>
        <textarea id="objective-requested-action" rows="2" placeholder="e.g. Fix the hardcoded absolute-path references found in ROLE_OS"></textarea>
      </div>
      <div class="field-row u-mt-2">
        <label for="objective-expected-deliverable">Expected deliverable (optional)</label>
        <textarea id="objective-expected-deliverable" rows="2" placeholder="e.g. All hardcoded absolute paths replaced with relative/config-driven paths."></textarea>
      </div>
      <div class="field-row u-mt-2">
        <label for="objective-completion-criteria">Completion criteria (optional)</label>
        <textarea id="objective-completion-criteria" rows="2" placeholder="e.g. Grep for the repo root string returns zero matches outside config files."></textarea>
      </div>
      <div id="objective-error" class="error-box u-mt-2" hidden></div>
      <button type="button" class="btn btn-primary u-mt-3" id="objective-submit-btn">Start Session</button>
    `;
    document.getElementById("objective-submit-btn").addEventListener("click", async () => {
      const requestedAction = document.getElementById("objective-requested-action").value.trim();
      const errorEl = document.getElementById("objective-error");
      if (!requestedAction) {
        errorEl.textContent = "An objective is required.";
        errorEl.hidden = false;
        return;
      }
      errorEl.hidden = true;
      const userObjective = {
        requested_action: requestedAction,
        expected_deliverable: document.getElementById("objective-expected-deliverable").value.trim() || null,
        completion_criteria: document.getElementById("objective-completion-criteria").value.trim() || null,
      };
      objectiveOverlay.hidden = true;
      await triggerResumeWork(itemId, userObjective);
    });
  }

  // Context Sufficiency Guard (hotfix §7): the Context Package could not
  // embed any real local file content -- do NOT auto-open Claude or copy a
  // prompt that a fresh, filesystem-less conversation could not act on.
  // Surface exactly what's missing instead, in Cockpit.
  function showMissingContext(result) {
    objectiveOverlay.hidden = false;
    const missing = (result.missing_context || []).map((m) => `<li>${escapeHtml(m)}</li>`).join("");
    objectiveBody.innerHTML = `
      <h3>Not enough local context yet</h3>
      <p class="muted u-fs-12 u-mt-1">${escapeHtml(result.message || "ROLE OS could not gather enough local project context to hand off to a fresh conversation.")}</p>
      <ul class="u-mt-2 u-fs-12">${missing}</ul>
      <p class="muted u-fs-12 u-mt-2">Add project documentation (README.md, ROADMAP.md, etc.) to the project folder, or provide an objective with more detail, then try again.</p>
    `;
  }

  // Hotfix (Resume Work Execution Target): `execution_target` tells us
  // whether this session belongs in Claude Code (local repository) or a
  // web assistant (claude.ai/chatgpt.com) -- see
  // `app.workspace.execution_target`. "user_choice" means the action was
  // ambiguous enough that either could work; the frontend asks instead of
  // guessing, defaulting to `recommended_assistant`.
  const ASSISTANT_LABELS = {
    claude_code: "Claude Code",
    claude_web: "Claude (web)",
    chatgpt_web: "ChatGPT",
  };

  async function launchClaudeCode(itemId, prompt) {
    try {
      const launch = await postJSON(`/workspace/discovered/${encodeURIComponent(itemId)}/launch-claude-code`, {
        prompt,
      });
      // Never silently pretend a missing local CLI succeeded, or fall
      // back to a web assistant on its own -- surface exactly what
      // launched (or didn't) and where.
      showToast(launch.message || (launch.launched ? "Claude Code launched." : "Could not launch Claude Code."));
    } catch (err) {
      // Clipboard already has the prompt even if the server-side launch
      // failed (e.g. off Windows) -- still useful, so don't dead-end here.
      showToast(`Could not launch Claude Code: ${err.message}`);
    }
  }

  async function openWebAssistant(result) {
    await navigator.clipboard.writeText(result.prompt);
    if (result.url) window.open(result.url, "_blank");
    showToast(
      result.used_saved_conversation
        ? "Prompt copied — conversation opened."
        : (result.message || "Prompt copied.")
    );
  }

  function promptForExecutionTarget(itemId, result) {
    objectiveOverlay.hidden = false;
    const options = (result.available_assistants || [])
      .map((target) => {
        const label = ASSISTANT_LABELS[target] || target;
        const recommended = target === result.recommended_assistant ? " (Recommended)" : "";
        return `<button type="button" class="btn u-mt-2" data-target="${escapeHtml(target)}">${escapeHtml(label)}${recommended}</button>`;
      })
      .join("<br>");
    objectiveBody.innerHTML = `
      <h3>Resume With</h3>
      <p class="muted u-fs-12 u-mt-1">${escapeHtml(result.execution_target_reason || "")}</p>
      ${result.working_directory ? `<p class="muted u-fs-12">Working Directory: ${escapeHtml(result.working_directory)}</p>` : ""}
      <div class="u-mt-2">${options}</div>
    `;
    objectiveBody.querySelectorAll("button[data-target]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        objectiveOverlay.hidden = true;
        if (btn.dataset.target === "claude_code") {
          await launchClaudeCode(itemId, result.prompt);
        } else {
          await openWebAssistant(result);
        }
        navigate("cockpit", result.project_id);
      });
    });
  }

  async function triggerResumeWork(itemId, userObjective) {
    try {
      const result = await postJSON(`/workspace/discovered/${encodeURIComponent(itemId)}/resume-work`, {
        user_objective: userObjective || null,
      });
      if (result.requires_user_objective) {
        promptForSessionObjective(itemId, result.project_name, result.message);
        return;
      }
      if (result.context_sufficient === false) {
        showMissingContext(result);
        return;
      }
      if (result.execution_target === "claude_code") {
        await launchClaudeCode(itemId, result.prompt);
        navigate("cockpit", result.project_id);
        return;
      }
      if (result.execution_target === "user_choice") {
        promptForExecutionTarget(itemId, result);
        return;
      }
      await openWebAssistant(result);
      navigate("cockpit", result.project_id);
    } catch (err) {
      showToast(`Could not resume work: ${err.message}`);
    }
  }

  function renderAiLauncherCardHtml() {
    return `
      <div class="card">
        <p class="card-title">AI Launcher</p>
        <p class="muted u-fs-12">Copies today's session prompt to your clipboard and opens the AI tool -- paste with Ctrl+V once it loads.</p>
        <div class="field-row">
          <button type="button" class="btn btn-sm btn-primary" id="ai-launch-claude-btn">Start Claude</button>
          <button type="button" class="btn btn-sm btn-primary" id="ai-launch-chatgpt-btn">Start ChatGPT</button>
          <button type="button" class="btn btn-sm" id="ai-launch-both-btn">Start Both</button>
        </div>
        <div id="ai-launch-status" class="muted u-fs-12 u-mt-2"></div>
      </div>`;
  }

  async function launchAiTool(tool, buttonEl) {
    const statusEl = document.getElementById("ai-launch-status");
    const allButtons = [
      document.getElementById("ai-launch-claude-btn"),
      document.getElementById("ai-launch-chatgpt-btn"),
      document.getElementById("ai-launch-both-btn"),
    ];
    allButtons.forEach((btn) => { if (btn) btn.disabled = true; });
    statusEl.textContent = "Preparing session prompt…";

    try {
      const result = await postJSON("/launcher/start", { tool });

      try {
        await navigator.clipboard.writeText(result.prompt);
      } catch (clipErr) {
        statusEl.innerHTML = `<span class="error-box">Could not copy automatically (${escapeHtml(clipErr.message)}). Copy the prompt from the card below manually.</span>`;
        return;
      }

      result.urls.forEach((url) => window.open(url, "_blank"));

      statusEl.textContent = "";
      showToast("Prompt copied. Press Ctrl+V and Enter.");
    } catch (err) {
      statusEl.innerHTML = `<span class="error-box">${escapeHtml(err.message)}</span>`;
    } finally {
      allButtons.forEach((btn) => { if (btn) btn.disabled = false; });
    }
  }

  function wireAiLauncher() {
    document.getElementById("ai-launch-claude-btn").addEventListener("click", (e) => launchAiTool("claude", e.currentTarget));
    document.getElementById("ai-launch-chatgpt-btn").addEventListener("click", (e) => launchAiTool("chatgpt", e.currentTarget));
    document.getElementById("ai-launch-both-btn").addEventListener("click", (e) => launchAiTool("both", e.currentTarget));
  }

  function renderPromptCardHtml(promptText) {
    return `
      <div class="card">
        <div class="u-flex-between"><p class="card-title">Claude session prompt</p><button type="button" class="btn btn-sm" id="session-copy-prompt-btn">Copy</button></div>
        <pre id="session-prompt-text" class="rec-card-body u-fs-12" style="white-space: pre-wrap;">${escapeHtml(promptText)}</pre>
        <div id="session-copy-prompt-status" class="muted u-fs-12"></div>
      </div>`;
  }

  function renderEndFormHtml() {
    return `
      <div class="card">
        <p class="card-title">End My Day</p>
        <form id="session-end-form-el">
          <label>Work completed<textarea name="completed_work" rows="3" required></textarea></label>
          <label class="u-mt-2">Decisions made<textarea name="decisions" rows="2"></textarea></label>
          <label class="u-mt-2">Blockers<textarea name="blockers" rows="2"></textarea></label>
          <label class="u-mt-2">Next step<textarea name="next_step" rows="2"></textarea></label>
          <div class="u-mt-3">
            <button type="submit" class="btn btn-sm btn-primary">Close session</button>
          </div>
          <div id="session-end-status" class="u-mt-2"></div>
        </form>
      </div>`;
  }

  function renderCompletedCardHtml(session, md) {
    return `
      <div class="card">
        <div class="u-flex-between">
          <p class="card-title">Daily record — ${escapeHtml(md.filename)}</p>
          <div>
            <button type="button" class="btn btn-sm" id="session-copy-md-btn">Copy</button>
            <button type="button" class="btn btn-sm" id="session-download-md-btn">Download</button>
            <button type="button" class="btn btn-sm" id="session-save-vault-btn">Save to vault</button>
          </div>
        </div>
        <pre id="session-md-text" class="rec-card-body u-fs-12" style="white-space: pre-wrap;">${escapeHtml(md.markdown)}</pre>
        <div id="session-vault-status" class="muted u-fs-12"></div>
      </div>
      <div class="u-mt-3">
        <button type="button" class="btn btn-sm btn-primary" id="session-start-new-btn">Start a new session</button>
      </div>`;
  }

  async function renderSessionPage() {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading session…</p>';

    const [current, projects, modes, decisions] = await Promise.all([
      fetchJSON("/session/current"),
      fetchJSON("/session/registry"),
      getModesCached(),
      fetchJSON("/session/decisions/recent?limit=5"),
    ]);

    const summaryCard = `
      <div class="card">
        <div class="u-flex-between">
          <p class="card-title">${current ? escapeHtml(current.date) : todayISODate()}</p>
          ${sessionStatusBadge(current ? current.status : "not_started")}
        </div>
        <table class="kv-table">
          <tr><th>Mode</th><td>${current ? escapeHtml(current.mode) : '—'}</td></tr>
          <tr><th>Project</th><td>${current ? escapeHtml(current.project_name) : '—'}</td></tr>
          <tr><th>Today's objective</th><td>${current ? escapeHtml(current.objective) : '—'}</td></tr>
          <tr><th>Expected result</th><td>${current ? escapeHtml(current.expected_result) : '—'}</td></tr>
        </table>
        ${current ? "" : '<div class="u-mt-3"><button type="button" class="btn btn-sm btn-primary" id="session-quick-start-btn">Quick Start</button></div>'}
      </div>`;

    if (!current) {
      // Not Started: show summary + Start My Day + registry + decisions.
      viewRoot.innerHTML = `
        <div class="section-heading"><h2>Session</h2></div>
        <div class="home-grid">
          <div>
            ${summaryCard}
            <div class="u-mt-4">${renderStartFormHtml(modes, projects)}</div>
          </div>
          <div>
            ${renderRegistryCardHtml(projects)}
            <div class="u-mt-4">${renderDecisionsCardHtml(decisions)}</div>
          </div>
        </div>`;

      document.getElementById("session-quick-start-btn").addEventListener("click", () => {
        document.getElementById("session-start-form").scrollIntoView({ behavior: "smooth", block: "start" });
        document.querySelector("#session-start-form-el [name=project_id]").focus();
      });

      wireStartForm();
      wireRegistryEditing(projects);
      return;
    }

    if (current.status === "active") {
      const promptResp = await fetchJSON(`/session/${encodeURIComponent(current.id)}/prompt`);
      viewRoot.innerHTML = `
        <div class="section-heading"><h2>Session</h2></div>
        <div class="home-grid">
          <div>
            ${summaryCard}
            <div class="u-mt-4">${renderAiLauncherCardHtml()}</div>
            <div class="u-mt-4">${renderPromptCardHtml(promptResp.prompt)}</div>
            <div class="u-mt-4">${renderEndFormHtml()}</div>
          </div>
          <div>
            ${renderRegistryCardHtml(projects)}
            <div class="u-mt-4">${renderDecisionsCardHtml(decisions)}</div>
          </div>
        </div>`;

      wireCopyButton("session-copy-prompt-btn", "session-prompt-text", "session-copy-prompt-status");
      wireEndForm(current.id);
      wireRegistryEditing(projects);
      wireAiLauncher();
      return;
    }

    // Completed: show the generated Markdown record.
    const md = await fetchJSON(`/session/${encodeURIComponent(current.id)}/markdown`);
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Session</h2></div>
      <div class="home-grid">
        <div>
          ${summaryCard}
          <div class="u-mt-4">${renderCompletedCardHtml(current, md)}</div>
        </div>
        <div>
          ${renderRegistryCardHtml(projects)}
          <div class="u-mt-4">${renderDecisionsCardHtml(decisions)}</div>
        </div>
      </div>`;

    wireCopyButton("session-copy-md-btn", "session-md-text", "session-vault-status");
    document.getElementById("session-download-md-btn").addEventListener("click", () => {
      window.location.href = `/session/${encodeURIComponent(current.id)}/markdown/download`;
    });
    document.getElementById("session-save-vault-btn").addEventListener("click", async () => {
      const statusEl = document.getElementById("session-vault-status");
      statusEl.textContent = "Saving…";
      try {
        const result = await fetchJSON(`/session/${encodeURIComponent(current.id)}/save-to-vault`, { method: "POST" });
        statusEl.textContent = result.saved ? `Saved to ${result.path}` : `Not saved: ${result.reason}`;
      } catch (err) {
        statusEl.textContent = `Save failed: ${err.message}`;
      }
    });
    document.getElementById("session-start-new-btn").addEventListener("click", () => renderSessionPage());
  }

  function wireCopyButton(buttonId, sourceId, statusId) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const text = document.getElementById(sourceId).textContent;
      const statusEl = document.getElementById(statusId);
      try {
        await navigator.clipboard.writeText(text);
        statusEl.textContent = "Copied to clipboard.";
      } catch (err) {
        statusEl.textContent = `Could not copy automatically: ${err.message}`;
      }
    });
  }

  function wireStartForm() {
    const form = document.getElementById("session-start-form-el");
    const statusEl = document.getElementById("session-start-status");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const projectSelect = form.querySelector('[name="project_id"]');
      const payload = {
        date: data.get("date"),
        project_id: data.get("project_id") || null,
        project_name: projectSelect.options[projectSelect.selectedIndex]?.text || "",
        mode: data.get("mode"),
        objective: data.get("objective"),
        expected_result: data.get("expected_result"),
        notes: data.get("notes") || "",
      };
      if (!payload.project_id || !payload.mode) {
        statusEl.innerHTML = '<p class="error-box">Select a project and a mode.</p>';
        return;
      }
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      statusEl.innerHTML = '<p class="muted loading-pulse">Starting session…</p>';
      try {
        await postJSON("/session/start", payload);
        await renderSessionPage();
      } catch (err) {
        statusEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
        submitBtn.disabled = false;
      }
    });
  }

  function wireEndForm(sessionId) {
    const form = document.getElementById("session-end-form-el");
    const statusEl = document.getElementById("session-end-status");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const payload = {
        completed_work: data.get("completed_work"),
        decisions: data.get("decisions") || "",
        blockers: data.get("blockers") || "",
        next_step: data.get("next_step") || "",
      };
      if (!payload.completed_work || !payload.completed_work.trim()) {
        statusEl.innerHTML = '<p class="error-box">Describe what was completed before closing the session.</p>';
        return;
      }
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      statusEl.innerHTML = '<p class="muted loading-pulse">Closing session…</p>';
      try {
        await postJSON(`/session/${encodeURIComponent(sessionId)}/complete`, payload);
        await renderSessionPage();
      } catch (err) {
        statusEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
        submitBtn.disabled = false;
      }
    });
  }

  function wireRegistryEditing(projects) {
    document.querySelectorAll("[data-registry-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelector(`[data-registry-edit-row="${btn.dataset.registryEdit}"]`).hidden = false;
      });
    });
    document.querySelectorAll("[data-registry-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelector(`[data-registry-edit-row="${btn.dataset.registryCancel}"]`).hidden = true;
      });
    });
    document.querySelectorAll("[data-registry-form]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = form.dataset.registryForm;
        const data = new FormData(form);
        const payload = {
          status: data.get("status"),
          reference: data.get("reference"),
          milestone: data.get("milestone"),
          next_action: data.get("next_action"),
        };
        const statusEl = document.querySelector(`[data-registry-status="${id}"]`);
        try {
          await postJSON(`/session/registry/${encodeURIComponent(id)}`, payload, "PATCH");
          await renderSessionPage();
        } catch (err) {
          if (statusEl) statusEl.innerHTML = `<span class="error-box">Could not save: ${escapeHtml(err.message)}</span>`;
        }
      });
    });
  }

  // =======================================================================
  // WORKSPACE ADOPTION (Discovery Engine Sprint 2/3)
  //
  // Lets the user adopt/ignore/review folders the read-only Discovery
  // Engine already found on disk (/workspace/*). The filesystem is the
  // source of truth: every field shown here except priority/business
  // value/status/tags/notes/ignored/override comes straight from the last
  // cached scan, never something this page could have typed in itself.
  //
  // Sprint 3: the default view is *grouped* -- top-level projects only,
  // each with a repository/component/internal-folder count and an Expand
  // action to reveal its nested children indented underneath, instead of
  // Sprint 2's flat one-row-per-folder table. Filter tabs switch between
  // that grouped view and three flat ones (nested repositories, ignored/
  // excluded, needs review).
  // =======================================================================

  const WORKSPACE_FILTERS = [
    { key: "top_level", label: "Top-level projects" },
    { key: "repositories", label: "Nested repositories" },
    { key: "ignored_excluded", label: "Ignored / excluded" },
    { key: "needs_review", label: "Needs review" },
  ];
  let workspaceActiveFilter = "top_level";
  const workspaceExpandedIds = new Set();

  function workspaceRiskBadge(risk) {
    const cls = risk === "high" ? "badge-critical" : risk === "medium" ? "badge-warning" : "badge-healthy";
    return `<span class="badge ${cls}">${escapeHtml(risk)}</span>`;
  }

  function workspaceGitLabel(item) {
    if (!item.git_is_repo) return "—";
    const branch = escapeHtml(item.git_branch || "?");
    return item.git_is_dirty ? `${branch} <span class="badge badge-warning">dirty</span>` : branch;
  }

  // Workspace adoption-lifecycle vocabulary: ignored/adopted/discovered --
  // a third, distinct vocabulary (adoption state, not session or project
  // status), computed from the overlay booleans the Workspace domain owns.
  function workspaceStatusBadge(item) {
    if (item.ignored) return badgeHtml("Ignored");
    if (item.adopted) return badgeHtml("Adopted", "info");
    return badgeHtml("Discovered", "healthy");
  }

  function renderWorkspaceSummaryCardsHtml(summary) {
    // Sprint 4 §8: Data Freshness -- last scan / stale-data warning /
    // rescan action (the existing "Rescan Workspace" button already
    // covers the action; this just makes staleness visible).
    const staleWarning = summary.is_stale
      ? `<span class="badge badge-warning u-mt-1">Stale${
          summary.hours_since_scan != null ? ` — ${Math.round(summary.hours_since_scan)}h old` : ""
        }</span>`
      : "";
    return `
      <div class="card-grid u-mb-4">
        <div class="card">
          <p class="card-muted">Last Scan</p>
          <p class="card-title">${summary.last_scan ? formatDate(summary.last_scan) : "Never"}</p>
          ${staleWarning}
        </div>
        <div class="card">
          <p class="card-muted">Projects Found</p>
          <p class="card-title">${summary.projects_found}</p>
        </div>
        <div class="card">
          <p class="card-muted">Projects Adopted</p>
          <p class="card-title">${summary.projects_adopted}</p>
        </div>
        <div class="card">
          <p class="card-muted">Ignored Projects</p>
          <p class="card-title">${summary.projects_ignored}</p>
        </div>
      </div>`;
  }

  function renderWorkspaceFilterTabsHtml() {
    return `
      <div class="workspace-filter-tabs u-mb-2">
        ${WORKSPACE_FILTERS.map(
          (f) => `
          <button type="button" class="btn btn-sm ${f.key === workspaceActiveFilter ? "btn-primary" : ""}"
                  data-workspace-filter="${f.key}">${escapeHtml(f.label)}</button>`
        ).join("")}
      </div>`;
  }

  function workspaceActionsHtml(item) {
    const adoptOrIgnore = item.adopted
      ? `<button type="button" class="link-btn" data-workspace-ignore="${escapeHtml(item.id)}">Ignore</button>`
      : `<button type="button" class="link-btn" data-workspace-adopt="${escapeHtml(item.id)}">Adopt</button>
         <button type="button" class="link-btn" data-workspace-ignore="${escapeHtml(item.id)}">Ignore</button>`;
    return `${adoptOrIgnore}
      <button type="button" class="link-btn" data-workspace-review="${escapeHtml(item.id)}">Review</button>`;
  }

  function renderWorkspaceChildRowHtml(child, parentId) {
    return `
      <tr data-workspace-row="${escapeHtml(child.id)}" data-workspace-child-of="${escapeHtml(parentId)}" class="workspace-child-row" hidden>
        <td class="u-pl-4">&#8627; ${escapeHtml(child.name)} <span class="badge">${escapeHtml(child.item_kind)}</span></td>
        <td class="card-muted">${escapeHtml(child.root_path)}</td>
        <td>${escapeHtml(child.classification)}</td>
        <td>${workspaceGitLabel(child)}</td>
        <td>${child.health_score != null ? healthBadge(child.health_score, child.project_context && child.project_context.health) : "—"}</td>
        <td>${Math.round((child.confidence_score || 0) * 100)}%</td>
        <td>${workspaceRiskBadge(child.move_risk)}</td>
        <td>${workspaceStatusBadge(child)}</td>
        <td>${workspaceActionsHtml(child)}</td>
      </tr>`;
  }

  function renderWorkspaceTopLevelRowHtml(item) {
    const childCount = (item.children || []).length;
    const expanded = workspaceExpandedIds.has(item.id);
    const expandBtn = childCount
      ? `<button type="button" class="link-btn" data-workspace-expand="${escapeHtml(item.id)}">${expanded ? "Collapse" : "Expand"} (${childCount})</button>`
      : "";
    const counts = [
      item.repository_count ? `${item.repository_count} repo${item.repository_count === 1 ? "" : "s"}` : "",
      item.component_count ? `${item.component_count} component${item.component_count === 1 ? "" : "s"}` : "",
      item.documentation_count ? `${item.documentation_count} doc folder${item.documentation_count === 1 ? "" : "s"}` : "",
      item.asset_library_count ? `${item.asset_library_count} asset folder${item.asset_library_count === 1 ? "" : "s"}` : "",
      item.internal_folder_count ? `${item.internal_folder_count} internal folder${item.internal_folder_count === 1 ? "" : "s"}` : "",
    ]
      .filter(Boolean)
      .join(", ");

    const rows = [
      `<tr data-workspace-row="${escapeHtml(item.id)}">
        <td>${escapeHtml(item.name)}</td>
        <td class="card-muted">${escapeHtml(item.root_path)}</td>
        <td>${escapeHtml(item.classification)}</td>
        <td>${workspaceGitLabel(item)}</td>
        <td>${item.health_score != null ? healthBadge(item.health_score, item.project_context && item.project_context.health) : "—"}</td>
        <td>${Math.round((item.confidence_score || 0) * 100)}%</td>
        <td>${workspaceRiskBadge(item.move_risk)}</td>
        <td>${workspaceStatusBadge(item)}</td>
        <td>
          ${workspaceActionsHtml(item)}
          ${expandBtn}
        </td>
      </tr>`,
    ];
    if (childCount) {
      rows.push(
        `<tr class="workspace-counts-row" data-workspace-counts-of="${escapeHtml(item.id)}">
           <td colspan="9" class="card-muted">${escapeHtml(counts)}</td>
         </tr>`
      );
      (item.children || []).forEach((child) => rows.push(renderWorkspaceChildRowHtml(child, item.id)));
    }
    return rows.join("");
  }

  function renderWorkspaceFlatRowHtml(item, extraLabel) {
    return `
      <tr data-workspace-row="${escapeHtml(item.id)}">
        <td>${escapeHtml(item.name)} <span class="badge">${escapeHtml(item.item_kind)}</span></td>
        <td class="card-muted">${escapeHtml(item.root_path)}</td>
        <td class="card-muted">${escapeHtml(extraLabel(item))}</td>
        <td>${workspaceStatusBadge(item)}</td>
        <td>${workspaceActionsHtml(item)}</td>
      </tr>`;
  }

  function renderWorkspaceTableHtml(items) {
    if (items.length === 0) {
      return '<p class="muted">Nothing to show for this filter.</p>';
    }
    if (workspaceActiveFilter === "top_level") {
      return `<table class="explorer-table">
        <thead>
          <tr>
            <th>Name</th><th>Folder</th><th>Type</th><th>Git</th>
            <th>Health</th><th>Confidence</th><th>Move Risk</th><th>Status</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>${items.map(renderWorkspaceTopLevelRowHtml).join("")}</tbody>
      </table>`;
    }
    if (workspaceActiveFilter === "repositories") {
      return `<table class="explorer-table">
        <thead><tr><th>Name</th><th>Folder</th><th>Parent project</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${items.map((i) => renderWorkspaceFlatRowHtml(i, (it) => it.parent_name || "—")).join("")}</tbody>
      </table>`;
    }
    if (workspaceActiveFilter === "ignored_excluded") {
      return `<table class="explorer-table">
        <thead><tr><th>Name</th><th>Folder</th><th>Reason</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${items
          .map((i) => renderWorkspaceFlatRowHtml(i, (it) => it.exclusion_reason || "ignored by you"))
          .join("")}</tbody>
      </table>`;
    }
    // needs_review
    return `<table class="explorer-table">
      <thead><tr><th>Name</th><th>Folder</th><th>Why it needs review</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody>${items
        .map((i) => renderWorkspaceFlatRowHtml(i, (it) => (it.boundary_evidence || [])[0] || "ambiguous signal"))
        .join("")}</tbody>
    </table>`;
  }

  function renderWorkspacePageHtml(summary, items) {
    return `
      <div class="section-heading">
        <h2>Workspace</h2>
        <button type="button" class="btn btn-sm btn-primary" id="workspace-rescan-btn">Rescan Workspace</button>
      </div>
      ${renderWorkspaceSummaryCardsHtml(summary)}
      <p id="workspace-root-line" class="card-muted u-mb-2">Scanning: ${escapeHtml(summary.root || "not configured")}</p>
      <div id="workspace-status"></div>
      ${renderWorkspaceFilterTabsHtml()}
      <div id="workspace-table-container">${renderWorkspaceTableHtml(items)}</div>`;
  }

  function workspaceReviewDetailHtml(item) {
    const d = item.discovery_detail || {};
    const reasonList = (label, reasons) =>
      reasons && reasons.length
        ? `<p class="card-muted u-mt-2"><strong>${escapeHtml(label)}:</strong></p><ul>${reasons
            .map((r) => `<li>${escapeHtml(r)}</li>`)
            .join("")}</ul>`
        : "";
    const parentLine = item.parent_item_id
      ? `<p class="card-muted">Parent project id: <code>${escapeHtml(item.parent_item_id)}</code></p>`
      : '<p class="card-muted">No parent -- top-level project.</p>';
    const overrideLine = item.override_action
      ? `<p class="card-muted u-mt-2">User override active: <strong>${escapeHtml(item.override_action)}</strong>${
          item.override_parent_id ? ` (parent: <code>${escapeHtml(item.override_parent_id)}</code>)` : ""
        } <button type="button" class="link-btn" data-workspace-clear-override="${escapeHtml(item.id)}">Clear override</button></p>`
      : "";
    return `
      <h3>${escapeHtml(item.name)} ${workspaceStatusBadge(item)}</h3>
      <p class="card-muted">${escapeHtml(item.root_path)}</p>
      <div class="rec-card-meta u-mt-2">
        <span class="badge">boundary: ${escapeHtml(item.item_kind)}</span>
        <span class="badge">classification: ${escapeHtml(item.classification)}</span>
        ${workspaceRiskBadge(item.move_risk)}
        <span class="badge">${escapeHtml(item.maturity)}</span>
        <span class="badge">${escapeHtml(item.commercial_readiness)}</span>
      </div>
      <p class="card-muted u-mt-2">Boundary confidence: <strong>${item.boundary_confidence}</strong></p>
      ${parentLine}
      ${reasonList("Detected-boundary evidence", item.boundary_evidence)}
      ${item.is_excluded ? `<p class="card-muted u-mt-2"><strong>Excluded:</strong> ${escapeHtml(item.exclusion_reason || "")}</p>` : ""}
      ${overrideLine}
      <p class="card-muted u-mt-2">Recommendation: <strong>${escapeHtml(item.recommendation)}</strong></p>
      ${reasonList("Why this move-risk rating", d.move_risk_reasons)}
      ${reasonList("Why this recommendation", d.recommendation_reasons)}
      <p class="card-muted u-mt-2">Languages: ${escapeHtml(Object.keys(d.languages || {}).join(", ") || "none detected")}</p>
      <p class="card-muted">Tests: ${d.has_tests ? "yes" : "no"} &middot; Docs folder: ${(d.doc_folders || []).length} &middot; Images: ${d.image_count || 0} &middot; Videos: ${d.video_count || 0}</p>
      ${
        item.notes && item.notes.length
          ? `<p class="card-muted u-mt-2"><strong>Notes:</strong></p><ul>${item.notes
              .map((n) => `<li>${escapeHtml(n.text)} <span class="card-muted">(${formatDate(n.created_at)})</span></li>`)
              .join("")}</ul>`
          : ""
      }
      <div class="u-mt-4">
        <p class="card-muted"><strong>Override this item's grouping:</strong></p>
        <button type="button" class="btn btn-sm" data-workspace-override-top="${escapeHtml(item.id)}">Treat as top-level project</button>
        <button type="button" class="btn btn-sm" data-workspace-override-ignore="${escapeHtml(item.id)}">Ignore</button>
      </div>`;
  }

  async function openWorkspaceReviewDetail(itemId) {
    detailOverlay.hidden = false;
    detailBody.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const item = await fetchJSON(`/workspace/discovered/${encodeURIComponent(itemId)}`);
      detailBody.innerHTML = workspaceReviewDetailHtml(item);
      wireWorkspaceReviewActions();
    } catch (err) {
      detailBody.innerHTML = `<p class="error-box">Could not load project: ${escapeHtml(err.message)}</p>`;
    }
  }

  function wireWorkspaceReviewActions() {
    const topBtn = detailBody.querySelector("[data-workspace-override-top]");
    if (topBtn) {
      topBtn.addEventListener("click", async () => {
        try {
          await postJSON(
            `/workspace/discovered/${encodeURIComponent(topBtn.dataset.workspaceOverrideTop)}/override`,
            { action: "top_level" }
          );
          showToast("Now treated as a top-level project");
          detailOverlay.hidden = true;
          await renderWorkspacePage();
        } catch (err) {
          showToast(`Could not apply override: ${err.message}`);
        }
      });
    }
    const ignoreBtn = detailBody.querySelector("[data-workspace-override-ignore]");
    if (ignoreBtn) {
      ignoreBtn.addEventListener("click", async () => {
        try {
          await postJSON(
            `/workspace/discovered/${encodeURIComponent(ignoreBtn.dataset.workspaceOverrideIgnore)}/ignore`,
            {}
          );
          showToast("Project ignored");
          detailOverlay.hidden = true;
          await renderWorkspacePage();
        } catch (err) {
          showToast(`Could not ignore: ${err.message}`);
        }
      });
    }
    const clearBtn = detailBody.querySelector("[data-workspace-clear-override]");
    if (clearBtn) {
      clearBtn.addEventListener("click", async () => {
        try {
          await postJSON(
            `/workspace/discovered/${encodeURIComponent(clearBtn.dataset.workspaceClearOverride)}/override/clear`,
            {}
          );
          showToast("Override cleared");
          detailOverlay.hidden = true;
          await renderWorkspacePage();
        } catch (err) {
          showToast(`Could not clear override: ${err.message}`);
        }
      });
    }
  }

  function wireWorkspacePageActions() {
    const statusEl = document.getElementById("workspace-status");
    const rescanBtn = document.getElementById("workspace-rescan-btn");
    if (rescanBtn) {
      rescanBtn.addEventListener("click", async () => {
        rescanBtn.disabled = true;
        rescanBtn.textContent = "Scanning…";
        if (statusEl) statusEl.innerHTML = '<p class="muted">Scanning the filesystem — this can take a few seconds…</p>';
        try {
          await postJSON("/workspace/rescan", {});
          showToast("Workspace rescanned");
          await renderWorkspacePage();
        } catch (err) {
          if (statusEl) statusEl.innerHTML = `<p class="error-box">Rescan failed: ${escapeHtml(err.message)}</p>`;
          rescanBtn.disabled = false;
          rescanBtn.textContent = "Rescan Workspace";
        }
      });
    }

    document.querySelectorAll("[data-workspace-filter]").forEach((el) => {
      el.addEventListener("click", async () => {
        workspaceActiveFilter = el.dataset.workspaceFilter;
        await renderWorkspacePage();
      });
    });

    document.querySelectorAll("[data-workspace-expand]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.workspaceExpand;
        if (workspaceExpandedIds.has(id)) {
          workspaceExpandedIds.delete(id);
        } else {
          workspaceExpandedIds.add(id);
        }
        document.querySelectorAll(`[data-workspace-child-of="${CSS.escape(id)}"]`).forEach((row) => {
          row.hidden = !workspaceExpandedIds.has(id);
        });
        el.textContent = el.textContent.replace(/^(Expand|Collapse)/, workspaceExpandedIds.has(id) ? "Collapse" : "Expand");
      });
    });

    document.querySelectorAll("[data-workspace-adopt]").forEach((el) => {
      el.addEventListener("click", async () => {
        try {
          await postJSON(`/workspace/discovered/${encodeURIComponent(el.dataset.workspaceAdopt)}/adopt`, {});
          showToast("Project adopted into Workspace");
          await renderWorkspacePage();
        } catch (err) {
          showToast(`Could not adopt: ${err.message}`);
        }
      });
    });

    document.querySelectorAll("[data-workspace-ignore]").forEach((el) => {
      el.addEventListener("click", async () => {
        try {
          await postJSON(`/workspace/discovered/${encodeURIComponent(el.dataset.workspaceIgnore)}/ignore`, {});
          showToast("Project ignored");
          await renderWorkspacePage();
        } catch (err) {
          showToast(`Could not ignore: ${err.message}`);
        }
      });
    });

    document.querySelectorAll("[data-workspace-review]").forEach((el) => {
      el.addEventListener("click", () => openWorkspaceReviewDetail(el.dataset.workspaceReview));
    });
  }

  async function fetchWorkspaceFilterItems(filter) {
    if (filter === "ignored_excluded") {
      const [excluded, allItems] = await Promise.all([
        fetchJSON("/workspace/discovered?view=excluded"),
        fetchJSON("/workspace/discovered?include_ignored=true"),
      ]);
      const byId = new Map();
      excluded.forEach((i) => byId.set(i.id, i));
      allItems.filter((i) => i.ignored).forEach((i) => byId.set(i.id, i));
      return Array.from(byId.values());
    }
    return fetchJSON(`/workspace/discovered?view=${encodeURIComponent(filter)}`);
  }

  async function renderWorkspacePage() {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading…</p>';
    const [summary, items] = await Promise.all([
      fetchJSON("/workspace/summary"),
      fetchWorkspaceFilterItems(workspaceActiveFilter),
    ]);
    viewRoot.innerHTML = renderWorkspacePageHtml(summary, items);
    wireWorkspacePageActions();
  }

  // =======================================================================
  // DISCOVERED PROJECT DETAIL (Sprint 4 §2)
  //
  // A live-data detail view for a discovered/adopted project, parallel to
  // (and never touching) `renderProjectDetail()` above, which remains the
  // detail view for manually-created /pi/projects. Every section reads
  // real data from the Discovery Engine / Workspace Adoption / AI
  // Sessions; a field that can't be discovered shows "Not yet defined"
  // rather than a fabricated value.
  // =======================================================================

  const NOT_YET_DEFINED = '<span class="muted">Not yet defined</span>';

  function dprojectOverviewHtml(item) {
    const d = item.discovery_detail || {};
    return `
      <table class="kv-table">
        <tr><td>Root folder</td><td>${escapeHtml(item.root_path)}</td></tr>
        <tr><td>Status</td><td>${workspaceStatusBadge(item)}</td></tr>
        <tr><td>Project type</td><td>${escapeHtml(item.classification)}</td></tr>
        <tr><td>Technology stack</td><td>${escapeHtml(Object.keys(d.languages || {}).join(", ")) || NOT_YET_DEFINED}</td></tr>
        <tr><td>Health</td><td>${item.health_score != null ? healthBadge(item.health_score, item.project_context && item.project_context.health) : NOT_YET_DEFINED}</td></tr>
        <tr><td>Confidence</td><td>${Math.round((item.confidence_score || 0) * 100)}%</td></tr>
        <tr><td>Move risk</td><td>${workspaceRiskBadge(item.move_risk)}</td></tr>
        <tr><td>Priority / Business value</td><td>${escapeHtml(item.priority)} / ${escapeHtml(item.business_value)}</td></tr>
      </table>`;
  }

  function dprojectGitHtml(item) {
    const d = item.discovery_detail || {};
    const git = d.git || {};
    if (!git.is_repo) {
      return `<p class="muted">Not a git repository.</p>`;
    }
    const commits = (git.recent_commits || [])
      .map((c) => `<li>${escapeHtml(c.message)} <span class="card-muted">(${formatDate(c.date)})</span></li>`)
      .join("") || `<li>${NOT_YET_DEFINED}</li>`;
    return `
      <table class="kv-table">
        <tr><td>Branch</td><td>${escapeHtml(git.branch || "—")}</td></tr>
        <tr><td>State</td><td>${git.is_dirty ? '<span class="badge badge-warning">dirty</span>' : '<span class="badge badge-healthy">clean</span>'}</td></tr>
        <tr><td>Last commit</td><td>${git.last_commit_message ? escapeHtml(git.last_commit_message) + " (" + formatDate(git.last_commit_date) + ")" : NOT_YET_DEFINED}</td></tr>
        <tr><td>Remote</td><td>${escapeHtml(git.remote_url || "—")}</td></tr>
      </table>
      <p class="card-muted u-mt-2">Recent commits:</p>
      <ul>${commits}</ul>`;
  }

  function dprojectDocumentationHtml(item) {
    const d = item.discovery_detail || {};
    return `
      <p>${escapeHtml(item.documentation_status || NOT_YET_DEFINED)}</p>
      <ul class="u-mt-1">
        <li>README: ${d.has_readme ? "yes" : "no"}</li>
        <li>ROADMAP: ${d.has_roadmap ? "yes" : "no"}</li>
        <li>CHANGELOG: ${d.has_changelog ? "yes" : "no"}</li>
        <li>Docs folder(s): ${(d.doc_folders || []).length}</li>
      </ul>`;
  }

  function dprojectChildrenHtml(item) {
    const children = item.children || [];
    if (!children.length) {
      return `<p class="muted">No nested repositories or components found.</p>`;
    }
    return `<ul>${children
      .map((c) => `<li>${escapeHtml(c.name)} <span class="badge">${escapeHtml(c.item_kind)}</span></li>`)
      .join("")}</ul>`;
  }

  function dprojectAssetsHtml(assets) {
    if (!assets || !assets.length) {
      return `<p class="muted">No reusable assets discovered.</p>`;
    }
    const rows = assets
      .slice(0, 20)
      .map(
        (a) => `<tr class="u-clickable" data-asset-preview="${escapeHtml(a.asset_id || "")}">
          <td>${a.preview_available && a.preview_url ? `<img src="${escapeHtml(a.preview_url)}" alt="" loading="lazy" class="asset-thumb-tiny" />` : ""} ${escapeHtml(a.filename)}</td>
          <td><span class="badge">${escapeHtml(a.category)}</span></td>
          <td>${(a.size_bytes / 1024).toFixed(1)} KB</td>
          <td>${formatDate(a.modified_at)}</td>
          <td>${a.reusable ? "yes" : "no"}</td>
        </tr>`
      )
      .join("");
    return `
      <table class="explorer-table">
        <thead><tr><th>Filename</th><th>Category</th><th>Size</th><th>Modified</th><th>Reusable</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${assets.length > 20 ? `<p class="card-muted u-mt-1">+ ${assets.length - 20} more</p>` : ""}`;
  }

  function dprojectTestsHtml(item) {
    return `<p>${escapeHtml(item.test_status || NOT_YET_DEFINED)}</p>`;
  }

  function dprojectAiSessionsHtml(item) {
    const ai = item.ai_sessions || {};
    const sessions = ai.sessions || [];
    if (!sessions.length) {
      return `<p class="muted">Not yet defined -- no AI Sessions recorded for this project yet.</p>`;
    }
    return `<ul>${sessions
      .map((s) => `<li>${escapeHtml(s.assistant)}: ${escapeHtml(s.title || "untitled")} <span class="card-muted">(${formatDate(s.last_used_at || s.started_at)})</span></li>`)
      .join("")}</ul>`;
  }

  function dprojectLatestSnapshotHtml(item) {
    const snapshot = (item.ai_sessions || {}).latest_snapshot;
    if (!snapshot) {
      return `<p class="muted">Not yet defined.</p>`;
    }
    return `<p>${escapeHtml(snapshot.summary || snapshot.accomplishments || "")}</p>
      <p class="card-muted">${formatDate(snapshot.created_at)}</p>`;
  }

  function dprojectNextActionHtml(item) {
    const na = item.next_action || {};
    if (!na.text) {
      return `<p class="muted">Not yet defined.</p>`;
    }
    return `
      <p>${escapeHtml(na.text)}</p>
      <p class="card-muted">Source: ${escapeHtml(na.source)}${na.source_path ? " (`" + escapeHtml(na.source_path) + "`)" : ""} &middot; confidence ${na.confidence}</p>`;
  }

  function dprojectRisksHtml(item) {
    const d = item.discovery_detail || {};
    const reasons = d.move_risk_reasons || [];
    if (!reasons.length) {
      return `<p class="muted">No move-risk or boundary issues flagged.</p>`;
    }
    return `<ul>${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>`;
  }

  function dprojectSectionHtml(title, bodyHtml) {
    return `<div class="page-section"><div class="section-heading"><h3>${escapeHtml(title)}</h3></div>${bodyHtml}</div>`;
  }

  function dprojectTimelineHtml(item) {
    const entries = item.timeline || [];
    if (!entries.length) {
      return `<p class="muted">Not yet defined.</p>`;
    }
    return `<ul>${entries
      .slice()
      .reverse()
      .map((e) => `<li>${escapeHtml(e.excerpt)} <span class="card-muted">(${formatDate(e.timestamp)})</span></li>`)
      .join("")}</ul>`;
  }

  async function renderDiscoveredProjectDetail(itemId) {
    viewRoot.innerHTML = '<p class="muted loading-pulse">Loading…</p>';
    let item;
    try {
      item = await fetchJSON(`/workspace/discovered/${encodeURIComponent(itemId)}`);
    } catch (err) {
      viewRoot.innerHTML = `<p class="error-box">Could not load project: ${escapeHtml(err.message)}</p>`;
      return;
    }
    let assets = [];
    try {
      assets = await fetchJSON(`/workspace/assets?project_id=${encodeURIComponent(itemId)}`);
    } catch (_) {
      /* assets are additive; ignore failure */
    }
    let activityForProject = [];
    try {
      // Sprint C1 (Consolidation): the server now filters by project_id
      // directly (restricting the underlying filesystem walk to this one
      // project) instead of this page fetching every adopted project's
      // activity and filtering it here.
      activityForProject = await fetchJSON(`/workspace/activity?project_id=${encodeURIComponent(itemId)}`);
    } catch (_) {
      /* additive */
    }

    viewRoot.innerHTML = `
      <div class="section-heading">
        <h2>${escapeHtml(item.name)} ${workspaceStatusBadge(item)}</h2>
        <div>
          ${
            item.adopted
              ? `<button type="button" class="btn btn-primary" id="dproject-resume-work-btn">&#9654; Resume Work</button>`
              : `<span class="card-muted">Adopt this project on the Workspace page to enable Resume Work</span>`
          }
          <button type="button" class="link-btn" data-workspace-review="${escapeHtml(item.id)}">Full boundary review</button>
        </div>
      </div>
      ${dprojectSectionHtml("Overview", dprojectOverviewHtml(item))}
      ${dprojectSectionHtml("Git", dprojectGitHtml(item))}
      ${dprojectSectionHtml("Documentation", dprojectDocumentationHtml(item))}
      ${dprojectSectionHtml("Repositories / Components", dprojectChildrenHtml(item))}
      ${dprojectSectionHtml("Assets", dprojectAssetsHtml(assets))}
      ${dprojectSectionHtml("Tests", dprojectTestsHtml(item))}
      ${dprojectSectionHtml(
        "Recent Activity",
        activityForProject.length
          ? `<ul>${activityForProject.map((e) => `<li>${escapeHtml(e.summary)} <span class="card-muted">(${formatDate(e.timestamp)})</span></li>`).join("")}</ul>`
          : '<p class="muted">Not yet defined.</p>'
      )}
      ${dprojectSectionHtml("AI Sessions", dprojectAiSessionsHtml(item))}
      ${dprojectSectionHtml("Latest Snapshot", dprojectLatestSnapshotHtml(item))}
      ${dprojectSectionHtml("Timeline", dprojectTimelineHtml(item))}
      ${dprojectSectionHtml("Next Action", dprojectNextActionHtml(item))}
      ${dprojectSectionHtml("Risks / Blockers", dprojectRisksHtml(item))}
    `;

    document.querySelectorAll("[data-workspace-review]").forEach((el) => {
      el.addEventListener("click", () => openWorkspaceReviewDetail(el.dataset.workspaceReview));
    });
    const resumeBtn = document.getElementById("dproject-resume-work-btn");
    if (resumeBtn) {
      resumeBtn.addEventListener("click", () => triggerResumeWork(item.id));
    }
    document.querySelectorAll("[data-asset-preview]").forEach((el) => {
      if (el.dataset.assetPreview) el.addEventListener("click", () => openAssetDetail(el.dataset.assetPreview));
    });
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------

  tickClock();
  loadHeaderWorkspaces().then(route);
})();
