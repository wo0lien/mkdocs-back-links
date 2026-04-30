# Section-aware backlinks and graph nodes — Design

**Date:** 2026-04-29
**Status:** Approved
**Targets:** mkdocs-back-links v0.2.0

## Goal

Extend the plugin so links that target specific page anchors (`page.md#section`) are first-class citizens in both the backlinks UI and the graph view.

Concretely:

1. A **per-section backlinks block** renders at the end of any heading-eligible section that has at least one inbound link, in addition to the existing page-bottom block.
2. The graph gains **section nodes** for sections that meet eligibility rules, attached to their parent page node by a `"contains"` edge.
3. As the reader **scrolls through the page**, a "you are here" highlight on the graph shifts between the page node and the current section node — visually distinct from hover focus.
4. Backlinks coming from the **same page as the target** display the source heading (`# Source heading`) instead of the page title.

## Scope decisions

- Eligible heading levels are configurable via `graph.section_levels`, default `[2, 3]`.
- Section nodes default to "cross-page links only" — same-page-only references still get a backlinks block but don't add a graph node. Configurable via `graph.section_nodes_same_page`.
- Section backlinks blocks render **at the end of the section's content**, just before the next heading at the same-or-higher level. Pure-HTML `<details>` is used to collapse the list when entries exceed `backlinks.section_collapse_threshold` (default 3).
- Anchor slug generation matches MkDocs' default `markdown.extensions.toc.slugify` so the plugin's anchor ids align with the rendered HTML's `id="…"` attributes — no second source of truth.
- No JavaScript test harness for v0.2 (same call as v0.1).

## Configuration

Three new options on top of the existing schema:

```yaml
plugins:
  - back-links:
      backlinks:
        enabled: true
        heading: "Backlinks"
        section_collapse_threshold: 3   # collapse when entries > this; 0 disables collapse
      graph:
        enabled: true
        height: "40vh"
        max_nodes: 500
        section_levels: [2, 3]          # heading levels eligible for section treatment
        section_nodes_same_page: false  # if true, sections targeted only by same-page links also get graph nodes
        exclude:
          - "tags.md"
```

All defaults are backward-compatible: existing v0.1.0 sites picking up the upgrade get section-level backlinks "for free" (since H2/H3 are common targets) but gain no clutter from same-page-only references in the graph.

## Data model

### Link resolution

`resolve_link` is changed to preserve fragments:

```python
def resolve_link(source_id: str, href: str) -> tuple[str, str | None] | None:
    """Returns (page_id, fragment) or None.
    fragment is the slug after #, or None if the link has no fragment."""
```

### Section discovery

A new pure function in `linkgraph.py`:

```python
def extract_sections(markdown: str, levels: list[int]) -> list[Section]:
    """Section = {level, title, slug, line_offset}.
    Slugs use MkDocs' default slugify (markdown.extensions.toc.slugify)."""
```

Headings inside fenced code blocks are skipped, matching `extract_links`'s discipline.

### Edge shape

Edges are now 4-tuples:

```
(source_page_id, source_fragment_or_None, target_page_id, target_fragment_or_None)
```

`source_fragment` is determined by walking the markdown line-by-line and tracking the *current section* — at each link-extraction site, the source fragment is the slug of the most recent heading at any level (`None` if before the first heading on the page).

### Indexes

The plugin computes two indexes during `on_env`:

- `_inverse_page[target_page] -> list[(source_page, source_section)]` — feeds the page-bottom block (target-section is collapsed away; entries are deduped at the page level).
- `_inverse_section[(target_page, target_fragment)] -> list[(source_page, source_section)]` — feeds the per-section blocks.

### Per-page state

```python
self._sections: dict[page_id, list[Section]]
self._edges: list[tuple[page, section_or_None, page, section_or_None]]
self._inverse_page: dict[str, list[tuple[str, str | None]]]
self._inverse_section: dict[tuple[str, str], list[tuple[str, str | None]]]
```

