# Section-aware backlinks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `mkdocs-back-links` v0.2.0: per-section backlinks blocks, section nodes in the graph for cross-page-targeted headers, scroll-spy "you are here" highlight, and same-page entries labeled by source heading.

**Architecture:** All link parsing and graph construction stays at build time. New pure functions in `linkgraph.py` extract headings and walk markdown to attribute links to their source section. Edges become 4-tuples `(source_page, source_section, target_page, target_section)`. The plugin consumes a new section-level inverse index to render section blocks injected into the rendered HTML via regex on heading anchors. The frontend renders unified `(page | section)` nodes with `(cross | contains)` edges and uses `IntersectionObserver` to update the scroll indicator.

**Tech Stack:** Python 3.13, MkDocs 1.6+, mkdocs-material 9.5+, `markdown.extensions.toc.slugify` (already a transitive dep via mkdocs), d3 v7 (already vendored).

**Spec:** `docs/superpowers/specs/2026-04-29-section-aware-backlinks-design.md`

**File structure (touched):**

```
src/mkdocs_back_links/
├── config.py            # extend with section_levels, section_nodes_same_page, section_collapse_threshold
├── linkgraph.py         # extend: extract_sections, extract_links_in_sections, 4-tuple edges, section index
├── render.py            # add render_section_backlinks
├── plugin.py            # wire new state, inject section blocks, emit section nodes
└── assets/
    ├── back_links.css   # section-node styling, dashed contains edges, scrolled state, section aside
    └── back_links.js    # type/kind dispatch in renderGraph + IntersectionObserver scroll-spy

tests/
├── unit/{test_linkgraph,test_config,test_render}.py   # extend
├── integration/test_build.py                            # extend
└── fixtures/
    ├── sectioned-site/{mkdocs.yml,docs/...}             # NEW
    └── sectioned-collapse/{mkdocs.yml,docs/...}         # NEW
```

---

## Task 1: Config schema additions

**Files:**
- Modify: `src/mkdocs_back_links/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_config.py`:

```python
def test_section_defaults():
    errors, _, cfg = _validate({})
    assert errors == []
    assert cfg.backlinks.section_collapse_threshold == 3
    assert cfg.graph.section_levels == [2, 3]
    assert cfg.graph.section_nodes_same_page is False


def test_section_overrides():
    errors, _, cfg = _validate(
        {
            "backlinks": {"section_collapse_threshold": 0},
            "graph": {"section_levels": [2], "section_nodes_same_page": True},
        }
    )
    assert errors == []
    assert cfg.backlinks.section_collapse_threshold == 0
    assert cfg.graph.section_levels == [2]
    assert cfg.graph.section_nodes_same_page is True


def test_bad_section_levels_rejected():
    errors, _, _ = _validate({"graph": {"section_levels": ["two"]}})
    assert errors


def test_bad_section_collapse_threshold_rejected():
    errors, _, _ = _validate({"backlinks": {"section_collapse_threshold": "many"}})
    assert errors
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 4 new failing tests (attribute errors).

- [ ] **Step 3: Add the options**

In `src/mkdocs_back_links/config.py`:

```python
class _BacklinksSection(Config):
    enabled = c.Type(bool, default=True)
    heading = c.Type(str, default="Backlinks")
    section_collapse_threshold = c.Type(int, default=3)


class _GraphSection(Config):
    enabled = c.Type(bool, default=True)
    height = c.Type(str, default="40vh")
    max_nodes = c.Type(int, default=500)
    section_levels = c.ListOfItems(c.Type(int), default=[2, 3])
    section_nodes_same_page = c.Type(bool, default=False)
    exclude = c.ListOfItems(c.Type(str), default=[])
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/config.py tests/unit/test_config.py
git commit -m "feat(config): add section_levels, section_nodes_same_page, section_collapse_threshold"
```

---

## Task 2: Section extraction with slug parity

Pure function: `extract_sections(markdown, levels)` returns ordered list of `Section(level, title, slug, line_offset)`. Slugs match MkDocs' default `markdown.extensions.toc.slugify`.

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_linkgraph.py`:

```python
from markdown.extensions.toc import slugify as _md_slugify

from mkdocs_back_links.linkgraph import Section, extract_sections


def test_extract_sections_basic():
    md = "# Title\n\n## Intro\n\nbody\n\n## Details\n\nmore"
    sections = extract_sections(md, [1, 2])
    assert sections == [
        Section(level=1, title="Title", slug="title", line_offset=0),
        Section(level=2, title="Intro", slug="intro", line_offset=2),
        Section(level=2, title="Details", slug="details", line_offset=6),
    ]


def test_extract_sections_filters_levels():
    md = "# A\n\n## B\n\n### C\n\n## D"
    sections = extract_sections(md, [2])
    assert [s.title for s in sections] == ["B", "D"]


def test_extract_sections_ignores_fenced_code():
    md = "## Real\n\n```\n## Fake heading inside fence\n```\n\n## Also real"
    sections = extract_sections(md, [2])
    assert [s.title for s in sections] == ["Real", "Also real"]


def test_extract_sections_strips_trailing_hash_chars():
    # ATX-style closed headings: "## Heading ##"
    md = "## Heading ##"
    sections = extract_sections(md, [2])
    assert sections == [Section(level=2, title="Heading", slug="heading", line_offset=0)]


def test_extract_sections_slug_parity_with_mkdocs():
    # Confirms our slugs match the reference implementation
    titles = [
        "Hello World",
        "Edge: Cases & More",
        "  Spaces  Around  ",
        "UPPERCASE / Mixed-Case",
        "non-ascii — em dash",
    ]
    md = "\n\n".join(f"## {t}" for t in titles)
    sections = extract_sections(md, [2])
    expected_slugs = [_md_slugify(t, "-") for t in titles]
    assert [s.slug for s in sections] == expected_slugs


def test_extract_sections_empty_when_no_headings():
    assert extract_sections("just some text\n\nno headings here", [1, 2, 3]) == []
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `Section` / `extract_sections`.

- [ ] **Step 3: Implement**

Append to `src/mkdocs_back_links/linkgraph.py`:

```python
from typing import NamedTuple
from markdown.extensions.toc import slugify as _md_slugify

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")


class Section(NamedTuple):
    level: int
    title: str
    slug: str
    line_offset: int


def extract_sections(markdown: str, levels: list[int]) -> list[Section]:
    """Return headings at the configured levels with MkDocs-compatible slugs.

    Skips headings inside fenced code blocks. `line_offset` is the 0-indexed
    line number of the heading in the original markdown.
    """
    cleaned = _strip_code(markdown)
    out: list[Section] = []
    for i, line in enumerate(cleaned.splitlines()):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        if level not in levels:
            continue
        title = m.group(2).strip()
        out.append(Section(level=level, title=title, slug=_md_slugify(title, "-"), line_offset=i))
    return out
```

