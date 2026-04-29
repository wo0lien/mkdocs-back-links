/* mkdocs-back-links — graph pane bootstrap. */
(function () {
  "use strict";

  function readLocalGraph() {
    const tag = document.getElementById("mbl-local-graph");
    if (!tag) return null;
    try {
      return JSON.parse(tag.textContent);
    } catch (_e) {
      return null;
    }
  }

  function buildPaneElement() {
    const pane = document.createElement("aside");
    pane.className = "mbl-graph-pane";
    pane.innerHTML = `
      <div class="mbl-graph-header">
        <h3>Graph</h3>
        <div class="mbl-graph-toggle" role="group" aria-label="Graph view">
          <button type="button" data-view="local" aria-pressed="true">Local</button>
          <button type="button" data-view="global" aria-pressed="false">Global</button>
        </div>
        <button type="button" class="mbl-graph-expand" title="Expand" aria-label="Expand graph">⤢</button>
      </div>
      <svg class="mbl-graph-svg" xmlns="http://www.w3.org/2000/svg"></svg>
    `;
    return pane;
  }

  function findSidebarTarget() {
    return (
      document.querySelector(".md-sidebar--secondary .md-sidebar__scrollwrap") ||
      document.querySelector(".md-sidebar--secondary")
    );
  }

  function init() {
    const target = findSidebarTarget();
    if (!target) return;
    const data = readLocalGraph();
    if (!data) return;

    const pane = buildPaneElement();
    target.appendChild(pane);

    // Expose for the rendering layer to pick up.
    window.__mblPane = pane;
    window.__mblLocal = data;
    document.dispatchEvent(new CustomEvent("mbl:pane-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
