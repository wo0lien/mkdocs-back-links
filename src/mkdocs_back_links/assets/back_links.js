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

  const SETTINGS_DEFAULTS = { max_nodes: 500, center_strength: 0.08, section_cluster_threshold: 2 };

  function readSettings() {
    const tag = document.getElementById("mbl-settings");
    if (!tag) return { ...SETTINGS_DEFAULTS };
    try { return { ...SETTINGS_DEFAULTS, ...JSON.parse(tag.textContent) }; }
    catch (_e) { return { ...SETTINGS_DEFAULTS }; }
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

  function cssEscape(s) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, (c) => "\\" + c);
  }

  function setupScrollSpy(pane, localData, onReveal) {
    const sectionNodes = localData.nodes.filter(
      (n) => n.type === "section" && n.page === localData.current
    );
    if (sectionNodes.length === 0) return;

    // Mirror Material's own TOC scroll-spy: it tags the active TOC entry with
    // `md-nav__link--active`. Watching that single source keeps the graph
    // indicator perfectly in sync with the highlighted TOC item.
    const toc = document.querySelector('[data-md-component="toc"]');
    if (!toc) return;

    const slugToSectionId = new Map();
    for (const sn of sectionNodes) {
      const slug = sn.id.split("#", 2)[1];
      if (slug) slugToSectionId.set(slug, sn.id);
    }

    let activeId = localData.current;

    const apply = (newId) => {
      if (newId === activeId) return;
      pane
        .querySelectorAll(".mbl-graph-node--scrolled, .mbl-graph-label--scrolled, .mbl-graph-link--scrolled")
        .forEach((n) =>
          n.classList.remove(
            "mbl-graph-node--scrolled",
            "mbl-graph-label--scrolled",
            "mbl-graph-link--scrolled"
          )
        );
      const els = pane.querySelectorAll(`[data-graph-id="${cssEscape(newId)}"]`);
      els.forEach((el) => {
        if (el.tagName === "circle") el.classList.add("mbl-graph-node--scrolled");
        if (el.tagName === "text") el.classList.add("mbl-graph-label--scrolled");
      });
      pane
        .querySelectorAll(`line[data-graph-target="${cssEscape(newId)}"]`)
        .forEach((el) => el.classList.add("mbl-graph-link--scrolled"));
      activeId = newId;
      if (onReveal) onReveal(newId);
    };

    const detectActive = () => {
      // Multiple links may carry --active for nested headings; Material orders
      // them with the deepest last, so the last match is the most specific.
      const actives = toc.querySelectorAll(".md-nav__link--active");
      if (!actives.length) {
        apply(localData.current);
        return;
      }
      const href = actives[actives.length - 1].getAttribute("href") || "";
      const slug = href.split("#")[1] || "";
      apply(slugToSectionId.get(slug) || localData.current);
    };

    detectActive();
    const observer = new MutationObserver(detectActive);
    observer.observe(toc, {
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  function fitToView(svgEl, zoom, nodes, width, height) {
    const d3 = window.d3;
    if (!d3 || !nodes.length) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodes) {
      if (typeof n.x !== "number" || typeof n.y !== "number") continue;
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }
    if (!isFinite(minX)) return;
    const bboxW = Math.max(maxX - minX, 1);
    const bboxH = Math.max(maxY - minY, 1);
    const padding = nodes.length < 10 ? 60 : 40;
    const labelSpace = Math.min(width * 0.15, 100);
    const scale = Math.min(
      (width - padding * 2 - labelSpace) / bboxW,
      (height - padding * 2) / bboxH,
      2
    );
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const transformAt = (s) =>
      d3.zoomIdentity
        .translate((width - labelSpace) / 2 - cx * s, height / 2 - cy * s)
        .scale(s);

    // Intro zoom: small graphs start zoomed in (1.6x final) and ease out;
    // global graphs (modal) start zoomed out (0.4x final) and ease in.
    const inModal = width > 600;
    const startScale = scale * (inModal ? 0.4 : 1.6);

    const sel = d3.select(svgEl);
    sel.call(zoom.transform, transformAt(startScale));
    sel.transition()
      .duration(700)
      .ease(d3.easeCubicOut)
      .call(zoom.transform, transformAt(scale));
  }

  function renderGraph(svgEl, data) {
    const d3 = window.d3;
    if (!d3) return;
    const settings = readSettings();
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
    const currentId = data.current;

    // Build a set of section node ids that should cluster into their parent
    // page. A page's sections are clustered when its eligible-section count
    // exceeds settings.section_cluster_threshold. Clustered sections start
    // hidden via CSS; for the current page, scroll-spy reveals one at a time.
    const sectionsByPage = new Map();
    const sectionToPage = new Map();
    for (const n of nodes) {
      if (n.type !== "section") continue;
      if (!sectionsByPage.has(n.page)) sectionsByPage.set(n.page, []);
      sectionsByPage.get(n.page).push(n.id);
      sectionToPage.set(n.id, n.page);
    }
    const clusteredIds = new Set();
    for (const [, ids] of sectionsByPage) {
      if (ids.length > settings.section_cluster_threshold) {
        for (const id of ids) clusteredIds.add(id);
      }
    }

    // Edge handling for clustered sections:
    //  - Cross-edges to/from a clustered section are kept in their original
    //    section-level form but marked `--clustered` (hidden by CSS until
    //    scroll-spy reveals the section). This is what restores the section's
    //    direct connections when it pops out.
    //  - We also synthesize a redirected page-level copy so the graph stays
    //    visually connected while the section is hidden. Redirects dedupe
    //    against any naturally-existing page-level cross-edge.
    //  - `contains` edges are unchanged (page→section), marked clustered when
    //    their target is clustered.
    const seenEdges = new Set();
    const edges = [];
    const addEdge = (key, e) => {
      if (seenEdges.has(key)) return;
      seenEdges.add(key);
      edges.push(e);
    };
    for (const raw of data.edges) {
      if (raw.kind !== "cross") {
        addEdge(`${raw.source}|${raw.target}|${raw.kind}`, { ...raw });
        continue;
      }
      const srcClustered = clusteredIds.has(raw.source);
      const tgtClustered = clusteredIds.has(raw.target);
      if (!srcClustered && !tgtClustered) {
        addEdge(`${raw.source}|${raw.target}|cross`, { ...raw });
        continue;
      }
      // Original (clustered) cross-edge — hidden by default, revealed when
      // its clustered endpoint is the active scrolled-into-view section.
      const clusteredEndpoint = tgtClustered ? raw.target : raw.source;
      addEdge(`${raw.source}|${raw.target}|cross|orig`, {
        ...raw,
        _clusteredOriginal: true,
        _clusteredEndpoint: clusteredEndpoint,
      });
      // Redirected page-level shadow — visible whenever the section is hidden.
      const rsrc = srcClustered ? sectionToPage.get(raw.source) : raw.source;
      const rtgt = tgtClustered ? sectionToPage.get(raw.target) : raw.target;
      if (rsrc !== rtgt) {
        addEdge(`${rsrc}|${rtgt}|cross`, { source: rsrc, target: rtgt, kind: "cross" });
      }
    }

    const link = root
      .append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("class", (d) => {
        const cls = ["mbl-graph-link"];
        if (d.kind === "contains") cls.push("mbl-graph-link--contains");
        if (d.kind === "contains" && clusteredIds.has(d.target)) cls.push("mbl-graph-link--clustered");
        if (d._clusteredOriginal) cls.push("mbl-graph-link--clustered");
        return cls.join(" ");
      })
      .attr("data-graph-target", (d) => {
        if (d._clusteredOriginal) return d._clusteredEndpoint;
        if (d.kind === "contains") return d.target;
        return null;
      })
      .attr("stroke-width", 1);

    const edgeId = (e) => {
      const s = typeof e.source === "object" ? e.source.id : e.source;
      const t = typeof e.target === "object" ? e.target.id : e.target;
      return [s, t];
    };

    const focusNode = (focusId) => {
      const connected = new Set([focusId]);
      for (const e of edges) {
        const [s, t] = edgeId(e);
        if (s === focusId) connected.add(t);
        if (t === focusId) connected.add(s);
      }
      node.classed("mbl-graph-node--faded", (n) => !connected.has(n.id));
      label
        .classed("mbl-graph-label--faded", (n) => !connected.has(n.id))
        .classed("mbl-graph-label--hover", (n) => n.id === focusId);
      link
        .classed("mbl-graph-link--faded", (e) => {
          const [s, t] = edgeId(e);
          return s !== focusId && t !== focusId;
        })
        .classed("mbl-graph-link--active", (e) => {
          const [s, t] = edgeId(e);
          return s === focusId || t === focusId;
        });
    };

    const clearFocus = () => {
      node.classed("mbl-graph-node--faded", false);
      label
        .classed("mbl-graph-label--faded", false)
        .classed("mbl-graph-label--hover", false);
      link
        .classed("mbl-graph-link--faded", false)
        .classed("mbl-graph-link--active", false);
    };

    const node = root
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("class", (d) => {
        const cls = ["mbl-graph-node"];
        if (d.type === "section") cls.push("mbl-graph-node--section");
        if (d.id === currentId) cls.push("mbl-graph-node--current");
        if (clusteredIds.has(d.id)) cls.push("mbl-graph-node--clustered");
        return cls.join(" ");
      })
      .attr("r", (d) => {
        if (d.type === "section") return 5;
        return d.id === currentId ? 10 : 7;
      })
      .attr("data-graph-id", (d) => d.id)
      .on("click", (_event, d) => {
        if (d.url) window.location.href = d.url;
      })
      .on("mouseover", (_event, d) => focusNode(d.id))
      .on("mouseout", clearFocus);

    node.append("title").text((d) => d.title);

    const label = root
      .append("g")
      .attr("class", "mbl-graph-labels")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .attr("class", (d) => {
        const cls = ["mbl-graph-label"];
        if (d.id === currentId) cls.push("mbl-graph-label--current");
        if (clusteredIds.has(d.id)) cls.push("mbl-graph-label--clustered");
        return cls.join(" ");
      })
      .attr("dx", (d) => (d.id === currentId ? 14 : 11))
      .attr("dy", "0.35em")
      .attr("data-graph-id", (d) => d.id)
      .text((d) => d.title);

    // Scale forces with container size — the modal is much larger than the
    // sidebar pane and benefits from longer links and stronger repulsion.
    const inModal = width > 600;
    const linkDistance = inModal ? 140 : 60;
    const chargeStrength = inModal ? -500 : -120;
    const collideRadius = inModal ? 22 : 14;

    // Clustered sections are excluded from the simulation so they don't push
    // or pull other nodes. Their positions are pinned to a small halo around
    // their parent page each tick. When scroll-spy reveals one (revealedId),
    // it is dynamically added to the simulation so the layout rearranges.
    let revealedId = null;
    const idIsInSim = (id) => !clusteredIds.has(id) || id === revealedId;
    const computeSimSet = () => ({
      sNodes: nodes.filter((n) => idIsInSim(n.id)),
      sEdges: edges.filter((e) => {
        const s = typeof e.source === "object" ? e.source.id : e.source;
        const t = typeof e.target === "object" ? e.target.id : e.target;
        return idIsInSim(s) && idIsInSim(t);
      }),
    });
    let { sNodes: simNodes, sEdges: simEdges } = computeSimSet();

    const haloRadius = inModal ? 22 : 14;
    for (const [, ids] of sectionsByPage) {
      if (ids.length <= settings.section_cluster_threshold) continue;
      ids.forEach((id, i) => {
        const node = nodes.find((n) => n.id === id);
        if (!node) return;
        const angle = (2 * Math.PI * i) / ids.length;
        node._haloX = Math.cos(angle) * haloRadius;
        node._haloY = Math.sin(angle) * haloRadius;
      });
    }

    const nodesById = new Map(nodes.map((n) => [n.id, n]));

    const sim = d3
      .forceSimulation(simNodes)
      .force(
        "link",
        d3
          .forceLink(simEdges)
          .id((d) => d.id)
          .distance((e) => (e.kind === "contains" ? linkDistance * 0.35 : linkDistance))
          .strength((e) => (e.kind === "contains" ? 0.9 : 0.6))
      )
      .force("charge", d3.forceManyBody().strength(chargeStrength))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(settings.center_strength))
      .force("y", d3.forceY(height / 2).strength(settings.center_strength))
      .force("collide", d3.forceCollide(collideRadius));

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

    const placeClusteredNodes = () => {
      for (const n of nodes) {
        if (!clusteredIds.has(n.id)) continue;
        if (n.id === revealedId) continue; // simulation owns the revealed one
        const p = nodesById.get(n.page);
        if (p && typeof p.x === "number") {
          n.x = p.x + (n._haloX || 0);
          n.y = p.y + (n._haloY || 0);
        }
      }
    };
    const refX = (ref) => (typeof ref === "object" ? ref.x : nodesById.get(ref)?.x || 0);
    const refY = (ref) => (typeof ref === "object" ? ref.y : nodesById.get(ref)?.y || 0);
    const paint = () => {
      placeClusteredNodes();
      link
        .attr("x1", (d) => refX(d.source))
        .attr("y1", (d) => refY(d.source))
        .attr("x2", (d) => refX(d.target))
        .attr("y2", (d) => refY(d.target));
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    };
    sim.on("tick", paint);

    // Warm up the simulation synchronously so we can fit the viewport before
    // the user sees the graph, then optionally let it continue animating.
    const isFrozen = nodes.length > settings.max_nodes;
    sim.stop();
    const warmupTicks = isFrozen ? 300 : 150;
    for (let i = 0; i < warmupTicks; i++) sim.tick();
    paint();
    fitToView(svgEl, zoom, nodes, width, height);
    if (!isFrozen) {
      sim.alpha(0.1).restart();
    }

    const setRevealed = (id) => {
      const next = id && clusteredIds.has(id) ? id : null;
      if (next === revealedId) return;
      revealedId = next;
      // Seed the entering node at its current pinned (halo) position so the
      // restarted simulation animates it from there into its new resting spot.
      const fresh = computeSimSet();
      sim.nodes(fresh.sNodes);
      sim.force("link").links(fresh.sEdges);
      sim.alpha(0.5).restart();
    };

    return { svgRoot: root, simulation: sim, setRevealed };
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

    let closed = false;
    const close = () => {
      if (closed) return;
      closed = true;
      overlay.classList.remove("mbl-graph-modal--open");
      overlay.classList.add("mbl-graph-modal--closing");
      setTimeout(() => overlay.remove(), 260);
    };

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

    // Trigger CSS transition on the next frame so the initial state renders first.
    requestAnimationFrame(() => {
      overlay.classList.add("mbl-graph-modal--open");
      renderGraph(overlay.querySelector(".mbl-graph-svg"), globalData);
    });
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

    const hasLocalNodes = Array.isArray(data.nodes) && data.nodes.length > 0;
    if (hasLocalNodes) {
      const svg = pane.querySelector(".mbl-graph-svg");
      requestAnimationFrame(() => {
        const rendered = renderGraph(svg, data);
        setupScrollSpy(pane, data, rendered && rendered.setRevealed);
      });
    } else {
      pane.classList.add("mbl-graph-pane--header-only");
      const svg = pane.querySelector(".mbl-graph-svg");
      if (svg) svg.remove();
    }

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
