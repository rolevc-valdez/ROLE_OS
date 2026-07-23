/* ROLE OS Dashboard — plain JavaScript, no framework. */

(() => {
  "use strict";

  const els = {
    searchForm: document.getElementById("search-form"),
    searchInput: document.getElementById("search-input"),
    clearSearch: document.getElementById("clear-search"),
    resultsTitle: document.getElementById("results-title"),
    cardList: document.getElementById("card-list"),
    projectList: document.getElementById("project-list"),
    timelineList: document.getElementById("timeline-list"),
    overlay: document.getElementById("detail-overlay"),
    detailBody: document.getElementById("detail-body"),
    detailClose: document.getElementById("detail-close"),
  };

  let activeProject = null;

  async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const body = await resp.json();
        detail = body.detail || detail;
      } catch (_) {
        /* ignore parse errors on error body */
      }
      const error = new Error(detail);
      error.status = resp.status;
      throw error;
    }
    return resp.json();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  function formatDate(iso) {
    if (!iso) return "Unknown date";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function renderError(container, message) {
    container.innerHTML = `<li class="error-box">${escapeHtml(message)}</li>`;
  }

  // ---- Projects -------------------------------------------------------

  async function loadProjects() {
    try {
      const projects = await fetchJSON("/projects");
      if (!projects.length) {
        els.projectList.innerHTML = '<li class="muted">No projects yet.</li>';
        return;
      }
      els.projectList.innerHTML = projects
        .map(
          (p) => `
            <li>
              <button type="button" data-project="${escapeHtml(p.project)}">
                <span>${escapeHtml(p.project)}</span>
                <span class="count">${p.count}</span>
              </button>
            </li>`
        )
        .join("");

      els.projectList.querySelectorAll("button[data-project]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const project = btn.dataset.project;
          activeProject = activeProject === project ? null : project;
          highlightActiveProject();
          if (activeProject) {
            els.searchInput.value = activeProject;
            runSearch(activeProject);
          } else {
            els.searchInput.value = "";
            resetToRecent();
          }
        });
      });
    } catch (err) {
      renderError(els.projectList, `Could not load projects: ${err.message}`);
    }
  }

  function highlightActiveProject() {
    els.projectList.querySelectorAll("button[data-project]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.project === activeProject);
    });
  }

  // ---- Card list (recent / search results) -----------------------------

  function cardListItemHtml(card) {
    return `
      <li class="card-item" tabindex="0" data-id="${escapeHtml(card.conversation_id)}">
        <div class="card-item-header">
          <span class="card-item-title">${escapeHtml(card.title)}</span>
          <span class="card-item-meta">
            <span class="badge">${escapeHtml(card.project)}</span>
            ${escapeHtml(formatDate(card.date))}
          </span>
        </div>
        <div class="card-item-summary">${escapeHtml(card.summary || "No summary available.")}</div>
      </li>`;
  }

  function renderCardList(cards) {
    if (!cards.length) {
      els.cardList.innerHTML = '<li class="muted">No knowledge cards found.</li>';
      return;
    }
    els.cardList.innerHTML = cards.map(cardListItemHtml).join("");
    els.cardList.querySelectorAll(".card-item").forEach((item) => {
      const open = () => openDetail(item.dataset.id);
      item.addEventListener("click", open);
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      });
    });
  }

  async function loadRecent() {
    els.resultsTitle.textContent = "Recent knowledge cards";
    els.clearSearch.hidden = true;
    try {
      const cards = await fetchJSON("/ui/recent?limit=10");
      renderCardList(cards);
    } catch (err) {
      renderError(els.cardList, `Could not load recent cards: ${err.message}`);
    }
  }

  async function runSearch(query) {
    els.resultsTitle.textContent = `Search results for "${query}"`;
    els.clearSearch.hidden = false;
    try {
      const cards = await fetchJSON(`/search?q=${encodeURIComponent(query)}`);
      renderCardList(cards);
    } catch (err) {
      renderError(els.cardList, `Search failed: ${err.message}`);
    }
  }

  function resetToRecent() {
    activeProject = null;
    highlightActiveProject();
    loadRecent();
  }

  // ---- Timeline ---------------------------------------------------------

  async function loadTimeline() {
    try {
      const entries = await fetchJSON("/ui/timeline?limit=100");
      if (!entries.length) {
        els.timelineList.innerHTML = '<li class="muted">No timeline data yet.</li>';
        return;
      }
      els.timelineList.innerHTML = entries
        .slice()
        .reverse()
        .map(
          (entry) => `
            <li class="timeline-item" data-id="${escapeHtml(entry.conversation_id)}">
              <div class="timeline-date">${escapeHtml(formatDate(entry.date))} &middot; ${escapeHtml(entry.project)}</div>
              <div class="timeline-title">${escapeHtml(entry.title)}</div>
            </li>`
        )
        .join("");
      els.timelineList.querySelectorAll(".timeline-item").forEach((item) => {
        item.addEventListener("click", () => openDetail(item.dataset.id));
      });
    } catch (err) {
      renderError(els.timelineList, `Could not load timeline: ${err.message}`);
    }
  }

  // ---- Detail overlay -----------------------------------------------------

  function listSection(title, items) {
    if (!items || !items.length) return "";
    const lis = items.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
    return `<div class="detail-section"><h3>${escapeHtml(title)}</h3><ul>${lis}</ul></div>`;
  }

  function tagSection(title, items) {
    if (!items || !items.length) return "";
    const spans = items.map((x) => `<span class="tag">${escapeHtml(x)}</span>`).join("");
    return `<div class="detail-section"><h3>${escapeHtml(title)}</h3>${spans}</div>`;
  }

  async function openDetail(id) {
    els.overlay.hidden = false;
    els.detailBody.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const card = await fetchJSON(`/knowledge/${encodeURIComponent(id)}`);
      els.detailBody.innerHTML = `
        <h2 id="detail-title" class="detail-title">${escapeHtml(card.title)}</h2>
        <div class="detail-meta">
          <span class="badge">${escapeHtml(card.project)}</span>
          ${escapeHtml(card.category)} &middot; ${escapeHtml(card.status)} &middot;
          ${escapeHtml(formatDate(card.date))}
        </div>
        <div class="detail-section">
          <h3>Summary</h3>
          <p>${escapeHtml(card.summary || "No summary available.")}</p>
        </div>
        ${listSection("Decisions", card.decisions)}
        ${listSection("Deliverables", card.deliverables)}
        ${listSection("To-dos", card.todos)}
        ${tagSection("People", card.people)}
        ${tagSection("Applications", card.applications)}
        ${tagSection("Tags", card.tags)}
      `;
    } catch (err) {
      const message = err.status === 404 ? "Knowledge card not found." : `Could not load card: ${err.message}`;
      els.detailBody.innerHTML = `<p class="error-box">${escapeHtml(message)}</p>`;
    }
  }

  function closeDetail() {
    els.overlay.hidden = true;
    els.detailBody.innerHTML = "";
  }

  els.detailClose.addEventListener("click", closeDetail);
  els.overlay.addEventListener("click", (e) => {
    if (e.target === els.overlay) closeDetail();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !els.overlay.hidden) closeDetail();
  });

  // ---- Search form --------------------------------------------------------

  els.searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = els.searchInput.value.trim();
    if (!query) {
      resetToRecent();
      return;
    }
    activeProject = null;
    highlightActiveProject();
    runSearch(query);
  });

  els.clearSearch.addEventListener("click", () => {
    els.searchInput.value = "";
    resetToRecent();
  });

  // ---- Init -----------------------------------------------------------------

  loadProjects();
  loadRecent();
  loadTimeline();
})();

