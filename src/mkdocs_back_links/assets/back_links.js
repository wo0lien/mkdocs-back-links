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

  function readSettings() {
    const tag = document.getElementById("mbl-settings");
    if (!tag) return { max_nodes: 500, default_view: "local" };
    try { return JSON.parse(tag.textContent); }
    catch (_e) { return { max_nodes: 500, default_view: "local" }; }
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

  function renderGraph(svgEl, data) {
    const d3 = window.d3;
    if (!d3) return;
    const width = svgEl.clientWidth || 200;
    const height = svgEl.clientHeight || 200;

    // 1. Set up svg and root
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const root = svg.append("g").attr("class", "mbl-graph-root");

    // 2. Set up zoom on svg
    const zoom = d3
      .zoom()
      .scaleExtent([0.25, 4])
      .on("zoom", (event) => {
        root.attr("transform", event.transform);
      });
    svg.call(zoom).on("dblclick.zoom", null);

    // 3. Create nodes/edges data, link selection, node selection
    const nodes = data.nodes.map((n) => Object.assign({}, n));
    const edges = data.edges.map((e) => Object.assign({}, e));
    const currentId = data.current;

    const link = root
      .append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("class", "mbl-graph-link")
      .attr("stroke-width", 1);

    const node = root
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("class", (d) => "mbl-graph-node" + (d.id === currentId ? " mbl-graph-node--current" : ""))
      .attr("r", (d) => (d.id === currentId ? 6 : 4))
      .on("click", (_event, d) => {
        if (d.url) window.location.href = d.url;
      });

    node.append("title").text((d) => d.title);

    // 4. Create simulation
    const sim = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d) => d.id).distance(40).strength(0.6))
      .force("charge", d3.forceManyBody().strength(-80))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(8));

    // 5. Set up drag (references sim)
    const drag = d3
      .drag()
      .on("start", (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        // pinned: leave fx/fy set so it stays put
      });

    // 6. Attach drag and dblclick to node
    node.call(drag).on("dblclick", (_event, d) => {
      d.fx = null;
      d.fy = null;
      sim.alpha(0.3).restart();
    });

    // 7. Set sim tick handler
    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });

    // 8. Freeze check: if node count exceeds max_nodes, run fixed ticks and stop
    const settings = readSettings();
    if (nodes.length > settings.max_nodes) {
      // run a fixed number of ticks then stop
      sim.stop();
      for (let i = 0; i < 200; i++) sim.tick();
      // manually paint final positions
      link
        .attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    }

    return { svgRoot: root, simulation: sim };
  }

  function openModal(currentData) {
    const overlay = document.createElement("div");
    overlay.className = "mbl-graph-modal";
    overlay.innerHTML = `
      <div class="mbl-graph-modal__inner">
        <div class="mbl-graph-header">
          <h3>Graph</h3>
          <button type="button" class="mbl-graph-expand" aria-label="Close">×</button>
        </div>
        <svg class="mbl-graph-svg" xmlns="http://www.w3.org/2000/svg"></svg>
      </div>`;
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    overlay.querySelector(".mbl-graph-expand").addEventListener("click", close);
    document.addEventListener(
      "keydown",
      function onKey(e) {
        if (e.key === "Escape") {
          close();
          document.removeEventListener("keydown", onKey);
        }
      }
    );
    requestAnimationFrame(() => renderGraph(overlay.querySelector(".mbl-graph-svg"), currentData));
  }

  function init() {
    const target = findSidebarTarget();
    if (!target) return;
    const data = readLocalGraph();
    if (!data) return;

    const pane = buildPaneElement();
    target.appendChild(pane);
    window.__mblPane = pane;
    window.__mblLocal = data;

    const svg = pane.querySelector(".mbl-graph-svg");
    let globalCache = null;
    let currentRender = null;
    let activeData = data;

    const settings = readSettings();
    if (settings.default_view === "global") {
      // simulate clicking the Global pill once the pane is ready
      requestAnimationFrame(() => {
        const globalBtn = pane.querySelector('.mbl-graph-toggle button[data-view="global"]');
        if (globalBtn) globalBtn.click();
      });
    } else {
      requestAnimationFrame(() => { currentRender = renderGraph(svg, data); });
    }

    pane.querySelectorAll(".mbl-graph-toggle button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const view = btn.dataset.view;
        pane.querySelectorAll(".mbl-graph-toggle button").forEach((b) => {
          b.setAttribute("aria-pressed", String(b === btn));
        });
        if (view === "local") {
          if (currentRender) currentRender.simulation.stop();
          currentRender = renderGraph(svg, data);
          activeData = data;
          return;
        }
        // global
        if (!globalCache) {
          try {
            const res = await fetch("/assets/back_links/graph.json");
            globalCache = await res.json();
            globalCache.current = data.current;
          } catch (_e) {
            return;
          }
        }
        if (currentRender) currentRender.simulation.stop();
        currentRender = renderGraph(svg, globalCache);
        activeData = globalCache;
      });
    });

    pane.querySelector(".mbl-graph-expand").addEventListener("click", () => {
      openModal(activeData);
    });

    document.dispatchEvent(new CustomEvent("mbl:pane-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