## Backlinks rendering

### Page-bottom block (existing, slightly enriched)

Same position, same alphabetical sort. v0.2 keeps it page-level: each linking *page* appears once, regardless of how many of its sections link to this page. Section-specific information lives in the per-section blocks below.

### Per-section blocks

For each eligible heading with at least one inbound link:

```html
<aside class="mbl-section-backlinks" data-section="data-flow">
  <h3>Backlinks to "Data flow"</h3>
  <ul>
    <li><a href="/guides/install/">Install</a></li>
    <li><a href="/concepts/architecture/#prereqs"># Prereqs</a></li>   <!-- same-page -->
  </ul>
</aside>
```

Rules:

- Heading text is the section's title (HTML-escaped).
- Each entry shows the linking *page* by title and links to its URL.
- **Same-page rule**: when `source_page == target_page`, the entry text is `# <source-heading-title>` and the href points to that source section's anchor on the same page (`#source-slug`).
- Sorted alphabetically by entry text.
- When `entries.count > section_collapse_threshold` and threshold > 0, the list is wrapped in `<details><summary>↩ N backlinks</summary>…</details>`. Pure HTML — no JS required.

### Injection mechanism

The page-bottom block continues using `on_page_context` to mutate `page.content`. Per-section blocks land *inside* the rendered HTML at the right position via regex-driven string insertion:

1. Build a list of `(slug, html_block)` pairs for the page's eligible-and-targeted sections.
2. Find each `<h2 id="slug">` / `<h3 id="slug">` in the rendered HTML using `re.finditer(r'<h([1-6]) id="([^"]+)"')`.
3. For each match whose slug is in our list, locate the *next* heading at the same-or-higher level (or the end of `page.content`) and insert the block immediately before that boundary.

No external HTML parser dependency.

## Graph data and rendering

### Local graph (inlined per page)

```json
{
  "current": "concepts/architecture.md",
  "current_url": "/concepts/architecture/",
  "nodes": [
    {
      "id": "concepts/architecture.md",
      "type": "page",
      "title": "Architecture",
      "url": "/concepts/architecture/"
    },
    {
      "id": "concepts/architecture.md#data-flow",
      "type": "section",
      "title": "Data flow",
      "page": "concepts/architecture.md",
      "url": "/concepts/architecture/#data-flow"
    },
    {
      "id": "guides/install.md",
      "type": "page",
      "title": "Install",
      "url": "/guides/install/"
    }
  ],
  "edges": [
    { "source": "guides/install.md", "target": "concepts/architecture.md#data-flow", "kind": "cross" },
    { "source": "concepts/architecture.md", "target": "concepts/architecture.md#data-flow", "kind": "contains" }
  ]
}
```

### Global graph (`/assets/back_links/graph.json`)

Same shape; pages and sections live in one `nodes` array, distinguished by `type`.

### Inclusion rules for section nodes

A section appears as a graph node when **all** of:

1. Its heading level ∈ `graph.section_levels`.
2. Its parent page is included in the graph (i.e., not in `graph.exclude`).
3. At least one of:
   - It has any inbound *cross-page* link, OR
   - `graph.section_nodes_same_page: true` and it has any inbound link (cross or same-page).

For each section node included, the plugin emits a `"contains"` edge from the page node to that section node.

### Visual treatment

- **Page node**: same as v0.1 (current page = primary fill, others = default fg, current radius 10, others 7).
- **Section node**: smaller radius (5 px), lighter fill (`--md-default-fg-color--light`).
- **`"contains"` edge**: dashed stroke (`stroke-dasharray: 3 3`), reduced opacity (~0.5).
- **`"cross"` edge**: today's solid stroke.
- **Click on a section node** sets `window.location.href` to the node's `url` — page URL plus `#anchor` — so the browser scrolls there.
- **Hover focus mode**: works unchanged. Section nodes are first-class for connection lookup.

