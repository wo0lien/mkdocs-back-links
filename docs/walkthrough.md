# Walkthrough

A long-form tour of how the plugin works end to end. Use this page to test
scroll-spy: the section currently in view should highlight in the graph pane.

## Why a graph view

Documentation is a network. A page rarely stands alone — it cites guides,
references concepts, and is itself referenced by overview pages. Linear
navigation hides this structure. A graph view makes it visible at a glance,
which helps readers discover related material that a sidebar would never
surface.

The graph in this plugin is intentionally local-first. The small pane in the
secondary sidebar always shows the neighborhood of the page you are reading,
so it stays relevant while you scroll. The expand button reveals the global
graph when you want to zoom out.

## Building the index

At build time the plugin walks every Markdown page and records the inbound
edges. An edge is a tuple of `(source_page, source_section, target_page,
target_section)`. Sections are tracked alongside pages so that a link to
`other.md#anchor` is not collapsed to a page-level edge — the anchor matters.

The walker is single-pass and cheap. On a 500-page corpus the scan typically
finishes in under a second. The result is a flat list of edges, which is the
input to every downstream computation: backlinks, the local subgraph, and
the global graph file.

## Section discovery

Headings are discovered by parsing the rendered HTML of each page just before
MkDocs writes it to disk. The plugin reads the `id` attribute of each `h2` and
`h3` element (configurable via `section_levels`) and records the slug.

A heading becomes a graph node only if some other page links to it. Lonely
headings are noise — they would clutter the visualization without adding
information — so they are filtered out by default. The
`section_nodes_same_page` option flips this for pages whose own internal
table of contents links to the heading.

## Local subgraph

For each page the plugin computes a one-hop neighborhood: the page itself,
plus every page that either links to it or is linked from it. Section nodes
are then layered on top — for every page in the neighborhood, every eligible
section is added as a node with a `contains` edge from its parent page.

This is what you see in the small sidebar pane. The graph stays manageable
even on highly-cross-referenced sites because the neighborhood does not
expand transitively. If you want to follow the network further, you can
click any node to navigate, which gives you that node's neighborhood next.

## Rendering with D3

The graph itself is rendered with D3's force-directed layout. Each node is a
circle and each edge is a line. The simulation balances three forces:
many-body repulsion that spreads nodes out, a link force that pulls connected
nodes together, and a centering force that keeps everything within view.

Force parameters are tuned to the container size. The sidebar pane uses
short, tightly-coupled links because it is small. The expanded modal uses
longer links and stronger repulsion to take advantage of the available
space. A centering pull keeps disconnected nodes from drifting off-canvas.

## Scroll-spy behavior

When the local graph contains section nodes for the current page, the
plugin sets up an `IntersectionObserver` that watches the actual headings in
the body. As you scroll, the section that is most prominently in view gets
a highlighted ring in the graph. This gives a continuous "you are here"
indicator without requiring a click.

Scroll-spy degrades gracefully: if the browser does not support
`IntersectionObserver`, the feature is simply skipped. The graph still works,
just without the live indicator.

## Backlinks block

At the bottom of every page the plugin renders a `Backlinks` section listing
the pages that link to this one. It is plain HTML with classes scoped under
Material's `.md-typeset`, so it inherits typography from the theme without
fighting it.

When a section on the page is linked from elsewhere, an inline aside is
inserted right before the next heading boundary, listing only the backlinks
for that specific section. This keeps the context tight: while you are
reading section X, you can see who points to X without scrolling to the
bottom of the page.

## Performance considerations

Most of the work happens once at build time. At runtime the only computation
is the D3 force simulation, which runs for a fixed warmup of 150–300 ticks
synchronously before paint, then optionally continues animating at low
energy. Pages with very large neighborhoods skip the post-paint animation to
keep the main thread quiet.

The global graph file is fetched lazily when you open the modal. It is a
single JSON document keyed by node id, gzipped by the server, and cached for
the duration of the session. On most sites it is under 50 KB compressed.

## Configuration surface

The plugin tries to expose only options that meaningfully change behavior.
You can disable either feature, change the heading level set, exclude pages,
adjust the centering pull, hide the pane on orphan pages, and cap the node
count above which the simulation freezes after warmup. That is the entire
surface — there are no theme knobs, no font overrides, no layout switches.

If you need something more, the rendered DOM uses semantic classes so a few
lines of custom CSS in your `extra.css` will usually do the trick.

## Beyond this page

That is the full pipeline: parse markdown, build edges, derive subgraphs,
render with D3, light up scroll-spy. Every other feature in this plugin is
a refinement of one of those steps. Read the
[architecture overview](concepts/architecture.md#components) for a higher
level picture, or the [internals](concepts/internals.md#parsing) for the
gory details of the parser.
