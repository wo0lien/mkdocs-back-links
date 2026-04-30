# mkdocs-back-links

Backlinks at the bottom of every page and a sticky force-directed graph view in
the right sidebar, for [Material for MkDocs][material].

## Install

From git (until a PyPI release is published):

```bash
pip install git+https://github.com/wo0lien/mkdocs-back-links.git@v0.2.0
```

Then add the plugin to `mkdocs.yml`:

```yaml
plugins:
  - back-links
```

## Configuration

```yaml
plugins:
  - back-links:
      backlinks:
        enabled: true
        heading: "Backlinks"
        section_collapse_threshold: 3   # collapse section blocks when entries > this; 0 disables
      graph:
        enabled: true
        height: "40vh"
        max_nodes: 500
        section_levels: [2, 3]          # heading levels eligible for section treatment
        section_nodes_same_page: false  # if true, sections targeted only by same-page links also become graph nodes
        center_strength: 0.08           # gravity pulling nodes toward center; raise to bring orphans closer, lower to spread out
        section_cluster_threshold: 2    # cluster section nodes into their parent page when count exceeds this; current page reveals the scrolled-into-view section
        hide_when_orphan: true          # hide the small graph pane on pages with no incoming or outgoing links
        exclude:
          - "tags.md"
          - "404.md"
        colors:                         # any valid CSS color (hex, rgb, hsl, var(...))
          node: ""                      # page node fill (default: blue grey 800/100)
          section: ""                   # section node fill (default: blue grey 200/400)
          current_fill: ""              # current page node fill (default: var(--md-accent-fg-color))
          current_stroke: ""            # current page node stroke (default: var(--md-primary-fg-color))
          link: ""                      # link/edge stroke (default: var(--md-default-fg-color--lighter))
          highlight: ""                 # hover/active highlight (default: var(--md-accent-fg-color))
          label: ""                     # label text fill (default: var(--md-default-fg-color--light))
          current_label: ""             # current page label fill (default: var(--md-primary-fg-color))
```

Each `colors.*` field maps to a `--mbl-graph-*` CSS custom property emitted
at `:root`. Any value left empty keeps the Material default. You can also
override the same variables directly from your own `extra.css` if you prefer
not to put colors in `mkdocs.yml`.

## Per-page overrides

```yaml
---
back_links:
  backlinks: false   # hide the backlinks section on this page
  graph: false       # hide the graph pane on this page
---
```

## How it works

The plugin parses outbound markdown links during `mkdocs build`, builds a
page-to-page graph, and:

- Appends a backlinks `<section>` to each page when other pages link to it.
- Inlines a 1-hop subgraph per page and writes the global graph to
  `/assets/back_links/graph.json`.
- Injects a sticky pane into Material's secondary sidebar at runtime; the pane
  renders the graph with d3-force and an SVG, styled with Material's CSS
  custom properties so it adopts your theme automatically.

v0.2 adds **section-aware backlinks**: when another page links to
`page.md#some-header`, a separate backlinks block renders at the end of that
section, the section gets its own node in the graph (when targeted across
pages), and a "you are here" indicator on the graph follows your scroll position.
Same-page entries are labeled by the source heading (e.g. `# Overview`)
instead of the page title.

[material]: https://squidfunk.github.io/mkdocs-material/