## Scroll-spy / "you are here" highlight

### Detection

`IntersectionObserver` watches the `<h2>` / `<h3>` elements that correspond to graph-eligible-AND-targeted sections (i.e., the same set that produced section nodes). `rootMargin` is `-20% 0px -70% 0px` — a heading is "active" while sitting in roughly the top fifth of the viewport.

### State machine

- Initial state: current *page* node carries the indicator.
- When a heading enters the active band, the indicator moves to that section's node.
- When the active band contains zero eligible headings (e.g., scrolled above the first or past the last), the indicator reverts to the page node.
- At most one node carries the indicator at any time.

### Visual style — distinct from hover focus

Hover focus uses fill color and neighbor fading. The scroll indicator is quieter and persistent:

```css
.mbl-graph-node--scrolled {
  stroke: var(--md-primary-fg-color);
  stroke-width: 2;
  stroke-opacity: 0.9;
}
.mbl-graph-label--scrolled {
  font-weight: 600;
}
```

No fill change, no neighbor fading. Hover focus and scroll indicator coexist.

### Performance

`IntersectionObserver` is passive — no JS runs while the reader isn't crossing a heading boundary. Each crossing costs one class swap on the relevant graph elements.

## Testing

### Unit tests

- `extract_sections`: H1–H6 detection, slug correctness against MkDocs' `markdown.extensions.toc.slugify`, fenced-code skipping, level filter, headings inside HTML blocks ignored.
- `resolve_link` returns `(page_id, fragment)` for: bare links, fragment links, anchor-only (still excluded), `?query` strings stripped, escape-above-root rejected.
- `build_edges` returns 4-tuples; `source_fragment` is set from the walking heading state; edges to non-existent pages dropped; self-page-self-section dropped.
- `inverse_page` and `inverse_section` indexes built correctly.
- Section node inclusion: under default config, under `section_nodes_same_page: true`, under different `section_levels`.
- `render_section_backlinks` helper: list rendering, alphabetical sort, same-page entry uses `# Source heading`, `<details>` wrap when over threshold.

### Integration tests

A new fixture site `tests/fixtures/sectioned-site/`:

- `a.md` with H2 `Intro`, H2 `Details`. The `Details` section contains `[here](b.md#deep-dive)`.
- `b.md` with H2 `Overview`, H2 `Deep dive`. The `Overview` section contains `[same-page jump](#deep-dive)`.

Assertions against the built `site/`:

- `b.md` rendered HTML contains `<aside class="mbl-section-backlinks" data-section="deep-dive">` *after* the Deep-dive section content. The block has two entries: `A` (cross-page link from `a.md`, labeled by the source page title) and `# Overview` (same-page link, labeled by the source heading).
- The page-bottom block on `b.md` contains a single `A` entry (page-level dedupe).
- `b.md`'s inlined `local_graph` includes a section node for `b.md#deep-dive` with `type: "section"` and a `"contains"` edge from `b.md`.
- `a.md`'s inlined `local_graph` does NOT include a section node for any of its sections (no cross-page links target them; default config).
- Global `graph.json` contains both page and section nodes consistently.
- A second fixture (`tests/fixtures/sectioned-collapse/`) with one section receiving 4 inbound links: assert the rendered HTML wraps that block in `<details>`.
- Per-page front-matter `back_links: { backlinks: false }` suppresses both page-bottom and all per-section blocks for that page.

### No JS test harness for v0.2

The scroll-spy logic is small and visually verifiable in the demo site. Revisit if it grows.

## Out of scope for v0.2

- Showing the linked-target section anchor next to entries in the page-bottom block (e.g., `Architecture → Data flow`).
- Configurable styling for the scroll indicator beyond the Material CSS variables.
- A "linked from" preview popover when hovering a section node.
- Re-ordering page-bottom entries by linked-section count.