Note: `_strip_code` already exists at the top of the module from v0.1.

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat(linkgraph): extract_sections with MkDocs-compatible slugs"
```

---

## Task 3: Walk markdown for source-section attribution

Pure function: `extract_links_in_sections(markdown, section_levels)` returns `[(href, source_section_slug_or_None), ...]` for each non-skipped link in the page. The "source section" is the slug of the most recent heading at any of the configured levels (or `None` if before the first such heading).

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import extract_links_in_sections


def test_extract_links_in_sections_attributes_source():
    md = (
        "# Title\n\n"
        "Top-level [a](one.md)\n\n"
        "## Intro\n\n"
        "Intro link [b](two.md)\n\n"
        "## Details\n\n"
        "Detail link [c](three.md)\n"
    )
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [
        ("one.md", None),
        ("two.md", "intro"),
        ("three.md", "details"),
    ]


def test_extract_links_in_sections_respects_levels():
    md = "# A\n[1](one.md)\n## B\n[2](two.md)\n### C\n[3](three.md)"
    # Only H2 counts as "source section"
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [("one.md", None), ("two.md", "b"), ("three.md", "b")]


def test_extract_links_in_sections_skips_code_fences_consistent():
    md = "## Real\n\n```\n[fake](nope.md)\n```\n\n[real](real.md)"
    pairs = extract_links_in_sections(md, [2])
    assert pairs == [("real.md", "real")]


def test_extract_links_in_sections_no_levels_returns_none_sources():
    md = "## Heading\n\n[link](page.md)"
    pairs = extract_links_in_sections(md, [])
    assert pairs == [("page.md", None)]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `extract_links_in_sections`.

- [ ] **Step 3: Implement**

Append to `src/mkdocs_back_links/linkgraph.py`:

```python
def extract_links_in_sections(
    markdown: str, section_levels: list[int]
) -> list[tuple[str, str | None]]:
    """Extract each outbound link along with the slug of its containing section.

    Walks the (code-stripped) markdown line-by-line, tracking the most recent
    heading at one of `section_levels` as the active source section. Each link
    is paired with that slug (or None if no qualifying heading has been seen yet).
    """
    cleaned = _strip_code(markdown)
    current: str | None = None
    out: list[tuple[str, str | None]] = []
    for line in cleaned.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) in section_levels:
            current = _md_slugify(m.group(2).strip(), "-")
            continue
        for lm in _LINK_RE.finditer(line):
            href = lm.group(1)
            if _is_external(href) or _is_anchor_only(href):
                continue
            out.append((href, current))
    return out
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat(linkgraph): attribute outbound links to their source section"
```

---

## Task 4: `resolve_link` returns `(page_id, fragment | None)`

Breaking change to the function's return type. Internal callers (`build_edges`) and existing tests are updated in the same task so the suite stays green.

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Update existing `resolve_link` tests to expect tuples**

In `tests/unit/test_linkgraph.py`, replace the existing `resolve_link` tests so each expected value is a tuple `(page, fragment_or_None)` (or `None` when the link does not resolve to a markdown page):

```python
def test_resolve_relative_in_same_dir():
    assert resolve_link("guides/install.md", "configure.md") == ("guides/configure.md", None)


def test_resolve_parent_dir():
    assert resolve_link("guides/install.md", "../concepts/architecture.md") == ("concepts/architecture.md", None)


def test_resolve_keeps_anchor():
    assert resolve_link("guides/install.md", "configure.md#prereqs") == ("guides/configure.md", "prereqs")


def test_resolve_strips_query_keeps_anchor():
    assert resolve_link("guides/install.md", "configure.md?x=1#sec") == ("guides/configure.md", "sec")


def test_resolve_root_relative_path():
    assert resolve_link("guides/install.md", "/concepts/architecture.md") == ("concepts/architecture.md", None)


def test_resolve_returns_none_for_non_md():
    assert resolve_link("page.md", "image.png") is None
    assert resolve_link("page.md", "file.txt") is None


def test_resolve_returns_none_for_escape_above_root():
    assert resolve_link("page.md", "../../../etc/passwd.md") is None


def test_resolve_empty_fragment_is_none():
    assert resolve_link("a.md", "b.md#") == ("b.md", None)
```

- [ ] **Step 2: Run, verify failures**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: existing `resolve_link` tests fail (return value still a string).

- [ ] **Step 3: Update `resolve_link` implementation**

In `src/mkdocs_back_links/linkgraph.py`, replace the existing `resolve_link` body:

```python
def resolve_link(source_id: str, href: str) -> tuple[str, str | None] | None:
    """Resolve a link href to (target_page_id, fragment_or_None).

    Returns None when the link doesn't point to a markdown page or escapes
    the docs root. The fragment is the slug after `#`, or None if absent.
    """
    no_query = href.split("?", 1)[0]
    page_part, _, frag_part = no_query.partition("#")
    fragment = frag_part or None
    if not page_part.endswith(".md"):
        return None
    if page_part.startswith("/"):
        candidate = posixpath.normpath(page_part.lstrip("/"))
    else:
        source_dir = posixpath.dirname(source_id)
        candidate = posixpath.normpath(posixpath.join(source_dir, page_part))
    if candidate.startswith("..") or candidate.startswith("/"):
        return None
    return candidate, fragment
