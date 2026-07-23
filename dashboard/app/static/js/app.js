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
