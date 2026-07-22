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
