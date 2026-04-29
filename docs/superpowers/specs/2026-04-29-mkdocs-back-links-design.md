# mkdocs-back-links — Design

**Date:** 2026-04-29
**Status:** Approved

## Goal

Build an MkDocs plugin that adds two features to a Material-themed documentation site:

1. **Backlinks** — a list at the bottom of every page showing which other pages link to it.
2. **Graph view** — an interactive force-directed graph in a sticky pane at the bottom of the right sidebar, showing the page's neighborhood (local) or the whole site (global).

The repository ships both the plugin package (`mkdocs-back-links`) and a demo MkDocs site under `docs/` that exercises the plugin end-to-end.

## Scope decisions

- **Link format:** standard Markdown only (`[label](path.md)`, including relative paths). No wikilinks, no extra parser extensions.
- **Graph scope:** both local (current page + 1-hop neighbors) and global (entire site), toggled in the pane header.
- **Pane placement:** sticky at the bottom of Material's secondary (right) sidebar. The TOC stays at the top of that sidebar, scrolling normally above the graph.
- **Rendering:** d3-force + hand-rolled SVG, styled with Material CSS custom properties so the graph adopts light/dark/palette changes for free. Chosen over Cytoscape.js / Sigma / vis-network for bundle size, theme integration, and full control over a small surface.

## Repository layout

```
mkdocs-back-links/
├── pyproject.toml              # plugin package metadata + entry points
├── src/
│   └── mkdocs_back_links/
│       ├── __init__.py
│       ├── plugin.py           # MkDocs plugin class (lifecycle hooks)
│       ├── linkgraph.py        # builds page -> page graph from markdown
│       ├── assets/
│       │   ├── back_links.css
│       │   └── back_links.js   # d3-force + SVG rendering
│       └── templates/
│           └── back_links.html # snippet templates (backlinks, graph pane)
├── docs/                       # demo site content
│   ├── index.md
│   ├── topic-a.md
│   └── ...
├── mkdocs.yml                  # demo site config, with the plugin enabled
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
        └── basic-site/
```

The plugin is published as `mkdocs-back-links` and registered as an MkDocs plugin entry point named `back-links` (so users add `- back-links` to `plugins:`).

## Build-time data flow

The plugin computes all backlink and graph data during `mkdocs build`. Nothing is computed in the browser.

Lifecycle hooks:

1. **`on_files`** — inventory all markdown files and their canonical URLs (respecting `use_directory_urls`).
2. **`on_page_markdown`** — for each page, parse outbound markdown links via regex on the raw markdown. Code fences are stripped before parsing. External URLs and anchor-only links are skipped. Relative `.md` targets are resolved to canonical page URLs. Edges accumulate in plugin state.
3. **`on_env`** — once all pages are parsed, build the inverse index (`page → list of pages linking to it`) and serialize the global graph (nodes = pages, edges = links) to JSON.
4. **`on_page_context`** — inject per-page values into the template context:
   - `backlinks`: list of `{title, url}` for pages linking to this page.
   - `local_graph`: subgraph containing this page + 1-hop neighbors (both inbound and outbound).
5. **`on_page_content`** — append the rendered backlinks `<section>` to the page HTML when `backlinks` is non-empty.
6. **`on_post_build`** — write the global graph JSON to `assets/back_links/graph.json` in the site output and copy `back_links.css` / `back_links.js`.

### Data shapes

Global graph (one file, served from `/assets/back_links/graph.json`):

```json
{
  "nodes": [
    { "id": "guides/install", "title": "Install", "url": "/guides/install/" }
  ],
  "edges": [
    { "source": "guides/install", "target": "guides/configure" }
  ]
}
```

Per-page (passed via template context, inlined into the page):

```python
backlinks = [{"title": "...", "url": "..."}, ...]
local_graph = {"nodes": [...], "edges": [...]}
```

## Backlinks rendering

A section appended to the main content area, after the page body. Markup:

```html
<section class="mbl-backlinks" aria-labelledby="mbl-backlinks-heading">
  <h2 id="mbl-backlinks-heading">Backlinks</h2>
  <ul>
    <li><a href="/guides/install/">Install</a></li>
    <li><a href="/concepts/architecture/">Architecture</a></li>
  </ul>
</section>
```

Rules:

- Renders only when `backlinks` is non-empty — no empty section, no "No backlinks" placeholder.
- List sorted alphabetically by linking page title for stable output.
- Each entry shows the linking page's title (from MkDocs nav metadata) and links to its URL.
- Styled with Material tokens — no custom palette.

