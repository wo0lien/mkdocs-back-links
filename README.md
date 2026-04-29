# mkdocs-back-links

Backlinks at the bottom of every page and a sticky force-directed graph view in
the right sidebar, for [Material for MkDocs][material].

## Install

From git (until a PyPI release is published):

```bash
pip install git+https://github.com/wo0lien/mkdocs-back-links.git@v0.1.0
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
      graph:
        enabled: true
        height: "40vh"
        max_nodes: 500
        exclude:
          - "tags.md"
          - "404.md"
```

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

[material]: https://squidfunk.github.io/mkdocs-material/
