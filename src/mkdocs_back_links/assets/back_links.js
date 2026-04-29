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

  function renderGraph(svgEl, data) {
    const d3 = window.d3;
    if (!d3) return;
    const width = svgEl.clientWidth || 200;
    const height = svgEl.clientHeight || 200;

    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const root = svg.append("g").attr("class", "mbl-graph-root");

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

    const sim = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink(edges).id((d) => d.id).distance(40).strength(0.6))
      .force("charge", d3.forceManyBody().strength(-80))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(8));

    sim.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
    });

    return { svgRoot: root, simulation: sim };
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
    // Defer one tick so the SVG has dimensions
    requestAnimationFrame(() => renderGraph(svg, data));
    document.dispatchEvent(new CustomEvent("mbl:pane-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