```

- [ ] **Step 4: Update `build_edges` to use the tuple**

`build_edges` keeps its existing 2-tuple return shape for now (Task 5 will widen it). Replace its body in `src/mkdocs_back_links/linkgraph.py`:

```python
def build_edges(pages: Mapping[str, str]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for source_id, markdown in pages.items():
        for href in extract_links(markdown):
            resolved = resolve_link(source_id, href)
            if resolved is None:
                continue
            target, _frag = resolved
            if target == source_id or target not in pages:
                continue
            seen.add((source_id, target))
    return sorted(seen)
```

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all PASS — `build_edges` and `inverse_index` tests still match because their signatures are unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "refactor(linkgraph): resolve_link returns (page_id, fragment) tuple"
```

---

## Task 5: Edges become 4-tuples; add `inverse_section_index`

The link graph now records source and target sections. `build_edges` is renamed-by-signature (still called `build_edges`) and produces 4-tuples. `inverse_index` is renamed `inverse_page_index` (page-level, unchanged shape). A new `inverse_section_index` keys on `(target_page, target_section)`.

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `src/mkdocs_back_links/plugin.py` (caller follows the rename)
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Update existing `build_edges` and `inverse_index` tests**

In `tests/unit/test_linkgraph.py`, replace the four existing `build_edges` tests and the `inverse_index` test:

```python
def test_build_edges_simple():
    pages = {
        "a.md": "[to b](b.md)",
        "b.md": "[to c](c.md) and back to [a](a.md)",
        "c.md": "no links",
    }
    edges = build_edges(pages, section_levels=[])
    assert sorted(edges) == [
        ("a.md", None, "b.md", None),
        ("b.md", None, "a.md", None),
        ("b.md", None, "c.md", None),
    ]


def test_build_edges_drops_unknown_targets():
    pages = {
        "a.md": "[ghost](does-not-exist.md)",
        "b.md": "",
    }
    assert build_edges(pages, section_levels=[]) == []


def test_build_edges_dedupes():
    pages = {"a.md": "[1](b.md) and [2](b.md)", "b.md": ""}
    assert build_edges(pages, section_levels=[]) == [("a.md", None, "b.md", None)]


def test_build_edges_skips_self_links():
    # A whole-page self-link is dropped; an anchor self-link goes to a different
    # section so it's allowed only when source_section != target_section.
    pages = {"a.md": "[self](a.md) [to-foo](a.md#foo) [to-self](#bar)", "b.md": ""}
    # The third link is anchor-only and excluded by extract_links.
    edges = build_edges(pages, section_levels=[])
    assert edges == [("a.md", None, "a.md", "foo")]


def test_build_edges_records_target_section():
    pages = {
        "a.md": "[deep](b.md#deep-dive)",
        "b.md": "## Deep dive\n\nbody",
    }
    edges = build_edges(pages, section_levels=[])
    assert edges == [("a.md", None, "b.md", "deep-dive")]


def test_build_edges_records_source_section():
    pages = {
        "a.md": "## Intro\n\n[ext](b.md)\n\n## Details\n\n[ext2](b.md#x)",
        "b.md": "",
    }
    edges = build_edges(pages, section_levels=[2])
    assert sorted(edges) == [
        ("a.md", "details", "b.md", "x"),
        ("a.md", "intro", "b.md", None),
    ]


def test_build_edges_drops_self_section_link():
    # Same page, same source and target section -> self loop, dropped
    pages = {"a.md": "## Foo\n\n[loop](a.md#foo)", "b.md": ""}
    edges = build_edges(pages, section_levels=[2])
    assert edges == []


def test_inverse_page_index():
    edges = [
        ("a.md", None, "b.md", None),
        ("c.md", "intro", "b.md", "deep-dive"),
        ("a.md", None, "c.md", None),
    ]
    assert inverse_page_index(edges) == {
        "b.md": ["a.md", "c.md"],
        "c.md": ["a.md"],
    }


def test_inverse_section_index():
    edges = [
        ("a.md", None, "b.md", "deep-dive"),
        ("c.md", "intro", "b.md", "deep-dive"),
        ("d.md", None, "b.md", None),                # page-level link, not in section index
    ]
    assert inverse_section_index(edges) == {
        ("b.md", "deep-dive"): [("a.md", None), ("c.md", "intro")],
    }
```

Also update the import line at the top of `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import (
    Section,
    build_edges,
    extract_links,
    extract_links_in_sections,
    extract_sections,
    inverse_page_index,
    inverse_section_index,
    local_subgraph,
    resolve_link,
)
```

(Remove the now-unused `inverse_index` import.)

- [ ] **Step 2: Run, verify failures**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `inverse_page_index` / `inverse_section_index` and shape mismatches.

- [ ] **Step 3: Replace implementations in `linkgraph.py`**

Replace the existing `build_edges` and `inverse_index` functions:

```python
def build_edges(
    pages: Mapping[str, str], *, section_levels: list[int]
) -> list[tuple[str, str | None, str, str | None]]:
    """Return sorted, deduped 4-tuples (source_page, source_section, target_page, target_section).

    Drops external links, anchor-only links, links to non-markdown targets,
    links to pages outside `pages`, and self-loops where source and target
    page+section are identical.
    """
    seen: set[tuple[str, str | None, str, str | None]] = set()
    for source_id, markdown in pages.items():
        for href, source_section in extract_links_in_sections(markdown, section_levels):
            resolved = resolve_link(source_id, href)
            if resolved is None:
                continue
            target_page, target_section = resolved
            if target_page == source_id and source_section == target_section:
                continue
            if target_page not in pages:
                continue
            seen.add((source_id, source_section, target_page, target_section))
    return sorted(seen, key=lambda e: (e[0], e[1] or "", e[2], e[3] or ""))


def inverse_page_index(
    edges: Iterable[tuple[str, str | None, str, str | None]],
) -> dict[str, list[str]]:
    """Map target_page -> sorted, deduped list of source pages (ignores sections)."""
    inv: dict[str, set[str]] = defaultdict(set)
    for src, _src_sec, tgt, _tgt_sec in edges:
        inv[tgt].add(src)
    return {k: sorted(v) for k, v in inv.items()}


def inverse_section_index(
    edges: Iterable[tuple[str, str | None, str, str | None]],
) -> dict[tuple[str, str], list[tuple[str, str | None]]]:
    """Map (target_page, target_section) -> sorted list of (source_page, source_section).

    Only edges with a non-None target_section are included.
    """
    inv: dict[tuple[str, str], set[tuple[str, str | None]]] = defaultdict(set)
    for src, src_sec, tgt, tgt_sec in edges:
        if tgt_sec is None:
            continue
        inv[(tgt, tgt_sec)].add((src, src_sec))
    return {k: sorted(v, key=lambda e: (e[0], e[1] or "")) for k, v in inv.items()}
```

Delete the old `inverse_index` definition.

- [ ] **Step 4: Update the plugin caller**

In `src/mkdocs_back_links/plugin.py`:

Replace the import line:

```python
from .linkgraph import build_edges, inverse_page_index, local_subgraph
```

Update `on_env`:

```python
    def on_env(self, env, config, files):
        self._edges = build_edges(self._markdown, section_levels=self.config.graph.section_levels)
        self._inverse = inverse_page_index(self._edges)
        return env
```

The plugin's `_edges` is now 4-tuples; the existing `local_subgraph(page_id, edges)` was written assuming 2-tuples. Update its call site to pass page-only edges. In `on_page_context`, before invoking `local_subgraph`, derive page edges:

```python
        if graph_enabled:
            page_edges = [(s, t) for s, _ss, t, _ts in self._edges if s != t]
            nodes_ids, sub_edges = local_subgraph(page_id, page_edges)
```

`local_subgraph` itself stays unchanged in this task.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all PASS (existing 39 tests + 3 new from Task 1 + 6 new from Task 2 + 4 new from Task 3 + 6 new replacing the old build_edges tests + 2 new for the section indexes ≈ 60+).

- [ ] **Step 6: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py src/mkdocs_back_links/plugin.py tests/unit/test_linkgraph.py
git commit -m "refactor(linkgraph): edges as 4-tuples; split inverse index by page/section"
```

---

## Task 6: `render_section_backlinks` helper

Pure HTML rendering for one section's backlinks `<aside>`. Same-page entries are labeled `# Source heading`; cross-page entries are labeled by source page title. Collapses with `<details>` when entries exceed the threshold.

**Files:**
- Modify: `src/mkdocs_back_links/render.py`
- Modify: `tests/unit/test_render.py`

- [ ] **Step 1: Failing tests**

Append to `tests/unit/test_render.py`:

```python
from mkdocs_back_links.render import render_section_backlinks


def test_section_backlinks_basic_cross_page():
    html = render_section_backlinks(
        section_title="Deep dive",
        section_slug="deep-dive",
        target_page="b.md",
        entries=[
            {"source_page": "a.md", "source_section": None, "page_title": "A", "page_url": "/a/", "section_title_lookup": None},
        ],
        collapse_threshold=3,
    )
    assert 'class="mbl-section-backlinks"' in html
    assert 'data-section="deep-dive"' in html
    assert ">Backlinks to &quot;Deep dive&quot;</h3>" in html or '>Backlinks to "Deep dive"</h3>' in html
    assert '<a href="/a/">A</a>' in html
    assert "<details" not in html  # below threshold


def test_section_backlinks_same_page_uses_source_heading():
    html = render_section_backlinks(
        section_title="Deep dive",
        section_slug="deep-dive",
        target_page="b.md",
        entries=[
            {
                "source_page": "b.md",  # same page
                "source_section": "overview",
                "page_title": "B",
                "page_url": "/b/",
                "section_title_lookup": "Overview",
            },
        ],
        collapse_threshold=3,
    )
    assert '<a href="#overview"># Overview</a>' in html


def test_section_backlinks_collapses_when_over_threshold():
    entries = [
        {"source_page": f"p{i}.md", "source_section": None, "page_title": f"P{i}", "page_url": f"/p{i}/", "section_title_lookup": None}
        for i in range(4)
    ]
    html = render_section_backlinks(
        section_title="Hot",
        section_slug="hot",
        target_page="b.md",
        entries=entries,
        collapse_threshold=3,
    )
    assert "<details" in html
    assert "<summary" in html
    assert "4 backlinks" in html


def test_section_backlinks_threshold_zero_disables_collapse():
    entries = [
        {"source_page": f"p{i}.md", "source_section": None, "page_title": f"P{i}", "page_url": f"/p{i}/", "section_title_lookup": None}
        for i in range(10)
    ]
    html = render_section_backlinks(
        section_title="Hot",
        section_slug="hot",
        target_page="b.md",
        entries=entries,
        collapse_threshold=0,
    )
    assert "<details" not in html


def test_section_backlinks_sorted_alphabetically_by_label():
    entries = [
        {"source_page": "z.md", "source_section": None, "page_title": "Zebra", "page_url": "/z/", "section_title_lookup": None},
        {"source_page": "a.md", "source_section": None, "page_title": "Apple", "page_url": "/a/", "section_title_lookup": None},
    ]
    html = render_section_backlinks(
        section_title="X",
        section_slug="x",
        target_page="t.md",
        entries=entries,
        collapse_threshold=3,
    )
    assert html.index("Apple") < html.index("Zebra")


def test_section_backlinks_escapes_titles():
    entries = [
        {"source_page": "x.md", "source_section": None, "page_title": "<bad>", "page_url": "/x/", "section_title_lookup": None},
    ]
    html = render_section_backlinks(
        section_title="<b>Section</b>",
        section_slug="s",
        target_page="t.md",
        entries=entries,
        collapse_threshold=3,
    )
    assert "<bad>" not in html
    assert "&lt;bad&gt;" in html
    assert "<b>Section</b>" not in html
    assert "&lt;b&gt;Section&lt;/b&gt;" in html
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run pytest tests/unit/test_render.py -v
```

Expected: ImportError on `render_section_backlinks`.

- [ ] **Step 3: Implement**

Append to `src/mkdocs_back_links/render.py`:

```python
def render_section_backlinks(
    *,
    section_title: str,
    section_slug: str,
    target_page: str,
    entries: Iterable[Mapping[str, object]],
    collapse_threshold: int,
) -> str:
    """Render a single section's backlinks <aside>.

    `entries` is an iterable of dicts with keys:
      source_page, source_section, page_title, page_url, section_title_lookup
    `section_title_lookup` is the title of the source section (used when the
    entry is same-page); may be None for cross-page entries.

    When entries count > collapse_threshold (and threshold > 0), the list is
    wrapped in <details><summary>↩ N backlinks</summary>…</details>.
    """
    items = list(entries)
    if not items:
        return ""

    rendered = []
    for e in items:
        same_page = e["source_page"] == target_page
        if same_page:
            label_raw = "# " + (e.get("section_title_lookup") or e["source_section"] or e["page_title"])
            href = "#" + (e["source_section"] or "")
        else:
            label_raw = e["page_title"]
            href = e["page_url"]
        rendered.append((label_raw.lower(), label_raw, href))
    rendered.sort(key=lambda r: r[0])

    lis = "\n".join(
        f'    <li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>'
        for _key, label, href in rendered
    )

    inner = (
        f'  <h3>Backlinks to "{escape(section_title)}"</h3>\n'
        f"  <ul>\n{lis}\n  </ul>\n"
    )

    if collapse_threshold > 0 and len(items) > collapse_threshold:
        body = (
            f'  <details>\n'
            f'    <summary>↩ {len(items)} backlinks</summary>\n'
            f"{inner}"
            f'  </details>\n'
        )
    else:
        body = inner

    return (
        f'<aside class="mbl-section-backlinks" data-section="{escape(section_slug, quote=True)}">\n'
        f"{body}"
        "</aside>\n"
    )
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run pytest tests/unit/test_render.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/render.py tests/unit/test_render.py
git commit -m "feat(render): render_section_backlinks with same-page label rule and collapse"
```

---

## Task 7: Plugin — collect sections; build section inverse index

Wire section discovery into the plugin lifecycle. State is held alongside the existing per-page state.

**Files:**
- Modify: `src/mkdocs_back_links/plugin.py`

- [ ] **Step 1: Extend plugin state and on_page_markdown**

In `src/mkdocs_back_links/plugin.py`:

Update the `on_config` reset:

```python
    def on_config(self, config):
        self._markdown: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._urls: dict[str, str] = {}
        self._page_overrides: dict[str, dict] = {}
        self._sections: dict[str, list] = {}                      # NEW
        self._section_titles: dict[tuple[str, str], str] = {}      # NEW
        self._edges: list = []
        self._inverse: dict[str, list[str]] = {}
        self._inverse_section: dict[tuple[str, str], list] = {}   # NEW
        return config
```

Update the imports:

```python
from .linkgraph import (
    build_edges,
    extract_sections,
    inverse_page_index,
    inverse_section_index,
    local_subgraph,
)
```

Extend `on_page_markdown` (still keep markdown collection):

```python
    def on_page_markdown(self, markdown: str, *, page: Page, config, files):
        page_id = page.file.src_uri
        self._markdown[page_id] = markdown
        self._titles[page_id] = page.title or page_id
        self._urls[page_id] = page.url if page.url.startswith("/") else "/" + page.url
        meta_overrides = (page.meta or {}).get("back_links") or {}
        if isinstance(meta_overrides, dict):
            self._page_overrides[page_id] = meta_overrides
        # Discover headings for section-level features.
        sections = extract_sections(markdown, list(self.config.graph.section_levels))
        self._sections[page_id] = sections
        for s in sections:
            self._section_titles[(page_id, s.slug)] = s.title
        return markdown
```

Extend `on_env` to build the section index:

```python
    def on_env(self, env, config, files):
        levels = list(self.config.graph.section_levels)
        self._edges = build_edges(self._markdown, section_levels=levels)
        self._inverse = inverse_page_index(self._edges)
        self._inverse_section = inverse_section_index(self._edges)
        return env
```

- [ ] **Step 2: Run unit + integration tests**

```bash
uv run pytest -v
```

Expected: existing tests still pass — no behavior visible to integration tests yet (Task 9 emits the new HTML).

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/plugin.py
git commit -m "feat(plugin): discover sections and build section inverse index"
```

---

## Task 8: Plugin — inject per-section backlinks blocks via regex

Insert each section's backlinks `<aside>` immediately before the next heading at the same-or-higher level (or before the existing page-bottom block).

**Files:**
- Modify: `src/mkdocs_back_links/plugin.py`

- [ ] **Step 1: Add the injection helper**

In `src/mkdocs_back_links/plugin.py`, near the top (after imports), add:

```python
import re

_HEADING_TAG_RE = re.compile(r'<h([1-6])\s+id="([^"]+)"[^>]*>')
```

In `BackLinksPlugin`, add a helper method:

```python
    def _build_section_blocks(self, page_id: str) -> dict[str, str]:
        """Map slug -> rendered <aside> for sections of `page_id` that have inbound links."""
        out: dict[str, str] = {}
        for section in self._sections.get(page_id, []):
            entries_raw = self._inverse_section.get((page_id, section.slug), [])
            if not entries_raw:
                continue
            entries = []
            for src_page, src_section in entries_raw:
                entries.append({
                    "source_page": src_page,
                    "source_section": src_section,
                    "page_title": self._titles.get(src_page, src_page),
                    "page_url": self._urls.get(src_page, "/" + src_page),
                    "section_title_lookup": self._section_titles.get((src_page, src_section)) if src_section else None,
                })
            from .render import render_section_backlinks
            out[section.slug] = render_section_backlinks(
                section_title=section.title,
                section_slug=section.slug,
                target_page=page_id,
                entries=entries,
                collapse_threshold=self.config.backlinks.section_collapse_threshold,
            )
        return out

    def _inject_section_blocks(self, html: str, page_id: str) -> str:
        """Insert <aside> blocks just before the next heading boundary at same-or-higher level."""
        blocks = self._build_section_blocks(page_id)
        if not blocks:
            return html

        # Find heading boundaries in the rendered HTML.
        matches = list(_HEADING_TAG_RE.finditer(html))
        # We mutate the html as we go; insertions are processed back-to-front
        # so earlier offsets stay valid.
        insertions: list[tuple[int, str]] = []
        for i, m in enumerate(matches):
            slug = m.group(2)
            level = int(m.group(1))
            block = blocks.get(slug)
            if block is None:
                continue
            # Find the next heading at level <= this section's level (i.e., a sibling
            # or shallower heading). If none, insert at end of html.
            insert_at = len(html)
            for nxt in matches[i + 1:]:
                if int(nxt.group(1)) <= level:
                    insert_at = nxt.start()
                    break
            insertions.append((insert_at, block))

        if not insertions:
            return html

        insertions.sort(key=lambda it: it[0], reverse=True)
        for offset, block in insertions:
            html = html[:offset] + block + html[offset:]
        return html
```

Now wire the injection into `on_page_context`. Find the existing `extra = ""` block and update it so the per-section blocks are inserted into `page.content` BEFORE the page-bottom block is appended:

```python
    def on_page_context(self, context, *, page: Page, config, nav):
        page_id = page.file.src_uri
        overrides = self._page_overrides.get(page_id, {})

        backlinks_enabled = self.config.backlinks.enabled and overrides.get("backlinks", True)
        graph_enabled = self.config.graph.enabled and overrides.get("graph", True)

        # Insert per-section backlinks blocks into the rendered HTML at the
        # right boundaries.
        if backlinks_enabled and page.content:
            page.content = self._inject_section_blocks(page.content, page_id)

        extra = ""
        if backlinks_enabled:
            sources = self._inverse.get(page_id, [])
            entries = sorted(
                (
                    {"title": self._titles.get(s, s), "url": self._urls.get(s, "/" + s)}
                    for s in sources
                ),
                key=lambda e: e["title"].lower(),
            )
            extra += render_backlinks_section(
                heading=self.config.backlinks.heading, entries=entries
            )
        if graph_enabled:
            page_edges = [(s, t) for s, _ss, t, _ts in self._edges if s != t]
            nodes_ids, sub_edges = local_subgraph(page_id, page_edges)
            graph = {
                "current": page_id,
                "nodes": [
                    {"id": n, "title": self._titles.get(n, n), "url": self._urls.get(n, "/" + n)}
                    for n in nodes_ids
                ],
                "edges": [{"source": s, "target": t} for s, t in sub_edges],
            }
            extra += render_local_graph_data(graph)
            settings = {"max_nodes": self.config.graph.max_nodes}
            extra += render_settings_data(settings)

        if extra:
            page.content = (page.content or "") + extra
        return context
```

- [ ] **Step 2: Run existing integration tests**

```bash
uv run pytest tests/integration/ -v
```

Expected: existing 6 integration tests still pass — the basic-site fixture has no anchor links, so injection is a no-op there.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/plugin.py
git commit -m "feat(plugin): inject per-section backlinks blocks into rendered HTML"
```

---

## Task 9: Plugin — emit section nodes and `contains` edges in graph data

Local graph (inlined) and global graph (`graph.json`) gain section nodes (with `type: "section"`) and `contains` edges (with `kind: "contains"`). Page nodes get `type: "page"` and `kind: "cross"` is added to the existing edges.

**Files:**
- Modify: `src/mkdocs_back_links/plugin.py`

- [ ] **Step 1: Add a helper for section eligibility**

In `BackLinksPlugin` (after `_inject_section_blocks`), add:

```python
    def _section_is_graph_eligible(self, page_id: str, section) -> bool:
        """A section appears as a graph node if its level is in section_levels
        AND (cross-page link targets it, OR same-page allowed and any link)."""
        if section.level not in self.config.graph.section_levels:
            return False
        if page_id in self.config.graph.exclude:
            return False
        sources = self._inverse_section.get((page_id, section.slug), [])
        if not sources:
            return False
        if self.config.graph.section_nodes_same_page:
            return True
        # Cross-page only: at least one source from a different page
        return any(src_page != page_id for src_page, _src_section in sources)

    def _section_nodes_for_page(self, page_id: str) -> list[dict]:
        nodes = []
        for section in self._sections.get(page_id, []):
            if not self._section_is_graph_eligible(page_id, section):
                continue
            sid = f"{page_id}#{section.slug}"
            nodes.append({
                "id": sid,
                "type": "section",
                "title": section.title,
                "page": page_id,
                "url": self._urls.get(page_id, "/" + page_id).rstrip("/") + "/#" + section.slug
                       if not self._urls.get(page_id, "/" + page_id).endswith("/")
                       else self._urls.get(page_id, "/" + page_id) + "#" + section.slug,
            })
        return nodes
```

Note: build URLs by appending `#slug` to the page URL. The page URL already starts with `/` and ends with `/` for `use_directory_urls=true`; if not, the rstrip handles it.

Simpler version (always works for both URL styles):

Replace the `url` line in `_section_nodes_for_page` with:

```python
                "url": (self._urls.get(page_id, "/" + page_id)) + "#" + section.slug,
```

Actually MkDocs URLs end with `/` for directory style and `.html` for file style. Either way, appending `#slug` produces a valid URL. Use the simple form.

- [ ] **Step 2: Update local-graph emission**

Replace the local-graph block inside `on_page_context` (currently builds nodes/edges from `nodes_ids` and `sub_edges`):

```python
        if graph_enabled:
            page_edges = [(s, t) for s, _ss, t, _ts in self._edges if s != t]
            page_nodes_ids, page_sub_edges = local_subgraph(page_id, page_edges)

            # Page nodes
            nodes = [
                {
                    "id": n,
                    "type": "page",
                    "title": self._titles.get(n, n),
                    "url": self._urls.get(n, "/" + n),
                }
                for n in page_nodes_ids
            ]
            # Section nodes for the current page and any 1-hop neighbor page
            for pid in page_nodes_ids:
                nodes.extend(self._section_nodes_for_page(pid))

            # Cross edges (page <-> page) plus any cross edges that actually target
            # a section node we included.
            included_section_ids = {n["id"] for n in nodes if n["type"] == "section"}
            edges_out = []
            for s, ss, t, ts in self._edges:
                if s not in page_nodes_ids and t not in page_nodes_ids:
                    continue
                src_id = s
                tgt_id = f"{t}#{ts}" if ts and f"{t}#{ts}" in included_section_ids else t
                if src_id == tgt_id:
                    continue
                edges_out.append({"source": src_id, "target": tgt_id, "kind": "cross"})
            # Deduplicate
            edges_out = [dict(e) for e in {(d["source"], d["target"], d["kind"]) for d in edges_out}]
            edges_out = sorted(edges_out, key=lambda e: (e["source"], e["target"]))
            edges_out = [{"source": s, "target": t, "kind": k} for (s, t, k) in {(d["source"], d["target"], d["kind"]) for d in edges_out}]
            # `contains` edges from each page to its included section nodes
            for n in nodes:
                if n["type"] == "section":
                    edges_out.append({"source": n["page"], "target": n["id"], "kind": "contains"})
            # Final dedupe + sort
            seen_keys = set()
            unique_edges = []
            for e in edges_out:
                k = (e["source"], e["target"], e["kind"])
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                unique_edges.append(e)
            unique_edges.sort(key=lambda e: (e["source"], e["target"], e["kind"]))

            graph = {
                "current": page_id,
                "current_url": self._urls.get(page_id, "/" + page_id),
                "nodes": nodes,
                "edges": unique_edges,
            }
            extra += render_local_graph_data(graph)
            settings = {"max_nodes": self.config.graph.max_nodes}
            extra += render_settings_data(settings)
```

That double-dedup looks ugly — simplify by using a tuple-keyed dict from the start. Replace with:

```python
        if graph_enabled:
            page_edges = [(s, t) for s, _ss, t, _ts in self._edges if s != t]
            page_nodes_ids, page_sub_edges = local_subgraph(page_id, page_edges)

            nodes_by_id: dict[str, dict] = {
                n: {
                    "id": n,
                    "type": "page",
                    "title": self._titles.get(n, n),
                    "url": self._urls.get(n, "/" + n),
                }
                for n in page_nodes_ids
            }
            # Section nodes for the current page and any 1-hop neighbor page
            for pid in page_nodes_ids:
                for sn in self._section_nodes_for_page(pid):
                    nodes_by_id[sn["id"]] = sn

            edges_by_key: dict[tuple[str, str, str], dict] = {}

            def add_edge(src: str, tgt: str, kind: str) -> None:
                if src == tgt:
                    return
                edges_by_key[(src, tgt, kind)] = {"source": src, "target": tgt, "kind": kind}

            # Cross edges into nodes we have
            for s, _ss, t, ts in self._edges:
                if s not in page_nodes_ids and t not in page_nodes_ids:
                    continue
                tgt_id = f"{t}#{ts}" if ts and f"{t}#{ts}" in nodes_by_id else t
                if tgt_id not in nodes_by_id:
                    continue
                if s not in nodes_by_id:
                    continue
                add_edge(s, tgt_id, "cross")

            # Contains edges from each page to its included section nodes
            for n in nodes_by_id.values():
                if n["type"] == "section":
                    add_edge(n["page"], n["id"], "contains")

            graph = {
                "current": page_id,
                "current_url": self._urls.get(page_id, "/" + page_id),
                "nodes": sorted(nodes_by_id.values(), key=lambda n: (n["type"] != "page", n["id"])),
                "edges": sorted(edges_by_key.values(), key=lambda e: (e["source"], e["target"], e["kind"])),
            }
            extra += render_local_graph_data(graph)
            settings = {"max_nodes": self.config.graph.max_nodes}
            extra += render_settings_data(settings)
```

- [ ] **Step 3: Update global-graph (`on_post_build`)**

Replace the global-graph emission in `on_post_build`:

```python
    def on_post_build(self, config):
        site_dir = Path(config["site_dir"])
        out_dir = site_dir / "assets" / "back_links"
        out_dir.mkdir(parents=True, exist_ok=True)

        excluded = set(self.config.graph.exclude)

        page_nodes = [
            {
                "id": pid,
                "type": "page",
                "title": self._titles.get(pid, pid),
                "url": self._urls.get(pid, "/" + pid),
            }
            for pid in sorted(self._markdown)
            if pid not in excluded
        ]
        page_node_ids = {n["id"] for n in page_nodes}

        section_nodes: list[dict] = []
        for pid in sorted(self._markdown):
            if pid in excluded:
                continue
            section_nodes.extend(self._section_nodes_for_page(pid))
        section_node_ids = {n["id"] for n in section_nodes}

        edges: list[dict] = []
        for s, _ss, t, ts in self._edges:
            if s in excluded or t in excluded:
                continue
            tgt_id = f"{t}#{ts}" if ts and f"{t}#{ts}" in section_node_ids else t
            if tgt_id not in page_node_ids and tgt_id not in section_node_ids:
                continue
            edges.append({"source": s, "target": tgt_id, "kind": "cross"})
        for n in section_nodes:
            edges.append({"source": n["page"], "target": n["id"], "kind": "contains"})

        # Dedupe edges
        seen = set()
        unique_edges = []
        for e in edges:
            k = (e["source"], e["target"], e["kind"])
            if k in seen:
                continue
            seen.add(k)
            unique_edges.append(e)
        unique_edges.sort(key=lambda e: (e["source"], e["target"], e["kind"]))

        graph = {
            "nodes": page_nodes + section_nodes,
            "edges": unique_edges,
        }
        (out_dir / "graph.json").write_text(json.dumps(graph))

        for asset in ("back_links.css", "back_links.js"):
            src = _ASSETS_DIR / asset
            if src.exists():
                shutil.copy(src, out_dir / asset)
        vendor_src = _ASSETS_DIR / "vendor" / "d3.min.js"
        if vendor_src.exists():
            shutil.copy(vendor_src, out_dir / "d3.min.js")
```

- [ ] **Step 4: Run existing integration tests**

```bash
uv run pytest tests/integration/ -v
```

The existing assertion `'"nodes"' in content and '"edges"' in content` still passes. The basic-site fixture asserts `id="mbl-local-graph"` — still emitted. Confirm green.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/plugin.py
git commit -m "feat(plugin): emit section nodes and contains edges in graph data"
```

---

## Task 10: Integration tests with sectioned fixtures

Two new fixture sites cover the full plumbing.

**Files:**
- Create: `tests/fixtures/sectioned-site/mkdocs.yml`
- Create: `tests/fixtures/sectioned-site/docs/{a,b}.md`
- Create: `tests/fixtures/sectioned-collapse/mkdocs.yml`
- Create: `tests/fixtures/sectioned-collapse/docs/{popular,p1,p2,p3,p4}.md`
- Modify: `tests/integration/test_build.py`

- [ ] **Step 1: Create the `sectioned-site` fixture**

`tests/fixtures/sectioned-site/mkdocs.yml`:

```yaml
site_name: SectionedSite
theme:
  name: material
nav:
  - A: a.md
  - B: b.md
plugins:
  - back-links
```

`tests/fixtures/sectioned-site/docs/a.md`:

```markdown
# A

## Intro

Some intro text.

## Details

In Details we link to [the deep dive](b.md#deep-dive).
```

`tests/fixtures/sectioned-site/docs/b.md`:

```markdown
# B

## Overview

Reading the overview suggests jumping to [the deep dive](#deep-dive).

## Deep dive

Deep dive content.
```

- [ ] **Step 2: Create the `sectioned-collapse` fixture**

`tests/fixtures/sectioned-collapse/mkdocs.yml`:

```yaml
site_name: CollapseSite
theme:
  name: material
nav:
  - Popular: popular.md
  - P1: p1.md
  - P2: p2.md
  - P3: p3.md
  - P4: p4.md
plugins:
  - back-links
```

`tests/fixtures/sectioned-collapse/docs/popular.md`:

```markdown
# Popular

## Hot section

Lots of pages link here.
```

`tests/fixtures/sectioned-collapse/docs/p1.md`:
```markdown
# P1

See [hot](popular.md#hot-section).
```

`tests/fixtures/sectioned-collapse/docs/p2.md`:
```markdown
# P2

See [hot](popular.md#hot-section).
```

`tests/fixtures/sectioned-collapse/docs/p3.md`:
```markdown
# P3

See [hot](popular.md#hot-section).
```

`tests/fixtures/sectioned-collapse/docs/p4.md`:
```markdown
# P4

See [hot](popular.md#hot-section).
```

- [ ] **Step 3: Append integration tests**

Append to `tests/integration/test_build.py`:

```python
SECTIONED_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sectioned-site"
COLLAPSE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sectioned-collapse"


def _build_at(fixture: Path, tmp_path: Path) -> Path:
    site_dir = tmp_path / "site"
    subprocess.run(
        ["uv", "run", "mkdocs", "build", "--strict", "-f", str(fixture / "mkdocs.yml"), "-d", str(site_dir)],
        check=True,
    )
    return site_dir


def test_section_block_rendered_after_section(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / "b" / "index.html").read_text()
    assert 'class="mbl-section-backlinks"' in b_html
    assert 'data-section="deep-dive"' in b_html
    # Cross-page entry shows page title 'A'
    assert ">A</a>" in b_html
    # Same-page entry shows source heading "# Overview" and links to #overview
    assert ">"+"# Overview</a>" in b_html
    assert 'href="#overview"' in b_html


def test_page_bottom_dedupes_to_pages(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / "b" / "index.html").read_text()
    # The page-bottom block exists separately; A appears at most twice total
    # (once in section block, once in page-bottom).
    occurrences = b_html.count(">A</a>")
    assert 1 <= occurrences <= 2  # deduped at page level


def test_local_graph_includes_section_node(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    b_html = (site / "b" / "index.html").read_text()
    import json, re
    m = re.search(r'<script id="mbl-local-graph" type="application/json">(.+?)</script>', b_html, re.DOTALL)
    assert m
    data = json.loads(m.group(1))
    section_nodes = [n for n in data["nodes"] if n["type"] == "section"]
    assert any(n["id"] == "b.md#deep-dive" for n in section_nodes)
    contains_edges = [e for e in data["edges"] if e["kind"] == "contains"]
    assert any(e["source"] == "b.md" and e["target"] == "b.md#deep-dive" for e in contains_edges)


def test_a_local_graph_has_no_section_nodes_by_default(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    a_html = (site / "a" / "index.html").read_text()
    import json, re
    m = re.search(r'<script id="mbl-local-graph" type="application/json">(.+?)</script>', a_html, re.DOTALL)
    data = json.loads(m.group(1))
    a_section_nodes = [n for n in data["nodes"] if n["type"] == "section" and n.get("page") == "a.md"]
    assert a_section_nodes == []  # no cross-page link targets a.md's sections


def test_global_graph_has_section_nodes(tmp_path):
    site = _build_at(SECTIONED_FIXTURE, tmp_path)
    import json
    g = json.loads((site / "assets" / "back_links" / "graph.json").read_text())
    assert any(n["type"] == "section" and n["id"] == "b.md#deep-dive" for n in g["nodes"])
    assert any(e["kind"] == "contains" and e["source"] == "b.md" for e in g["edges"])


def test_collapse_threshold_wraps_in_details(tmp_path):
    site = _build_at(COLLAPSE_FIXTURE, tmp_path)
    pop = (site / "popular" / "index.html").read_text()
    assert 'data-section="hot-section"' in pop
    # Above threshold (4 > default 3): wrapped in <details>
    aside_start = pop.index('data-section="hot-section"')
    aside_end = pop.index("</aside>", aside_start)
    aside = pop[aside_start:aside_end]
    assert "<details" in aside
    assert "4 backlinks" in aside
```

- [ ] **Step 4: Run integration tests**

```bash
uv run pytest tests/integration/ -v
```

Expected: all PASS (existing 6 + 6 new = 12).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/sectioned-site tests/fixtures/sectioned-collapse tests/integration/test_build.py
git commit -m "test: integration coverage for section blocks, graph nodes, and collapse"
```

---

## Task 11: Frontend CSS — section nodes, contains edges, scrolled state, section aside

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.css`

- [ ] **Step 1: Append section-node + edge styles**

Append at the end of `back_links.css`:

```css
/* --- Section nodes & contains edges --- */
.mbl-graph-node--section {
  fill: var(--md-default-fg-color--light);
  r: 5;
}

.mbl-graph-link--contains {
  stroke-dasharray: 3 3;
  stroke-opacity: 0.45;
}

/* --- Scrolled-into-view indicator (distinct from hover) --- */
.mbl-graph-node--scrolled {
  stroke: var(--md-primary-fg-color);
  stroke-width: 2;
  stroke-opacity: 0.9;
}

.mbl-graph-label--scrolled {
  font-weight: 600;
}

/* --- Per-section backlinks aside --- */
.md-typeset .mbl-section-backlinks {
  margin: 1.5em 0;
  padding: 0.6em 0.8em;
  border-left: 3px solid var(--md-default-fg-color--lightest);
  background: var(--md-code-bg-color, var(--md-default-bg-color));
  font-size: 0.8em;
  line-height: 1.5;
}

.md-typeset .mbl-section-backlinks h3 {
  font-size: inherit;
  font-weight: 600;
  margin: 0 0 0.3em;
  padding: 0;
  border: 0;
  color: var(--md-default-fg-color--light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.md-typeset .mbl-section-backlinks ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.md-typeset .mbl-section-backlinks li {
  margin: 0.15em 0;
}

.md-typeset .mbl-section-backlinks a {
  color: var(--md-typeset-a-color);
  text-decoration: none;
}

.md-typeset .mbl-section-backlinks a:hover {
  text-decoration: underline;
}

.md-typeset .mbl-section-backlinks summary {
  cursor: pointer;
  color: var(--md-default-fg-color--light);
}
```

- [ ] **Step 2: Build demo to confirm no regressions**

```bash
uv run mkdocs build --strict
```

Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.css
git commit -m "feat(css): styles for section nodes, contains edges, scrolled state, section aside"
```

---

## Task 12: Frontend JS — render section nodes & contains edges

The renderer dispatches on `node.type` and `edge.kind`. Section nodes are smaller and use the `--section` modifier; `contains` edges use the `--contains` modifier.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Update node + link selections inside `renderGraph`**

In `back_links.js`, replace the `link` and `node` selection blocks inside `renderGraph`:

```javascript
    const link = root
      .append("g")
      .selectAll("line")
      .data(edges)
      .join("line")
      .attr("class", (d) => "mbl-graph-link" + (d.kind === "contains" ? " mbl-graph-link--contains" : ""))
      .attr("stroke-width", 1);

    const node = root
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("class", (d) => {
        const cls = ["mbl-graph-node"];
        if (d.type === "section") cls.push("mbl-graph-node--section");
        if (d.id === currentId) cls.push("mbl-graph-node--current");
        return cls.join(" ");
      })
      .attr("r", (d) => {
        if (d.type === "section") return 5;
        return d.id === currentId ? 10 : 7;
      })
      .on("click", (_event, d) => {
        if (d.url) window.location.href = d.url;
      })
      .on("mouseover", (_event, d) => focusNode(d.id))
      .on("mouseout", clearFocus);
```

The `focusNode` and `clearFocus` helpers don't need changes — they already operate on whatever the link `source`/`target` ids are, and section ids are first-class in the new data.

- [ ] **Step 2: Build, inspect**

```bash
uv run mkdocs build --strict -f tests/fixtures/sectioned-site/mkdocs.yml -d /tmp/mbl-task12
```

Open `/tmp/mbl-task12/b/index.html` in a browser via `python -m http.server -d /tmp/mbl-task12`. Confirm the graph shows a small section node attached to the page node by a dashed edge.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat(js): render section nodes and contains edges per node.type/edge.kind"
```

---

## Task 13: Frontend JS — scroll-spy with `IntersectionObserver`

When the reader scrolls a section heading into the active band, the corresponding graph node receives the `mbl-graph-node--scrolled` class (and its label `mbl-graph-label--scrolled`). At most one node carries the indicator.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Add `setupScrollSpy` and call it from `init`**

In `back_links.js`, add a helper near `init`:

```javascript
  function setupScrollSpy(pane, localData) {
    if (!("IntersectionObserver" in window)) return;
    const sectionIds = new Set(
      localData.nodes
        .filter((n) => n.type === "section" && n.page === localData.current)
        .map((n) => n.id)
    );
    if (sectionIds.size === 0) return;

    // Eligible heading elements: those whose id matches a section node we have.
    const headings = [];
    sectionIds.forEach((sid) => {
      const slug = sid.split("#", 2)[1];
      const el = document.getElementById(slug);
      if (el) headings.push({ el, sectionId: sid });
    });
    if (!headings.length) return;

    let activeId = localData.current; // default: the page itself
    const apply = (newId) => {
      if (newId === activeId) return;
      // Clear old
      const oldEl = pane.querySelector(`[data-graph-id="${cssEscape(activeId)}"]`);
      // We attach data-graph-id below in renderGraph (done in step 2).
      pane.querySelectorAll(".mbl-graph-node--scrolled, .mbl-graph-label--scrolled")
        .forEach((n) => n.classList.remove("mbl-graph-node--scrolled", "mbl-graph-label--scrolled"));
      // Apply new
      const els = pane.querySelectorAll(`[data-graph-id="${cssEscape(newId)}"]`);
      els.forEach((el) => {
        if (el.tagName === "circle") el.classList.add("mbl-graph-node--scrolled");
        if (el.tagName === "text") el.classList.add("mbl-graph-label--scrolled");
      });
      activeId = newId;
    };

    const visible = new Set();
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const sid = entry.target.dataset.mblSectionId;
          if (entry.isIntersecting) visible.add(sid);
          else visible.delete(sid);
        }
        // Pick the visible section nearest the top of the document; if none, page.
        if (visible.size === 0) {
          apply(localData.current);
        } else {
          const ordered = headings
            .filter((h) => visible.has(h.sectionId))
            .sort((a, b) => a.el.getBoundingClientRect().top - b.el.getBoundingClientRect().top);
          if (ordered.length) apply(ordered[0].sectionId);
        }
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );

    headings.forEach((h) => {
      h.el.dataset.mblSectionId = h.sectionId;
      obs.observe(h.el);
    });
  }

  // Polyfill for CSS.escape if absent (very old browsers).
  function cssEscape(s) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_ -￿-]/g, (c) => "\\" + c);
  }
```

- [ ] **Step 2: Tag rendered nodes/labels with `data-graph-id` for selector lookups**

In `renderGraph`, where the `node` and `label` selections are configured, add a `data-graph-id` attribute. Append after the `node = root.append("g")...` chain:

```javascript
    node.attr("data-graph-id", (d) => d.id);
```

And after the `label = root.append("g")...` chain:

```javascript
    label.attr("data-graph-id", (d) => d.id);
```

- [ ] **Step 3: Wire `setupScrollSpy` from `init`**

In `init`, after the existing `requestAnimationFrame(() => renderGraph(svg, data));` line, add:

```javascript
    setupScrollSpy(pane, data);
```

- [ ] **Step 4: Build the sectioned fixture and verify visually**

```bash
uv run mkdocs build --strict -f tests/fixtures/sectioned-site/mkdocs.yml -d /tmp/mbl-task13
uv run python -m http.server -d /tmp/mbl-task13 8767 &
# Visit http://localhost:8767/b/ and scroll between Overview and Deep dive.
# The section node attached to b.md should pick up the scrolled ring style as
# you reach the Deep dive heading. Then: kill %1
```

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat(js): scroll-spy updates graph 'you are here' indicator"
```

---

## Task 14: Demo site — exercise the new feature

Add cross-page anchor links to the existing demo so the demo really shows the new behavior.

**Files:**
- Modify: `docs/concepts/architecture.md`
- Modify: `docs/concepts/internals.md`
- Modify: `docs/guides/install.md`
- Modify: `docs/guides/configure.md`

- [ ] **Step 1: Add anchored sections + cross-page anchor links**

`docs/concepts/architecture.md`:

```markdown
# Architecture

High-level design overview.

## Components

The plugin has a small, focused Python core and a separate JS rendering layer.

## Data flow

Markdown is parsed at build time. See [internals](internals.md#parsing) for
how the parser walks each page line by line.
```

`docs/concepts/internals.md`:

```markdown
# Internals

Implementation details.

## Parsing

The parser walks each page line-by-line, tracking the current section.

## Rendering

Backlinks blocks are inserted by the [data flow](architecture.md#data-flow)
step right before the next heading boundary.
```

`docs/guides/install.md`:

```markdown
# Install

Before installing, read the [components overview](../concepts/architecture.md#components).

After installing, head to the [configure guide](configure.md#options).
```

`docs/guides/configure.md`:

```markdown
# Configure

## Options

Every option has a sensible default. The available set is informed by the
[data flow](../concepts/architecture.md#data-flow) — only what the build can
actually produce is exposed here.

## Examples

A minimal `mkdocs.yml` is enough for a typical docs site.
```

- [ ] **Step 2: Build and serve**

```bash
uv run mkdocs build --strict
```

Expected: clean build, no warnings.

```bash
uv run mkdocs serve
```

Open `http://127.0.0.1:8000/concepts/architecture/`. Confirm:
- Each H2 with inbound cross-page links shows a section block at the end of its content.
- The local graph shows small section nodes attached to neighbor pages.
- Scrolling between Components and Data flow updates the "you are here" ring on the right node.
- Clicking a section node navigates to that anchor on the target page.

Stop the server.

- [ ] **Step 3: Commit**

```bash
git add docs/concepts docs/guides
git commit -m "docs(demo): cross-page anchor links to exercise section feature"
```

---

## Task 15: Bump version, update README and changelog notes

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `src/mkdocs_back_links/__init__.py`

- [ ] **Step 1: Bump versions**

`pyproject.toml`:

```toml
version = "0.2.0"
```

`src/mkdocs_back_links/__init__.py`:

```python
__version__ = "0.2.0"
```

- [ ] **Step 2: Update `README.md` Configuration block**

Replace the `## Configuration` section with:

```markdown
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
        exclude:
          - "tags.md"
          - "404.md"
```
```

(Inside the README, the inner triple-backticks don't need escaping — write them as plain triple-backticks.)

Also update the install hint at the top to point at v0.2.0:

```markdown
pip install git+https://github.com/wo0lien/mkdocs-back-links.git@v0.2.0
```

- [ ] **Step 3: Run final test suite**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Build the demo with the new version**

```bash
uv run mkdocs build --strict
```

Expected: clean build.

- [ ] **Step 5: Commit and tag**

```bash
git add pyproject.toml src/mkdocs_back_links/__init__.py README.md
git commit -m "chore: bump to 0.2.0 + README config additions"
git tag -a v0.2.0 -m "v0.2.0: section-aware backlinks and graph nodes"
```

---

## Self-Review Notes

- **Spec coverage:** Configuration (Task 1), section discovery (Task 2), source-section attribution (Task 3), tuple-returning resolve_link (Task 4), 4-tuple edges + section index (Task 5), section backlinks renderer with same-page rule and collapse (Task 6), plugin wiring (Tasks 7–9), integration coverage (Task 10), CSS (Task 11), JS rendering (Task 12), scroll-spy (Task 13), demo site (Task 14), README + version (Task 15). All spec sections covered.
- **Type consistency:**
  - `Section` NamedTuple defined in Task 2; used by name in Tasks 3, 7, 8, 9.
  - Edge tuple shape `(source, source_section, target, target_section)` introduced in Task 5 and consistent through Tasks 7, 8, 9, 10.
  - `inverse_page_index` and `inverse_section_index` names consistent across Tasks 5, 7, 8.
  - `_section_nodes_for_page` plugin helper used by both local-graph (Task 9) and global-graph (Task 9 step 3) — single source of truth.
- **Placeholder scan:** No TBD/TODO/"add appropriate validation" — every step shows the actual code or command.
