/* mkdocs-back-links — graph pane bootstrap. */
(function () {
  "use strict";

  const EXPAND_ICON_SVG =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
    '<path fill="currentColor" d="M9.5,13.09L10.91,14.5L6.41,19H10V21H3V14H5V17.59L9.5,13.09M10.91,9.5L9.5,10.91L5,6.41V10H3V3H10V5H6.41L10.91,9.5M14.5,13.09L19,17.59V14H21V21H14V19H17.59L13.09,14.5L14.5,13.09M13.09,9.5L17.59,5H14V3H21V10H19V6.41L14.5,10.91L13.09,9.5Z"/>' +
    '</svg>';

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
    if (!tag) return { max_nodes: 500 };
    try { return JSON.parse(tag.textContent); }
    catch (_e) { return { max_nodes: 500 }; }
  }

  function buildPaneElement() {
    const pane = document.createElement("aside");
    pane.className = "mbl-graph-pane";
    pane.innerHTML =
      '<div class="mbl-graph-header">' +
        '<h3>Graph</h3>' +
        '<button type="button" class="mbl-graph-expand" title="Expand graph" aria-label="Expand graph">' +
          EXPAND_ICON_SVG +
        '</button>' +
      '</div>' +
      '<svg class="mbl-graph-svg" xmlns="http://www.w3.org/2000/svg"></svg>';
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

    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const root = svg.append("g").attr("class", "mbl-graph-root");

    const zoom = d3
      .zoom()
      .scaleExtent([0.25, 4])
      .on("zoom", (event) => {
        root.attr("transform", event.transform);
      });
    svg.call(zoom).on("dblclick.zoom", null);

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

    const label = root
      .append("g")
      .attr("class", "mbl-graph-labels")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("class", (d) => "mbl-graph-label" + (d.id === currentId ? " mbl-graph-label--current" : ""))
      .attr("dx", (d) => (d.id === currentId ? 9 : 7))
      .attr("dy", "0.35em")
      .text((d) => d.title);

    const sim = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d) => d.id).distance(60).strength(0.6))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(10));

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
      });

    node.call(drag).on("dblclick", (_event, d) => {
      d.fx = null;
      d.fy = null;
      sim.alpha(0.3).restart();
    });

    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });

    const settings = readSettings();
    if (nodes.length > settings.max_nodes) {
      sim.stop();
      for (let i = 0; i < 200; i++) sim.tick();
      link
        .attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    }

    return { svgRoot: root, simulation: sim };
  }

  function openModal(globalData) {
    const overlay = document.createElement("div");
    overlay.className = "mbl-graph-modal";
    overlay.innerHTML =
      '<div class="mbl-graph-modal__inner">' +
        '<div class="mbl-graph-header">' +
          '<h3>Graph</h3>' +
          '<button type="button" class="mbl-graph-close" aria-label="Close">×</button>' +
        '</div>' +
        '<svg class="mbl-graph-svg" xmlns="http://www.w3.org/2000/svg"></svg>' +
      '</div>';
    document.body.appendChild(overlay);
    const close = () => overlay.remove();
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    overlay.querySelector(".mbl-graph-close").addEventListener("click", close);
    document.addEventListener(
      "keydown",
      function onKey(e) {
        if (e.key === "Escape") {
          close();
          document.removeEventListener("keydown", onKey);
        }
      }
    );
    requestAnimationFrame(() => renderGraph(overlay.querySelector(".mbl-graph-svg"), globalData));
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
    requestAnimationFrame(() => renderGraph(svg, data));

    let globalCache = null;
    pane.querySelector(".mbl-graph-expand").addEventListener("click", async () => {
      if (!globalCache) {
        try {
          const res = await fetch("/assets/back_links/graph.json");
          globalCache = await res.json();
          globalCache.current = data.current;
        } catch (_e) {
          return;
        }
      }
      openModal(globalCache);
    });

    document.dispatchEvent(new CustomEvent("mbl:pane-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