Injection mechanism: appended via `on_page_content` (concatenated to the page's rendered HTML). This avoids requiring users to set `theme.custom_dir`, which Material itself uses.

The graph pane is injected at runtime by `back_links.js`: on `DOMContentLoaded`, the script locates `.md-sidebar--secondary .md-sidebar__scrollwrap` and appends the pane element. Going through JS avoids template overrides and the `custom_dir` collision; the small flash before injection is acceptable for a sidebar element below the fold.

## Graph pane

A pane anchored at the bottom of Material's secondary (right) sidebar.

### Layout & sizing

- Width: matches the secondary sidebar width.
- Height: `40vh` by default, configurable via `graph.height`.
- Position: `position: sticky; bottom: 0` inside the secondary sidebar.
- The TOC above receives `padding-bottom` equal to graph height so its last items stay reachable.
- Hidden on small viewports (inherits Material's existing behavior of hiding the secondary sidebar).

### Header strip

- Title: `Graph`
- Toggle: two pills, **Local** (default) / **Global**.
- Expand button: opens the graph in a full-viewport modal overlay (escape or click outside to close).

### Rendering

- Single `<svg>`. d3-force simulation drives `<circle>` nodes and `<line>` edges.
- Current page node: filled with `--md-primary-fg-color`, larger radius.
- Other nodes: `--md-default-fg-color`.
- Edges: `--md-default-fg-color--lightest` at low opacity.
- Hover: page title shown via native `<title>` element (no JS tooltip code).
- Click: navigates to the node's URL (`window.location.href`).
- Drag a node to pin it; double-click to unpin.
- Pan and pinch-zoom via a single SVG transform group.

### Local vs global data

- **Local:** inlined into the page in a `<script type="application/json">` tag. Loads instantly with the page.
- **Global:** lazily fetched from `/assets/back_links/graph.json` the first time the user toggles to **Global**, then cached for the rest of the session.

### Performance guard

If the global graph has more than `graph.max_nodes` (default 500) nodes, the d3 simulation runs a fixed number of ticks then freezes — no continuous animation. Drag still re-energizes a small local region. This keeps large sites responsive.

## Configuration

Plugin options exposed via `mkdocs.yml`. All have sensible defaults so a bare `- back-links` works.

```yaml
plugins:
  - back-links:
      backlinks:
        enabled: true              # toggle bottom section site-wide
        heading: "Backlinks"       # heading text (i18n hook)
      graph:
        enabled: true              # toggle sticky pane site-wide
        height: "40vh"             # CSS height of the sticky pane
        default_view: "local"      # "local" | "global"
        max_nodes: 500             # freeze threshold for global graph
        exclude:                   # glob patterns to exclude from the graph
          - "tags.md"
          - "404.md"
```

Per-page overrides via front-matter:

```yaml
---
back_links:
  backlinks: false   # hide backlinks section on this page
  graph: false       # hide graph pane on this page
---
```

Page-level keys override site-level. `exclude` removes pages from both nodes and edges of the graph; v1 does not preserve transitive connections through excluded pages.

Validation uses MkDocs' typed `Config` class. Bad values fail the build with a clear error.

## Testing

### Unit tests (`tests/unit/`) — fast, no MkDocs build

- `linkgraph.py` parsing: standard markdown links, relative paths, anchors stripped, code-fence skipping, `use_directory_urls` on/off.
- Backlink inverse-index correctness on small fixtures.
- Local subgraph extraction (1-hop neighborhood including inbound + outbound).
- Config validation: bad types, unknown keys, glob patterns.

### Integration tests (`tests/integration/`) — fixture-based MkDocs builds

- `tests/fixtures/basic-site/` — small site with 5 pages and known link structure. Build it; assert HTML contains the expected backlinks list and inlined `local_graph` JSON.
- Per-page front-matter override actually suppresses the section.
- Global `graph.json` is written to the site output, parses as JSON, has the expected node/edge counts.

### No browser/JS tests for v1

The rendering JS is small, framework-free, and easier to verify by eye in the demo site than to set up a headless browser harness. Revisit if the JS grows.

### Tooling

- `pytest` for tests, run via `uv run pytest`.
- The repo is a single `uv`-managed project; the plugin is installed in editable mode so the demo site under `docs/` picks up local changes immediately.
- Demo site built with `uv run mkdocs build` / served with `uv run mkdocs serve`.

## Out of scope for v1

- Wikilinks (`[[page]]`) or other non-standard link syntaxes.
- Tags or folders as graph nodes.
- Browser-based JS test harness.
- Preserving transitive connections through excluded pages.
- Customizable graph color palettes beyond Material's CSS variables.
