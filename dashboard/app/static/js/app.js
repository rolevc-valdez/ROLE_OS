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

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  function debounce(fn, wait) {
    let t = null;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function healthTier(score) {
    if (score >= 70) return "healthy";
    if (score >= 40) return "warning";
    return "critical";
  }

  function healthColorVar(score) {
    const tier = healthTier(score);
    return tier === "healthy" ? "var(--status-healthy)" : tier === "warning" ? "var(--status-warning)" : "var(--status-critical)";
  }

  function healthRingHtml(score, size) {
    const cls = size === "sm" ? "health-ring health-ring-sm" : "health-ring";
    const style = `--ring-value:${Math.max(0, Math.min(100, score))}; --ring-color:${healthColorVar(score)};`;
    return `<div class="${cls}" style="${style}"><span class="health-ring-value">${score}</span></div>`;
  }

  function priorityBadge(priority) {
    const p = (priority || "medium").toLowerCase();
    return `<span class="badge badge-priority-${escapeHtml(p)}">${escapeHtml(p)}</span>`;
  }

  function healthBadge(score) {
    const tier = healthTier(score);
    return `<span class="badge badge-${tier}">${tier}</span>`;
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
    home: renderHome,
    projects: renderProjectsList,
    project: renderProjectDetail,
    knowledge: renderKnowledge,
    explorer: renderExplorerPage,
    advisor: renderAdvisorPage,
    graph: renderGraphPage,
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
    const renderFn = routes[view] || renderHome;
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
    if (view === "home") renderHome();
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
        return `
        <div class="card rec-card">
          <div class="rec-card-header">
            <div>
              <p class="rec-card-title">${escapeHtml(name)}</p>
              <div class="rec-card-meta">
                ${healthBadge(score)}
                ${priorityBadge(priority)}
                <span class="badge">Effort: ${escapeHtml(rec.estimated_effort)}</span>
              </div>
            </div>
            ${healthRingHtml(score, "sm")}
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
        const healthy = wsProjects.filter((p) => healthTier(p.health_score) === "healthy").length;
        const warning = wsProjects.filter((p) => healthTier(p.health_score) === "warning").length;
        const critical = wsProjects.filter((p) => healthTier(p.health_score) === "critical").length;
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
  // PROJECTS LIST
  // =======================================================================

  async function renderProjectsList() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Projects</h2></div>
      <div id="projects-grid" class="card-grid"><p class="muted loading-pulse">Loading…</p></div>
    `;
    const workspaceFilter = workspaceSelect.value;
    const projects = await fetchJSON(`/pi/projects${workspaceFilter ? `?workspace=${encodeURIComponent(workspaceFilter)}` : ""}`);
    const el = document.getElementById("projects-grid");
    if (!projects.length) {
      el.innerHTML = '<p class="muted">No projects yet.</p>';
      return;
    }
    el.innerHTML = projects
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
      .join("");
  }

  // =======================================================================
  // PROJECT DETAIL
  // =======================================================================

  async function renderProjectDetail(projectId) {
    if (!projectId) {
      navigate("projects");
      return;
    }
    const [project, allProjects, capabilities, consumed, dependencies, dependents, recs] = await Promise.all([
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}`),
      fetchJSON("/pi/projects"),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities/consumed`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependencies`),
      fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependents`),
      fetchJSON(`/advisor/recommendations?project_id=${encodeURIComponent(projectId)}`),
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
  // CONVERSATION EXPLORER (Sprint B1.5)
  //
  // Browses/searches/filters imported conversations and lets you inspect,
  // export, or delete one. No AI, no extraction, no graph, no advisor --
  // strictly a read/manage view over what Sprint B1's importer persisted.
  // =======================================================================

  let explorerState = null;

  function defaultExplorerState() {
    return { page: 1, pageSize: 20, sortBy: "imported_at", sortDir: "desc", q: "", source: "", status: "", importedPreset: "" };
  }

  function importedAfterForPreset(preset) {
    const now = new Date();
    if (preset === "today") return new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    if (preset === "week") {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return d.toISOString();
    }
    if (preset === "month") return new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    return null;
  }

  async function renderExplorerPage() {
    explorerState = defaultExplorerState();
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Explorer</h2></div>
      <div id="explorer-metrics" class="health-dashboard-grid u-mb-4"></div>
      <div class="card page-section">
        <div class="graph-toolbar">
          <input id="explorer-search-input" type="search" placeholder="Search title, content, source, or ID..." />
          <select id="explorer-source-select"><option value="">All sources</option></select>
          <select id="explorer-status-select"><option value="">All statuses</option></select>
          <select id="explorer-imported-select">
            <option value="">Imported: any time</option>
            <option value="today">Imported today</option>
            <option value="week">Imported this week</option>
            <option value="month">Imported this month</option>
          </select>
          <select id="explorer-sort-select">
            <option value="imported_at">Sort: Import date</option>
            <option value="created_at">Sort: Conversation date</option>
            <option value="title">Sort: Title</option>
            <option value="message_count">Sort: Message count</option>
          </select>
          <button id="explorer-sort-dir-btn" type="button" class="btn btn-sm">↓ Desc</button>
        </div>
      </div>
      <div class="card page-section">
        <div id="explorer-list-wrap"><p class="muted loading-pulse">Loading…</p></div>
        <div id="explorer-pagination" class="explorer-pagination"></div>
      </div>
    `;

    loadExplorerMetrics();
    loadExplorerFacets();
    wireExplorerControls();
    await loadExplorerList();
  }

  async function loadExplorerMetrics() {
    const el = document.getElementById("explorer-metrics");
    try {
      const metrics = await fetchJSON("/import/metrics");
      const indicators = [
        { label: "Imported Conversations", value: metrics.imported_conversations },
        { label: "Pending Processing", value: metrics.pending_processing },
        { label: "Processed", value: metrics.processed },
        { label: "Knowledge Objects", value: metrics.knowledge_objects },
        { label: "Projects", value: metrics.projects },
        { label: "Decisions", value: metrics.decisions },
        { label: "Assets", value: metrics.assets },
      ];
      el.innerHTML = indicators
        .map(
          (ind, i) => `
        <div class="card u-text-center">
          <div class="card-muted u-fs-12 u-mb-2">${escapeHtml(ind.label)}</div>
          <div id="explorer-metric-${i}" class="u-fs-26">0</div>
        </div>`
        )
        .join("");
      indicators.forEach((ind, i) => animateCount(document.getElementById(`explorer-metric-${i}`), ind.value));
    } catch (err) {
      el.innerHTML = `<p class="error-box">Could not load metrics: ${escapeHtml(err.message)}</p>`;
    }
  }

  async function loadExplorerFacets() {
    try {
      const facets = await fetchJSON("/import/facets");
      const sourceSelect = document.getElementById("explorer-source-select");
      const statusSelect = document.getElementById("explorer-status-select");
      if (sourceSelect) {
        sourceSelect.innerHTML =
          '<option value="">All sources</option>' +
          facets.sources.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
      }
      if (statusSelect) {
        statusSelect.innerHTML =
          '<option value="">All statuses</option>' +
          facets.statuses.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
      }
    } catch (err) {
      console.error("Could not load import facets", err);
    }
  }

  function wireExplorerControls() {
    document.getElementById("explorer-search-input").addEventListener(
      "input",
      debounce((e) => {
        explorerState.q = e.target.value.trim();
        explorerState.page = 1;
        loadExplorerList();
      }, 250)
    );
    document.getElementById("explorer-source-select").addEventListener("change", (e) => {
      explorerState.source = e.target.value;
      explorerState.page = 1;
      loadExplorerList();
    });
    document.getElementById("explorer-status-select").addEventListener("change", (e) => {
      explorerState.status = e.target.value;
      explorerState.page = 1;
      loadExplorerList();
    });
    document.getElementById("explorer-imported-select").addEventListener("change", (e) => {
      explorerState.importedPreset = e.target.value;
      explorerState.page = 1;
      loadExplorerList();
    });
    document.getElementById("explorer-sort-select").addEventListener("change", (e) => {
      explorerState.sortBy = e.target.value;
      loadExplorerList();
    });
    document.getElementById("explorer-sort-dir-btn").addEventListener("click", (e) => {
      explorerState.sortDir = explorerState.sortDir === "desc" ? "asc" : "desc";
      e.target.textContent = explorerState.sortDir === "desc" ? "↓ Desc" : "↑ Asc";
      loadExplorerList();
    });
  }

  function explorerQueryString() {
    const params = new URLSearchParams();
    params.set("page", explorerState.page);
    params.set("page_size", explorerState.pageSize);
    params.set("sort_by", explorerState.sortBy);
    params.set("sort_dir", explorerState.sortDir);
    if (explorerState.q) params.set("q", explorerState.q);
    if (explorerState.source) params.set("source", explorerState.source);
    if (explorerState.status) params.set("status", explorerState.status);
    const importedAfter = importedAfterForPreset(explorerState.importedPreset);
    if (importedAfter) params.set("imported_after", importedAfter);
    return params.toString();
  }

  async function loadExplorerList() {
    const listEl = document.getElementById("explorer-list-wrap");
    const pageEl = document.getElementById("explorer-pagination");
    listEl.innerHTML = '<p class="muted loading-pulse">Loading…</p>';
    try {
      const result = await fetchJSON(`/import/conversations?${explorerQueryString()}`);
      listEl.innerHTML = explorerTableHtml(result.items);
      pageEl.innerHTML = explorerPaginationHtml(result);
      wireExplorerRowActions();
      wireExplorerPagination(result);
    } catch (err) {
      listEl.innerHTML = `<p class="error-box">${escapeHtml(err.message)}</p>`;
      pageEl.innerHTML = "";
    }
  }

  function explorerTableHtml(items) {
    if (!items.length) return '<p class="muted">No imported conversations match these filters.</p>';
    const rows = items
      .map(
        (c) => `
      <tr data-conversation-id="${escapeHtml(c.id)}">
        <td class="u-clickable" data-explorer-open="${escapeHtml(c.id)}">${escapeHtml(c.title)}</td>
        <td><span class="badge">${escapeHtml(c.source)}</span></td>
        <td>${formatDate(c.imported_at)}</td>
        <td>${formatDate(c.created_at)}</td>
        <td>${c.message_count}</td>
        <td><span class="badge badge-info">${escapeHtml(c.status)}</span></td>
        <td>
          <button type="button" class="link-btn" data-explorer-open="${escapeHtml(c.id)}">View</button>
          <button type="button" class="link-btn" data-explorer-export="${escapeHtml(c.id)}">Export</button>
          <button type="button" class="link-btn" data-explorer-delete="${escapeHtml(c.id)}">Delete</button>
        </td>
      </tr>`
      )
      .join("");
    return `
      <table class="explorer-table">
        <thead><tr><th>Title</th><th>Source</th><th>Import Date</th><th>Conversation Date</th><th>Messages</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function explorerPaginationHtml(result) {
    const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
    return `
      <button type="button" class="btn btn-sm" id="explorer-prev-btn" ${result.page <= 1 ? "disabled" : ""}>&larr; Prev</button>
      <span class="muted">Page ${result.page} of ${totalPages} &middot; ${result.total} conversation${result.total === 1 ? "" : "s"}</span>
      <button type="button" class="btn btn-sm" id="explorer-next-btn" ${result.page >= totalPages ? "disabled" : ""}>Next &rarr;</button>
    `;
  }

  function wireExplorerPagination(result) {
    const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
    const prevBtn = document.getElementById("explorer-prev-btn");
    const nextBtn = document.getElementById("explorer-next-btn");
    if (prevBtn) prevBtn.addEventListener("click", () => {
      if (explorerState.page > 1) {
        explorerState.page -= 1;
        loadExplorerList();
      }
    });
    if (nextBtn) nextBtn.addEventListener("click", () => {
      if (explorerState.page < totalPages) {
        explorerState.page += 1;
        loadExplorerList();
      }
    });
  }

  function wireExplorerRowActions() {
    document.querySelectorAll("[data-explorer-open]").forEach((el) => {
      el.addEventListener("click", () => openConversationDetail(el.dataset.explorerOpen));
    });
    document.querySelectorAll("[data-explorer-export]").forEach((el) => {
      el.addEventListener("click", () => exportConversation(el.dataset.explorerExport));
    });
    document.querySelectorAll("[data-explorer-delete]").forEach((el) => {
      el.addEventListener("click", () => deleteConversationWithConfirm(el.dataset.explorerDelete, loadExplorerList));
    });
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
    `;
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
          if (parseHash().view === "explorer") loadExplorerList();
        });
      });
    } catch (err) {
      detailBody.innerHTML = `<p class="error-box">Could not load conversation: ${escapeHtml(err.message)}</p>`;
    }
  }

  // =======================================================================
  // ADVISOR PAGE
  // =======================================================================

  async function renderAdvisorPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Advisor</h2></div>
      <div class="card page-section">
        <p class="card-title">Daily Brief</p>
        <pre id="advisor-brief" class="card-muted u-pre-wrap">Loading…</pre>
      </div>
      <div id="advisor-groups"><p class="muted loading-pulse">Loading recommendations…</p></div>
    `;

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

  async function renderAssetsPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Assets</h2></div>
      <div id="assets-list" class="card-grid"><p class="muted loading-pulse">Loading…</p></div>
    `;
    const assets = await fetchJSON("/graph?node_type=Asset");
    const el = document.getElementById("assets-list");
    if (!assets.nodes.length) {
      el.innerHTML = '<p class="muted">No assets recorded yet.</p>';
      return;
    }
    el.innerHTML = assets.nodes
      .map(
        (n) => `
      <div class="card">
        <p class="card-title">${escapeHtml(n.label)}</p>
        <p class="card-muted">${escapeHtml(n.data.status || n.data.source || "asset")}</p>
      </div>`
      )
      .join("");
  }

  // =======================================================================
  // SETTINGS PAGE
  // =======================================================================

  async function renderSettingsPage() {
    viewRoot.innerHTML = `
      <div class="section-heading"><h2>Settings</h2></div>
      <div class="card u-max-w-480">
        <p class="card-title">System status</p>
        <table class="kv-table" id="settings-table"><tr><td class="muted">Loading…</td></tr></table>
      </div>
      <p class="muted u-mt-4">
        ROLE OS Command Center is a UI-only layer over the existing Builder,
        Knowledge Engine, Project Intelligence, Advisor, and Knowledge Graph
        APIs — nothing here writes to a database directly.
      </p>
    `;
    const health = await fetchJSON("/health");
    document.getElementById("settings-table").innerHTML = `
      <tr><th>App</th><td>${escapeHtml(health.app)}</td></tr>
      <tr><th>Version</th><td>${escapeHtml(health.version)}</td></tr>
      <tr><th>Status</th><td>${escapeHtml(health.status)}</td></tr>
      <tr><th>Knowledge database connected</th><td>${health.database_connected ? "Yes" : "No"}</td></tr>
    `;
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

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------

  tickClock();
  loadHeaderWorkspaces().then(route);
})();