/* ROLE OS Dashboard — Project Intelligence (Epic 1), plain JavaScript. */

(() => {
  "use strict";

  const piEls = {
    tabButtons: document.querySelectorAll(".tab-btn"),
    knowledgeTab: document.getElementById("knowledge-tab"),
    projectsTab: document.getElementById("projects-tab"),
    advisorTab: document.getElementById("advisor-tab"),
    workspaceSelect: document.getElementById("workspace-select"),
    listView: document.getElementById("pi-list-view"),
    projectList: document.getElementById("pi-project-list"),
    detailView: document.getElementById("pi-detail-view"),
    detailBody: document.getElementById("pi-detail-body"),
    backBtn: document.getElementById("pi-back-btn"),
    graphTab: document.getElementById("graph-tab"),
  };

  if (!piEls.projectsTab) return; // template not present (shouldn't happen)

  async function fetchJSON(url) {
    const resp = await fetch(url);
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
    return resp.json();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  // ---- Tabs -----------------------------------------------------------

  let projectsInitialized = false;

  piEls.tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      piEls.tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      piEls.knowledgeTab.hidden = tab !== "knowledge";
      piEls.knowledgeTab.classList.toggle("active", tab === "knowledge");
      piEls.projectsTab.hidden = tab !== "projects";
      if (piEls.advisorTab) piEls.advisorTab.hidden = tab !== "advisor";
      if (piEls.graphTab) piEls.graphTab.hidden = tab !== "graph";
      if (tab === "projects" && !projectsInitialized) {
        projectsInitialized = true;
        initProjectsTab();
      }
      document.dispatchEvent(new CustomEvent("roleos:tabchange", { detail: { tab } }));
    });
  });

  // ---- Workspace selector + project list --------------------------------

  async function initProjectsTab() {
    await loadWorkspaces();
    await loadProjectList();
    piEls.workspaceSelect.addEventListener("change", loadProjectList);
  }

  async function loadWorkspaces() {
    try {
      const workspaces = await fetchJSON("/pi/workspaces");
      const options = workspaces
        .map((w) => `<option value="${escapeHtml(w.name)}">${escapeHtml(w.name)} (${w.project_count})</option>`)
        .join("");
      piEls.workspaceSelect.innerHTML = `<option value="">All workspaces</option>${options}`;
    } catch (err) {
      // Non-fatal: leave just "All workspaces" if this fails.
      console.error("Could not load workspaces", err);
    }
  }

  function healthClass(score) {
    if (score >= 70) return "health-good";
    if (score >= 40) return "health-ok";
    return "health-bad";
  }

  function projectCardHtml(project) {
    return `
      <li class="pi-project-card" data-id="${escapeHtml(project.id)}" tabindex="0">
        <div class="pi-project-card-header">
          <div>
            <div class="pi-project-name">${escapeHtml(project.name)}</div>
            <div class="pi-project-meta">
              <span class="badge">${escapeHtml(project.workspace)}</span>
              <span class="badge">${escapeHtml(project.status)}</span>
              <span class="badge">${escapeHtml(project.priority)}</span>
            </div>
          </div>
          <div class="health-ring ${healthClass(project.health_score)}" title="Health score">${project.health_score}</div>
        </div>
        <div class="pi-project-desc">${escapeHtml(project.description || "No description yet.")}</div>
      </li>`;
  }

  async function loadProjectList() {
    const workspace = piEls.workspaceSelect.value;
    const url = workspace ? `/pi/projects?workspace=${encodeURIComponent(workspace)}` : "/pi/projects";
    try {
      const projects = await fetchJSON(url);
      if (!projects.length) {
        piEls.projectList.innerHTML = '<li class="muted">No projects yet in this workspace.</li>';
        return;
      }
      piEls.projectList.innerHTML = projects.map(projectCardHtml).join("");
      piEls.projectList.querySelectorAll(".pi-project-card").forEach((card) => {
        card.addEventListener("click", () => openProjectDetail(card.dataset.id));
        card.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openProjectDetail(card.dataset.id);
          }
        });
      });
    } catch (err) {
      piEls.projectList.innerHTML = `<li class="error-box">Could not load projects: ${escapeHtml(err.message)}</li>`;
    }
  }

  // ---- Project detail page ------------------------------------------------

  function healthBreakdownHtml(breakdown) {
    const labels = {
      recent_activity: "Recent activity",
      open_todos: "Open to-dos",
      unresolved_decisions: "Unresolved decisions",
      missing_deliverables: "Deliverables delivered",
      recent_conversations: "Recent conversations",
      recent_commits: "Recent commits",
    };
    return Object.entries(breakdown)
      .map(
        ([key, value]) => `
          <div class="pi-health-signal">
            <span class="pi-health-signal-name">${escapeHtml(labels[key] || key)}</span>
            <span class="pi-health-bar-track"><span class="pi-health-bar-fill" style="width:${value}%"></span></span>
            <span>${value}</span>
          </div>`
      )
      .join("");
  }

  function listOrEmpty(items, render, emptyText) {
    if (!items || !items.length) return `<li class="muted">${escapeHtml(emptyText)}</li>`;
    return items.map(render).join("");
  }

  function collectionSectionHtml(title, items, renderItem, emptyText) {
    return `
      <div class="pi-subsection">
        <h4>${escapeHtml(title)} (${items ? items.length : 0})</h4>
        <ul>${listOrEmpty(items, renderItem, emptyText)}</ul>
      </div>`;
  }

  async function openProjectDetail(projectId) {
    piEls.listView.hidden = true;
    piEls.detailView.hidden = false;
    piEls.detailBody.innerHTML = '<p class="muted">Loading…</p>';

    try {
      const [project, health, capabilities, consumed, dependencies, dependents] = await Promise.all([
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}`),
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/health`),
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities`),
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/capabilities/consumed`),
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependencies`),
        fetchJSON(`/pi/projects/${encodeURIComponent(projectId)}/dependents`),
      ]);

      piEls.detailBody.innerHTML = `
        <div class="pi-detail-header">
          <div class="pi-detail-title-block">
            <h2>${escapeHtml(project.name)}</h2>
            <div class="pi-badges">
              <span class="badge">${escapeHtml(project.workspace)}</span>
              <span class="badge">${escapeHtml(project.status)}</span>
              <span class="badge">${escapeHtml(project.priority)}</span>
              ${project.owner ? `<span class="badge">Owner: ${escapeHtml(project.owner)}</span>` : ""}
              ${project.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}
            </div>
          </div>
          <div class="health-ring ${healthClass(health.score)}" title="Health score">${health.score}</div>
        </div>

        <div class="pi-section">
          <h3>Description</h3>
          <p>${escapeHtml(project.description || "No description yet.")}</p>
        </div>

        <div class="pi-section">
          <h3>Health Score breakdown</h3>
          <div class="pi-health-breakdown">${healthBreakdownHtml(health.breakdown)}</div>
        </div>

        <div class="pi-section pi-two-col">
          <div class="pi-subsection">
            <h4>Capabilities provided (${capabilities.length})</h4>
            <ul>${listOrEmpty(
              capabilities,
              (c) => `<li><strong>${escapeHtml(c.name)}</strong>${c.description ? " — " + escapeHtml(c.description) : ""}</li>`,
              "This project doesn't expose any capabilities yet."
            )}</ul>
          </div>
          <div class="pi-subsection">
            <h4>Capabilities consumed (${consumed.length})</h4>
            <ul>${listOrEmpty(
              consumed,
              (c) => `<li><strong>${escapeHtml(c.name)}</strong> from ${escapeHtml(c.provider_project_name)}</li>`,
              "This project doesn't consume any capabilities yet."
            )}</ul>
          </div>
        </div>

        <div class="pi-section pi-two-col">
          <div class="pi-subsection">
            <h4>Depends on (${dependencies.length})</h4>
            <ul>${listOrEmpty(
              dependencies,
              (d) => `<li>${escapeHtml(d.depends_on_project_name)}${d.note ? " — " + escapeHtml(d.note) : ""}</li>`,
              "No dependencies recorded."
            )}</ul>
          </div>
          <div class="pi-subsection">
            <h4>Depended on by (${dependents.length})</h4>
            <ul>${listOrEmpty(
              dependents,
              (d) => `<li>${escapeHtml(d.dependent_project_name)}</li>`,
              "No other project depends on this one yet."
            )}</ul>
          </div>
        </div>

        <div class="pi-section">
          <h3>Collections</h3>
          <div class="pi-collections-grid">
            ${collectionSectionHtml("Notes", project.notes, (n) => `<li>${escapeHtml(n.text)}</li>`, "No notes yet.")}
            ${collectionSectionHtml(
              "Decisions",
              project.decisions,
              (d) => `<li>${escapeHtml(d.text)} <span class="badge">${escapeHtml(d.status || "resolved")}</span></li>`,
              "No decisions logged yet."
            )}
            ${collectionSectionHtml(
              "Open TODOs",
              project.todos,
              (t) => `<li>${escapeHtml(t.text)} <span class="badge">${escapeHtml(t.status || "open")}</span></li>`,
              "No to-dos yet."
            )}
            ${collectionSectionHtml(
              "Deliverables",
              project.deliverables,
              (d) => `<li>${escapeHtml(d.text)} <span class="badge">${escapeHtml(d.status || "planned")}</span></li>`,
              "No deliverables tracked yet."
            )}
            ${collectionSectionHtml("Assets", project.assets, (a) => `<li>${escapeHtml(a.name || a.text || "Untitled asset")}</li>`, "No assets yet.")}
            ${collectionSectionHtml("Prompts", project.prompts, (p) => `<li>${escapeHtml(p.text)}</li>`, "No prompts captured yet.")}
            ${collectionSectionHtml(
              "Conversations",
              project.conversations,
              (c) => `<li>${escapeHtml(c)}</li>`,
              "No conversations linked yet."
            )}
            ${collectionSectionHtml(
              "Related projects",
              project.related_projects,
              (p) => `<li>${escapeHtml(p)}</li>`,
              "No related projects linked yet."
            )}
          </div>
        </div>
      `;
    } catch (err) {
      const message = err.status === 404 ? "Project not found." : `Could not load project: ${err.message}`;
      piEls.detailBody.innerHTML = `<p class="error-box">${escapeHtml(message)}</p>`;
    }
  }

  piEls.backBtn.addEventListener("click", () => {
    piEls.detailView.hidden = true;
    piEls.listView.hidden = false;
  });
})();

/* ROLE OS Dashboard — AI Advisor (Epic 2), plain JavaScript. */

(() => {
  "use strict";

  const els = {
    workspaceSelect: document.getElementById("advisor-workspace-select"),
    briefGreeting: document.getElementById("daily-brief-greeting"),
    recommendationList: document.getElementById("advisor-recommendation-list"),
  };

  if (!els.recommendationList) return; // template not present

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

  function priorityClass(score) {
    if (score >= 70) return "health-good";
    if (score >= 40) return "health-ok";
    return "health-bad";
  }

  let initialized = false;

  document.addEventListener("roleos:tabchange", (e) => {
    if (e.detail.tab === "advisor" && !initialized) {
      initialized = true;
      init();
    }
  });

  async function init() {
    await loadWorkspaces();
    await refresh();
    els.workspaceSelect.addEventListener("change", refresh);
  }

  async function loadWorkspaces() {
    try {
      const workspaces = await fetchJSON("/pi/workspaces");
      const options = workspaces.map((w) => `<option value="${escapeHtml(w.name)}">${escapeHtml(w.name)}</option>`).join("");
      els.workspaceSelect.innerHTML = `<option value="">All workspaces</option>${options}`;
    } catch (err) {
      console.error("Could not load workspaces", err);
    }
  }

  async function refresh() {
    await Promise.all([loadDailyBrief(), loadRecommendations()]);
  }

  function workspaceParam() {
    const value = els.workspaceSelect.value;
    return value ? `?workspace=${encodeURIComponent(value)}` : "";
  }

  async function loadDailyBrief() {
    els.briefGreeting.textContent = "Loading…";
    try {
      const brief = await fetchJSON(`/advisor/daily-brief${workspaceParam()}`);
      els.briefGreeting.textContent = brief.greeting;
    } catch (err) {
      els.briefGreeting.textContent = `Could not load daily brief: ${err.message}`;
    }
  }

  function recommendationCardHtml(rec) {
    const evidence = (rec.evidence || []).map((e) => `<li>${escapeHtml(e)}</li>`).join("");
    return `
      <li class="advisor-card" data-id="${escapeHtml(rec.id)}">
        <div class="advisor-card-header">
          <div>
            <div class="advisor-card-title">${escapeHtml(rec.title)}</div>
            <div class="advisor-card-meta">
              <span class="badge">${escapeHtml(rec.recommendation_type)}</span>
              <span class="badge">Effort: ${escapeHtml(rec.estimated_effort)}</span>
              <span class="priority-dot ${priorityClass(rec.priority_score)}">Priority ${rec.priority_score}</span>
              <span class="badge">Confidence ${rec.confidence_score}</span>
            </div>
          </div>
        </div>
        <div class="advisor-card-body">
          <p>${escapeHtml(rec.summary)}</p>
          <p><strong>Why:</strong> ${escapeHtml(rec.reason)}</p>
          <p><strong>Suggested action:</strong> ${escapeHtml(rec.suggested_action)}</p>
          <p><strong>Impact:</strong> ${escapeHtml(rec.impact)}</p>
          <ul class="advisor-evidence-list">${evidence}</ul>
        </div>
        <div class="advisor-card-actions">
          <button type="button" class="dismiss-btn">Dismiss</button>
          <button type="button" class="complete-btn">Mark completed</button>
        </div>
      </li>`;
  }

  async function loadRecommendations() {
    try {
      const recs = await fetchJSON(`/advisor/recommendations${workspaceParam()}`);
      if (!recs.length) {
        els.recommendationList.innerHTML = '<li class="muted">No recommendations right now — nothing needs attention.</li>';
        return;
      }
      els.recommendationList.innerHTML = recs.map(recommendationCardHtml).join("");
      els.recommendationList.querySelectorAll(".advisor-card").forEach((card) => {
        const id = card.dataset.id;
        card.querySelector(".dismiss-btn").addEventListener("click", () => act(id, "dismiss", card));
        card.querySelector(".complete-btn").addEventListener("click", () => act(id, "complete", card));
      });
    } catch (err) {
      els.recommendationList.innerHTML = `<li class="error-box">Could not load recommendations: ${escapeHtml(err.message)}</li>`;
    }
  }

  async function act(id, action, card) {
    try {
      await fetchJSON(`/advisor/recommendations/${encodeURIComponent(id)}/${action}`, { method: "POST" });
      card.classList.add(action === "dismiss" ? "dismissed" : "completed");
      card.remove();
      if (!els.recommendationList.children.length) {
        els.recommendationList.innerHTML = '<li class="muted">No recommendations right now — nothing needs attention.</li>';
      }
    } catch (err) {
      console.error(`Could not ${action} recommendation`, err);
    }
  }
})();

// ---------------------------------------------------------------------------
// Knowledge Graph tab (Epic 3)
//
// Hand-rolled SVG rendering with zero external dependencies -- deliberately
// not using a CDN graph library so the dashboard keeps working fully offline
// and "no frontend framework" stays trivially true. This is presentation
// only: every piece of data it shows comes from the standalone /graph/* API,
// which works completely independently of this file (see
// dashboard/app/graph/engine.py and queries.py).
// ---------------------------------------------------------------------------
(function () {
  const svg = document.getElementById("graph-canvas");
  if (!svg) return; // template not present (shouldn't happen)

  const els = {
    svg,
    wrap: document.getElementById("graph-canvas-wrap"),
    emptyMsg: document.getElementById("graph-empty-msg"),
    detailPanel: document.getElementById("graph-detail-panel"),
    searchInput: document.getElementById("graph-search-input"),
    nodeTypeSelect: document.getElementById("graph-node-type-select"),
    workspaceSelect: document.getElementById("graph-workspace-select"),
    relationshipSelect: document.getElementById("graph-relationship-select"),
    highlightDepsBtn: document.getElementById("graph-highlight-dependencies"),
    highlightCapsBtn: document.getElementById("graph-highlight-capabilities"),
    resetBtn: document.getElementById("graph-reset-btn"),
    pathStatus: document.getElementById("graph-path-status"),
  };

  const NS = "http://www.w3.org/2000/svg";
  const WIDTH = 900;
  const HEIGHT = 560;

  // Rendered subgraph state -- a subset of the full graph, built up via the
  // initial load plus any "expand neighbors" actions. Kept entirely
  // client-side; every mutation re-fetches from the read-only /graph/* API.
  let renderNodes = new Map(); // id -> { node, x, y, expandedFrom: id|null }
  let renderEdges = []; // { source, target, type }
  let pathSource = null;
  let pathTarget = null;
  let highlightMode = null; // null | "dependencies" | "capabilities" | "path"
  let highlightPathEdgeKeys = new Set();

  async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const body = await resp.json();
        detail = body.detail || detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail);
    }
    return resp.json();
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  function edgeKey(edge) {
    return `${edge.source}|${edge.target}|${edge.type}`;
  }

  // ---- Layout: simple deterministic circle-by-type layout ----------------
  // No physics simulation -- positions are computed once per render from
  // node order, which keeps the view stable and the code simple to test.

  function layout() {
    const ids = Array.from(renderNodes.keys());
    const n = ids.length || 1;
    const cx = WIDTH / 2;
    const cy = HEIGHT / 2;
    const radius = Math.min(WIDTH, HEIGHT) / 2 - 60;
    ids.forEach((id, i) => {
      const angle = (2 * Math.PI * i) / n;
      const entry = renderNodes.get(id);
      entry.x = cx + radius * Math.cos(angle);
      entry.y = cy + radius * Math.sin(angle);
    });
  }

  const NODE_COLORS = {
    Project: "#4f7cff",
    KnowledgeCard: "#8a6dff",
    Person: "#ff8a4f",
    Application: "#22b8a0",
    Vendor: "#c74fff",
    Capability: "#ffb84f",
    Workspace: "#9aa5b1",
    Decision: "#4fd1ff",
    Deliverable: "#4fff8a",
    Prompt: "#ff4f9e",
    Asset: "#d1d64f",
    Conversation: "#6d8aff",
  };

  function render() {
    svg.setAttribute("viewBox", `0 0 ${WIDTH} ${HEIGHT}`);
    svg.innerHTML = "";
    els.emptyMsg.hidden = renderNodes.size > 0;
    if (!renderNodes.size) return;

    layout();

    // Edges first so nodes draw on top.
    renderEdges.forEach((edge) => {
      const a = renderNodes.get(edge.source);
      const b = renderNodes.get(edge.target);
      if (!a || !b) return;
      const line = document.createElementNS(NS, "line");
      line.setAttribute("x1", a.x);
      line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x);
      line.setAttribute("y2", b.y);
      let cls = "graph-edge";
      if (highlightMode === "path" && highlightPathEdgeKeys.has(edgeKey(edge))) {
        cls += " graph-edge-highlight-path";
      } else if (highlightMode === "dependencies" && (edge.type === "DEPENDS_ON" || edge.type === "UNBLOCKS")) {
        cls += " graph-edge-highlight-deps";
      } else if (
        highlightMode === "capabilities" &&
        (edge.type === "IMPLEMENTS" || edge.type === "USES" || edge.type === "SHARES_CAPABILITY")
      ) {
        cls += " graph-edge-highlight-caps";
      }
      line.setAttribute("class", cls);
      line.dataset.type = edge.type;
      svg.appendChild(line);
    });

    renderNodes.forEach((entry, id) => {
      const g = document.createElementNS(NS, "g");
      g.setAttribute("class", "graph-node");
      g.setAttribute("transform", `translate(${entry.x}, ${entry.y})`);
      g.dataset.id = id;

      const circle = document.createElementNS(NS, "circle");
      circle.setAttribute("r", id === pathSource || id === pathTarget ? 12 : 9);
      circle.setAttribute("fill", NODE_COLORS[entry.node.type] || "#999");
      if (id === pathSource || id === pathTarget) {
        circle.setAttribute("stroke", "#fff");
        circle.setAttribute("stroke-width", "2");
      }
      g.appendChild(circle);

      const text = document.createElementNS(NS, "text");
      text.setAttribute("x", 12);
      text.setAttribute("y", 4);
      text.setAttribute("class", "graph-node-label");
      text.textContent = entry.node.label;
      g.appendChild(text);

      g.addEventListener("click", () => selectNode(id));
      svg.appendChild(g);
    });
  }

  function setNodes(nodes, edges) {
    renderNodes = new Map(nodes.map((n) => [n.id, { node: n, x: 0, y: 0 }]));
    renderEdges = edges.map((e) => ({ source: e.source, target: e.target, type: e.type }));
    render();
  }

  function addNodes(nodes, edges) {
    nodes.forEach((n) => {
      if (!renderNodes.has(n.id)) renderNodes.set(n.id, { node: n, x: 0, y: 0 });
    });
    const existing = new Set(renderEdges.map(edgeKey));
    edges.forEach((e) => {
      const key = edgeKey(e);
      if (!existing.has(key)) {
        existing.add(key);
        renderEdges.push({ source: e.source, target: e.target, type: e.type });
      }
    });
    render();
  }

  // ---- Detail panel --------------------------------------------------------

  async function selectNode(id) {
    try {
      const data = await fetchJSON(`/graph/node/${encodeURIComponent(id)}`);
      renderDetailPanel(data.node, data.edges, id);
    } catch (err) {
      els.detailPanel.innerHTML = `<p class="error-box">Could not load node: ${escapeHtml(err.message)}</p>`;
    }
  }

  function renderDetailPanel(node, edges, id) {
    const dataRows = Object.entries(node.data || {})
      .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(JSON.stringify(v))}</td></tr>`)
      .join("");
    const edgeRows = edges
      .map((e) => {
        const otherId = e.source === id ? e.target : e.source;
        const otherNode = renderNodes.get(otherId);
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
        <button type="button" id="graph-expand-btn">Expand neighbors</button>
        <button type="button" id="graph-collapse-btn">Collapse to selection</button>
        <button type="button" id="graph-set-source-btn">Set as path source</button>
        <button type="button" id="graph-set-target-btn">Set as path target</button>
      </div>
    `;

    document.getElementById("graph-expand-btn").addEventListener("click", () => expandNode(id));
    document.getElementById("graph-collapse-btn").addEventListener("click", () => collapseToNode(id));
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
  }

  async function expandNode(id) {
    try {
      const entries = await fetchJSON(`/graph/neighbors/${encodeURIComponent(id)}?depth=1`);
      const nodes = entries.map((e) => e.node);
      const edges = entries.map((e) => e.edge);
      addNodes(nodes, edges);
    } catch (err) {
      console.error("Could not expand node", err);
    }
  }

  function collapseToNode(id) {
    const keep = new Set([id]);
    renderEdges.forEach((e) => {
      if (e.source === id) keep.add(e.target);
      if (e.target === id) keep.add(e.source);
    });
    renderNodes.forEach((_v, nodeId) => {
      if (!keep.has(nodeId)) renderNodes.delete(nodeId);
    });
    renderEdges = renderEdges.filter((e) => keep.has(e.source) && keep.has(e.target));
    render();
  }

  function updatePathStatus() {
    const sourceLabel = pathSource && renderNodes.get(pathSource) ? renderNodes.get(pathSource).node.label : "(none)";
    const targetLabel = pathTarget && renderNodes.get(pathTarget) ? renderNodes.get(pathTarget).node.label : "(none)";
    els.pathStatus.textContent = `Source: ${sourceLabel} — Target: ${targetLabel}`;
  }

  async function maybeComputePath() {
    if (!pathSource || !pathTarget) return;
    try {
      const result = await fetchJSON(
        `/graph/path?source=${encodeURIComponent(pathSource)}&target=${encodeURIComponent(pathTarget)}`
      );
      if (!result.found) {
        els.pathStatus.textContent += " — no path found within range.";
        return;
      }
      addNodes(result.nodes, result.edges);
      highlightMode = "path";
      highlightPathEdgeKeys = new Set(result.edges.map(edgeKey));
      els.pathStatus.textContent += ` — path length ${result.edges.length} hop(s), highlighted.`;
      render();
    } catch (err) {
      console.error("Could not compute path", err);
    }
  }

  // ---- Filters + search ----------------------------------------------------

  async function loadMetaTypes() {
    try {
      const meta = await fetchJSON("/graph/meta/types");
      els.nodeTypeSelect.innerHTML =
        '<option value="">All node types</option>' +
        meta.node_types.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
      els.relationshipSelect.innerHTML =
        '<option value="">All relationships</option>' +
        meta.relationship_types.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
    } catch (err) {
      console.error("Could not load graph meta types", err);
    }
  }

  async function loadWorkspaceOptions() {
    try {
      const workspaceNodes = await fetchJSON("/graph?node_type=Workspace");
      els.workspaceSelect.innerHTML =
        '<option value="">All workspaces</option>' +
        workspaceNodes.nodes.map((n) => `<option value="${escapeHtml(n.label)}">${escapeHtml(n.label)}</option>`).join("");
    } catch (err) {
      console.error("Could not load workspace options", err);
    }
  }

  async function loadFilteredView() {
    const params = new URLSearchParams();
    if (els.nodeTypeSelect.value) params.set("node_type", els.nodeTypeSelect.value);
    if (els.workspaceSelect.value) params.set("workspace", els.workspaceSelect.value);
    try {
      const data = await fetchJSON(`/graph?${params.toString()}`);
      let edges = data.edges;
      if (els.relationshipSelect.value) {
        edges = edges.filter((e) => e.type === els.relationshipSelect.value);
      }
      setNodes(data.nodes, edges);
    } catch (err) {
      els.detailPanel.innerHTML = `<p class="error-box">Could not load graph: ${escapeHtml(err.message)}</p>`;
    }
  }

  let searchDebounce = null;
  function onSearchInput() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(async () => {
      const q = els.searchInput.value.trim();
      if (!q) return;
      try {
        const results = await fetchJSON(`/graph/search?q=${encodeURIComponent(q)}`);
        els.detailPanel.innerHTML =
          "<h3>Search results</h3><ul class=\"graph-detail-edges\">" +
          results
            .map((n) => `<li><a href="#" data-id="${escapeHtml(n.id)}">${escapeHtml(n.label)} <span class="badge">${escapeHtml(n.type)}</span></a></li>`)
            .join("") +
          "</ul>";
        els.detailPanel.querySelectorAll("a[data-id]").forEach((a) => {
          a.addEventListener("click", async (ev) => {
            ev.preventDefault();
            const id = a.dataset.id;
            const entries = await fetchJSON(`/graph/neighbors/${encodeURIComponent(id)}?depth=1`);
            addNodes([...entries.map((e2) => e2.node)], entries.map((e2) => e2.edge));
            if (!renderNodes.has(id)) {
              const single = await fetchJSON(`/graph/node/${encodeURIComponent(id)}`);
              addNodes([single.node], []);
            }
            selectNode(id);
          });
        });
      } catch (err) {
        console.error("Graph search failed", err);
      }
    }, 250);
  }

  function resetView() {
    pathSource = null;
    pathTarget = null;
    highlightMode = null;
    highlightPathEdgeKeys = new Set();
    els.pathStatus.textContent =
      "Pick a source and target node (via the detail panel) to highlight the shortest path between them.";
    els.detailPanel.innerHTML =
      '<p class="muted">Click a node to see its details, expand its neighbors, or use it as a path endpoint.</p>';
    els.nodeTypeSelect.value = "";
    els.workspaceSelect.value = "";
    els.relationshipSelect.value = "";
    loadFilteredView();
  }

  let initialized = false;

  document.addEventListener("roleos:tabchange", (e) => {
    if (e.detail.tab === "graph" && !initialized) {
      initialized = true;
      init();
    }
  });

  async function init() {
    await loadMetaTypes();
    await loadWorkspaceOptions();
    await loadFilteredView();
    els.nodeTypeSelect.addEventListener("change", loadFilteredView);
    els.workspaceSelect.addEventListener("change", loadFilteredView);
    els.relationshipSelect.addEventListener("change", loadFilteredView);
    els.searchInput.addEventListener("input", onSearchInput);
    els.resetBtn.addEventListener("click", resetView);
    els.highlightDepsBtn.addEventListener("click", () => {
      highlightMode = highlightMode === "dependencies" ? null : "dependencies";
      render();
    });
    els.highlightCapsBtn.addEventListener("click", () => {
      highlightMode = highlightMode === "capabilities" ? null : "capabilities";
      render();
    });
  }
})();
