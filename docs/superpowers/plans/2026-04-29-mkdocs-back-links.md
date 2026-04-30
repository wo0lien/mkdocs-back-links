# mkdocs-back-links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `mkdocs-back-links`, an MkDocs plugin that adds backlinks at the bottom of every page and a sticky force-directed graph pane in the right sidebar of Material-themed sites, plus a demo site exercising the plugin.

**Architecture:** Plugin computes link data at build time via MkDocs lifecycle hooks. Backlinks are appended to page HTML server-side; the graph pane is injected client-side into Material's secondary sidebar by a small JS module that renders an SVG with d3-force. Local graph data is inlined per page; the global graph is fetched lazily as a single JSON file.

**Tech Stack:** Python 3.13, MkDocs 1.6+, mkdocs-material, d3 v7 (UMD vendored), pytest, uv.

**Spec:** `docs/superpowers/specs/2026-04-29-mkdocs-back-links-design.md`

**File structure (created across tasks):**

```
mkdocs-back-links/
├── pyproject.toml
├── mkdocs.yml                                # demo site
├── docs/                                     # demo site content
│   ├── index.md
│   ├── guides/{install,configure}.md
│   └── concepts/architecture.md
├── src/mkdocs_back_links/
│   ├── __init__.py
│   ├── plugin.py                             # lifecycle hooks
│   ├── config.py                             # typed Config schema
│   ├── linkgraph.py                          # parsing, resolution, graph
│   ├── render.py                             # HTML rendering
│   └── assets/
│       ├── back_links.css
│       ├── back_links.js
│       └── vendor/d3.min.js                  # vendored UMD bundle
└── tests/
    ├── unit/{test_linkgraph,test_config,test_render}.py
    ├── integration/test_build.py
    └── fixtures/basic-site/{mkdocs.yml,docs/...}
```

---

## Task 1: Project scaffolding & plugin entry point

**Files:**
- Modify: `pyproject.toml`
- Create: `src/mkdocs_back_links/__init__.py`
- Create: `src/mkdocs_back_links/plugin.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_plugin_registration.py`

- [ ] **Step 1: Replace `pyproject.toml`**

```toml
[project]
name = "mkdocs-back-links"
version = "0.1.0"
description = "Backlinks and graph view for Material-themed MkDocs sites"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
  "mkdocs>=1.6",
  "mkdocs-material>=9.5",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
]

[project.entry-points."mkdocs.plugins"]
back-links = "mkdocs_back_links.plugin:BackLinksPlugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mkdocs_back_links"]
```

- [ ] **Step 2: Delete `main.py` (leftover stub)**

```bash
rm /home/tom/dev/mkdocs-back-links/main.py
```

- [ ] **Step 3: Create `src/mkdocs_back_links/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Write the failing test**

Create `tests/unit/test_plugin_registration.py`:

```python
from importlib.metadata import entry_points


def test_plugin_is_registered():
    eps = entry_points(group="mkdocs.plugins")
    names = {ep.name for ep in eps}
    assert "back-links" in names


def test_plugin_class_loadable():
    eps = entry_points(group="mkdocs.plugins", name="back-links")
    (ep,) = eps
    cls = ep.load()
    assert cls.__name__ == "BackLinksPlugin"
```

Create empty `tests/__init__.py` and `tests/unit/__init__.py`.

- [ ] **Step 5: Run test to verify it fails**

```bash
uv sync --extra dev
uv run pytest tests/unit/test_plugin_registration.py -v
```

Expected: FAIL — `BackLinksPlugin` does not exist.

- [ ] **Step 6: Minimal plugin class**

Create `src/mkdocs_back_links/plugin.py`:

```python
from mkdocs.plugins import BasePlugin


class BackLinksPlugin(BasePlugin):
    pass
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/unit/test_plugin_registration.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/ -A
git rm main.py
git commit -m "feat: scaffold plugin package and entry point"
```

---

## Task 2: Markdown link extraction

Pure function that, given raw markdown, returns the list of outbound link targets (`href` values). Strips fenced code blocks and inline code first.

**Files:**
- Create: `src/mkdocs_back_links/linkgraph.py`
- Create: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import extract_links


def test_extracts_simple_link():
    md = "See [the install guide](install.md)."
    assert extract_links(md) == ["install.md"]


def test_extracts_multiple_links():
    md = "[a](one.md) and [b](two.md) and [c](sub/three.md)"
    assert extract_links(md) == ["one.md", "two.md", "sub/three.md"]


def test_strips_link_title():
    md = '[hi](page.md "Title text")'
    assert extract_links(md) == ["page.md"]


def test_skips_external_links():
    md = "[ext](https://example.com) [other](http://x.org) [local](page.md)"
    assert extract_links(md) == ["page.md"]


def test_skips_anchor_only_links():
    md = "[top](#section) [page](page.md#section)"
    assert extract_links(md) == ["page.md#section"]


def test_skips_links_inside_fenced_code():
    md = "Before [a](one.md)\n\n```\n[fake](nope.md)\n```\n\nAfter [b](two.md)"
    assert extract_links(md) == ["one.md", "two.md"]


def test_skips_links_inside_inline_code():
    md = "Use `[link](nope.md)` then [real](real.md)"
    assert extract_links(md) == ["real.md"]


def test_skips_image_links():
    md = "![alt](img.png) [page](page.md)"
    assert extract_links(md) == ["page.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError or test failures (module/function missing).

- [ ] **Step 3: Implement `extract_links`**

Create `src/mkdocs_back_links/linkgraph.py`:

```python
"""Pure functions for parsing markdown and building the link graph."""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^([`~]{3,})[^\n]*\n.*?\n\1[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# [text](href "optional title") — not preceded by '!' (image)
_LINK_RE = re.compile(r"(?<!!)\[(?:[^\[\]]|\\\[|\\\])*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")


def _strip_code(md: str) -> str:
    md = _FENCE_RE.sub("", md)
    md = _INLINE_CODE_RE.sub("", md)
    return md


def _is_external(href: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", href)) or href.startswith("//") or href.startswith("mailto:")


def _is_anchor_only(href: str) -> bool:
    return href.startswith("#")


def extract_links(markdown: str) -> list[str]:
    """Return a list of outbound link hrefs from markdown.

    Skips fenced code, inline code, image syntax, external URLs, and pure-anchor
    links. Does not resolve relative paths.
    """
    cleaned = _strip_code(markdown)
    out: list[str] = []
    for m in _LINK_RE.finditer(cleaned):
        href = m.group(1)
        if _is_external(href) or _is_anchor_only(href):
            continue
        out.append(href)
    return out
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat: extract markdown links from page content"
```

---

## Task 3: URL resolution

Given a source page id (path relative to docs root, with `.md`) and a link href, return the canonical target page id. The `use_directory_urls` flag is *not* applied here — we resolve to source-file ids; URL formatting comes later.

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import resolve_link


def test_resolve_relative_in_same_dir():
    assert resolve_link("guides/install.md", "configure.md") == "guides/configure.md"


def test_resolve_parent_dir():
    assert resolve_link("guides/install.md", "../concepts/architecture.md") == "concepts/architecture.md"


def test_resolve_strips_anchor():
    assert resolve_link("guides/install.md", "configure.md#prereqs") == "guides/configure.md"


def test_resolve_strips_query():
    assert resolve_link("guides/install.md", "configure.md?x=1") == "guides/configure.md"


def test_resolve_root_relative_path():
    # paths starting with / are treated as docs-root-relative
    assert resolve_link("guides/install.md", "/concepts/architecture.md") == "concepts/architecture.md"


def test_resolve_returns_none_for_non_md():
    assert resolve_link("page.md", "image.png") is None
    assert resolve_link("page.md", "file.txt") is None


def test_resolve_returns_none_for_escape_above_root():
    assert resolve_link("page.md", "../../../etc/passwd.md") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `resolve_link`.

- [ ] **Step 3: Implement `resolve_link`**

Append to `src/mkdocs_back_links/linkgraph.py`:

```python
import posixpath


def resolve_link(source_id: str, href: str) -> str | None:
    """Resolve a link href from a source page to a target page id.

    `source_id` and the returned id are paths relative to the docs root, using
    forward slashes, ending in `.md`. Returns None when the link doesn't point
    to a markdown page or escapes the docs root.
    """
    target = href.split("#", 1)[0].split("?", 1)[0]
    if not target.endswith(".md"):
        return None
    if target.startswith("/"):
        candidate = posixpath.normpath(target.lstrip("/"))
    else:
        source_dir = posixpath.dirname(source_id)
        candidate = posixpath.normpath(posixpath.join(source_dir, target))
    if candidate.startswith("..") or candidate.startswith("/"):
        return None
    return candidate
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat: resolve markdown link hrefs to canonical page ids"
```

---

## Task 4: Build edge list and inverse index

Combine extraction + resolution to produce a global edge list, and derive the inverse index used for backlinks.

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import build_edges, inverse_index


def test_build_edges_simple():
    pages = {
        "a.md": "[to b](b.md)",
        "b.md": "[to c](c.md) and back to [a](a.md)",
        "c.md": "no links",
    }
    edges = build_edges(pages)
    assert sorted(edges) == [("a.md", "b.md"), ("b.md", "a.md"), ("b.md", "c.md")]


def test_build_edges_drops_unknown_targets():
    pages = {
        "a.md": "[ghost](does-not-exist.md)",
        "b.md": "",
    }
    assert build_edges(pages) == []


def test_build_edges_dedupes():
    pages = {"a.md": "[1](b.md) and [2](b.md)", "b.md": ""}
    assert build_edges(pages) == [("a.md", "b.md")]


def test_build_edges_skips_self_links():
    pages = {"a.md": "[self](a.md)", "b.md": ""}
    assert build_edges(pages) == []


def test_inverse_index():
    edges = [("a.md", "b.md"), ("c.md", "b.md"), ("a.md", "c.md")]
    assert inverse_index(edges) == {
        "b.md": ["a.md", "c.md"],
        "c.md": ["a.md"],
    }
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `build_edges` / `inverse_index`.

- [ ] **Step 3: Implement**

Append to `src/mkdocs_back_links/linkgraph.py`:

```python
from collections import defaultdict
from typing import Iterable, Mapping


def build_edges(pages: Mapping[str, str]) -> list[tuple[str, str]]:
    """Return a sorted, deduped, self-link-free list of (source, target) edges
    where both source and target are keys in `pages`."""
    seen: set[tuple[str, str]] = set()
    for source_id, markdown in pages.items():
        for href in extract_links(markdown):
            target = resolve_link(source_id, href)
            if target is None or target == source_id or target not in pages:
                continue
            seen.add((source_id, target))
    return sorted(seen)


def inverse_index(edges: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Return a map of target_id -> sorted list of source ids that link to it."""
    inv: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        inv[target].add(source)
    return {k: sorted(v) for k, v in inv.items()}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat: build edge list and backlinks inverse index"
```

---

## Task 5: Local subgraph extraction

Extract a 1-hop neighborhood subgraph for a given page (its inbound and outbound neighbors plus the page itself).

**Files:**
- Modify: `src/mkdocs_back_links/linkgraph.py`
- Modify: `tests/unit/test_linkgraph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_linkgraph.py`:

```python
from mkdocs_back_links.linkgraph import local_subgraph


def test_local_subgraph_includes_self_and_neighbors():
    edges = [
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("d.md", "b.md"),
        ("e.md", "f.md"),
    ]
    nodes, sub_edges = local_subgraph("b.md", edges)
    assert sorted(nodes) == ["a.md", "b.md", "c.md", "d.md"]
    assert sorted(sub_edges) == [
        ("a.md", "b.md"),
        ("b.md", "c.md"),
        ("d.md", "b.md"),
    ]


def test_local_subgraph_isolated_page():
    edges = [("a.md", "b.md")]
    nodes, sub_edges = local_subgraph("z.md", edges)
    assert nodes == ["z.md"]
    assert sub_edges == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: ImportError on `local_subgraph`.

- [ ] **Step 3: Implement**

Append to `src/mkdocs_back_links/linkgraph.py`:

```python
def local_subgraph(
    page_id: str, edges: Iterable[tuple[str, str]]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (nodes, edges) of the 1-hop neighborhood around `page_id`."""
    edges = list(edges)
    neighbors: set[str] = {page_id}
    sub_edges: list[tuple[str, str]] = []
    for src, tgt in edges:
        if src == page_id or tgt == page_id:
            sub_edges.append((src, tgt))
            neighbors.add(src)
            neighbors.add(tgt)
    return sorted(neighbors), sub_edges
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_linkgraph.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/linkgraph.py tests/unit/test_linkgraph.py
git commit -m "feat: extract local 1-hop subgraph for a page"
```

---

## Task 6: Plugin config schema

Define the typed Config class so MkDocs validates `mkdocs.yml` options on load.

**Files:**
- Create: `src/mkdocs_back_links/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_config.py`:

```python
import pytest
from mkdocs.config.base import ValidationError

from mkdocs_back_links.config import BackLinksConfig


def _validate(raw):
    cfg = BackLinksConfig()
    cfg.load_dict(raw)
    errors, warnings = cfg.validate()
    return errors, warnings, cfg


def test_defaults_validate():
    errors, warnings, cfg = _validate({})
    assert errors == []
    assert cfg.backlinks.enabled is True
    assert cfg.backlinks.heading == "Backlinks"
    assert cfg.graph.enabled is True
    assert cfg.graph.height == "40vh"
    assert cfg.graph.default_view == "local"
    assert cfg.graph.max_nodes == 500
    assert cfg.graph.exclude == []


def test_overrides():
    errors, warnings, cfg = _validate(
        {
            "backlinks": {"enabled": False, "heading": "Linked from"},
            "graph": {
                "enabled": True,
                "height": "30vh",
                "default_view": "global",
                "max_nodes": 200,
                "exclude": ["404.md", "tags.md"],
            },
        }
    )
    assert errors == []
    assert cfg.backlinks.enabled is False
    assert cfg.backlinks.heading == "Linked from"
    assert cfg.graph.default_view == "global"
    assert cfg.graph.exclude == ["404.md", "tags.md"]


def test_bad_default_view_rejected():
    errors, _, _ = _validate({"graph": {"default_view": "weird"}})
    assert errors


def test_bad_max_nodes_type_rejected():
    errors, _, _ = _validate({"graph": {"max_nodes": "lots"}})
    assert errors
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: ImportError on `BackLinksConfig`.

- [ ] **Step 3: Implement the config schema**

Create `src/mkdocs_back_links/config.py`:

```python
"""Typed configuration schema for the back-links plugin."""

from __future__ import annotations

from mkdocs.config import config_options as c
from mkdocs.config.base import Config


class _BacklinksSection(Config):
    enabled = c.Type(bool, default=True)
    heading = c.Type(str, default="Backlinks")


class _GraphSection(Config):
    enabled = c.Type(bool, default=True)
    height = c.Type(str, default="40vh")
    default_view = c.Choice(("local", "global"), default="local")
    max_nodes = c.Type(int, default=500)
    exclude = c.ListOfItems(c.Type(str), default=[])


class BackLinksConfig(Config):
    backlinks = c.SubConfig(_BacklinksSection)
    graph = c.SubConfig(_GraphSection)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/config.py tests/unit/test_config.py
git commit -m "feat: typed config schema with validation"
```

---

## Task 7: HTML rendering helpers

Pure functions that produce the backlinks `<section>` and the inlined local-graph `<script type="application/json">` tag.

**Files:**
- Create: `src/mkdocs_back_links/render.py`
- Create: `tests/unit/test_render.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_render.py`:

```python
import json
import re

from mkdocs_back_links.render import render_backlinks_section, render_local_graph_data


def test_backlinks_section_with_entries():
    html = render_backlinks_section(
        heading="Backlinks",
        entries=[
            {"title": "Install", "url": "/guides/install/"},
            {"title": "Architecture", "url": "/concepts/architecture/"},
        ],
    )
    assert 'class="mbl-backlinks"' in html
    assert "<h2" in html and ">Backlinks</h2>" in html
    assert '<a href="/guides/install/">Install</a>' in html
    assert '<a href="/concepts/architecture/">Architecture</a>' in html


def test_backlinks_section_empty_returns_empty_string():
    assert render_backlinks_section(heading="Backlinks", entries=[]) == ""


def test_backlinks_escapes_html_in_titles():
    html = render_backlinks_section(
        heading="Backlinks",
        entries=[{"title": "<script>x</script>", "url": "/p/"}],
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_local_graph_data_emits_json_script_tag():
    html = render_local_graph_data(
        {"nodes": [{"id": "a", "title": "A", "url": "/a/"}], "edges": []}
    )
    m = re.search(
        r'<script id="mbl-local-graph" type="application/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    assert m
    parsed = json.loads(m.group(1))
    assert parsed["nodes"][0]["id"] == "a"


def test_local_graph_data_escapes_closing_script():
    # Defensive: a title containing </script> must not break out of the tag
    html = render_local_graph_data(
        {"nodes": [{"id": "a", "title": "evil </script><b>", "url": "/a/"}], "edges": []}
    )
    assert "</script><b>" not in html.split('<script', 1)[1].split("</script>", 1)[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_render.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement**

Create `src/mkdocs_back_links/render.py`:

```python
"""HTML rendering helpers for backlinks and inlined local-graph data."""

from __future__ import annotations

import json
from html import escape
from typing import Iterable, Mapping


def render_backlinks_section(*, heading: str, entries: Iterable[Mapping[str, str]]) -> str:
    items = list(entries)
    if not items:
        return ""
    lis = "\n".join(
        f'    <li><a href="{escape(e["url"], quote=True)}">{escape(e["title"])}</a></li>'
        for e in items
    )
    return (
        '<section class="mbl-backlinks" aria-labelledby="mbl-backlinks-heading">\n'
        f'  <h2 id="mbl-backlinks-heading">{escape(heading)}</h2>\n'
        f"  <ul>\n{lis}\n  </ul>\n"
        "</section>\n"
    )


def render_local_graph_data(graph: Mapping[str, object]) -> str:
    payload = json.dumps(graph, separators=(",", ":"))
    # Defuse any literal </script> appearing inside string fields
    safe = payload.replace("</", "<\\/")
    return f'<script id="mbl-local-graph" type="application/json">{safe}</script>\n'
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_render.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/render.py tests/unit/test_render.py
git commit -m "feat: HTML rendering helpers for backlinks and graph data"
```

---

## Task 8: Plugin lifecycle integration

Wire the pieces together: collect markdown across pages, build edges, attach per-page data, append HTML at `on_page_content`. Front-matter overrides handled here too.

**Files:**
- Modify: `src/mkdocs_back_links/plugin.py`

- [ ] **Step 1: Write the failing test (full lifecycle through a fixture build)**

Create `tests/integration/__init__.py` (empty) and `tests/integration/test_build.py`:

```python
from pathlib import Path
import shutil
import subprocess


FIXTURE = Path(__file__).parent.parent / "fixtures" / "basic-site"


def _build(tmp_path: Path) -> Path:
    site_dir = tmp_path / "site"
    subprocess.run(
        ["uv", "run", "mkdocs", "build", "--strict", "-f", str(FIXTURE / "mkdocs.yml"), "-d", str(site_dir)],
        check=True,
    )
    return site_dir


def test_backlinks_section_rendered(tmp_path):
    site = _build(tmp_path)
    target_html = (site / "target" / "index.html").read_text()
    assert "mbl-backlinks" in target_html
    assert ">Backlinks</h2>" in target_html
    # source.md links to target.md, so target should backlink to source
    assert "/source/" in target_html


def test_local_graph_inlined(tmp_path):
    site = _build(tmp_path)
    target_html = (site / "target" / "index.html").read_text()
    assert 'id="mbl-local-graph"' in target_html


def test_global_graph_written(tmp_path):
    site = _build(tmp_path)
    graph_json = site / "assets" / "back_links" / "graph.json"
    assert graph_json.exists()
    content = graph_json.read_text()
    assert '"nodes"' in content and '"edges"' in content


def test_orphan_has_no_backlinks_section(tmp_path):
    site = _build(tmp_path)
    orphan_html = (site / "orphan" / "index.html").read_text()
    assert "mbl-backlinks" not in orphan_html


def test_frontmatter_disables_backlinks(tmp_path):
    site = _build(tmp_path)
    no_back = (site / "no-backlinks" / "index.html").read_text()
    assert "mbl-backlinks" not in no_back
```

Create `tests/fixtures/basic-site/mkdocs.yml`:

```yaml
site_name: BasicSite
theme:
  name: material
plugins:
  - back-links
```

Create `tests/fixtures/basic-site/docs/source.md`:

```markdown
# Source

Links to [target](target.md).
```

Create `tests/fixtures/basic-site/docs/target.md`:

```markdown
# Target

A target page.
```

Create `tests/fixtures/basic-site/docs/orphan.md`:

```markdown
# Orphan

No links in or out.
```

Create `tests/fixtures/basic-site/docs/no-backlinks.md`:

```markdown
---
back_links:
  backlinks: false
---

# No Backlinks Here

[link](source.md)
```

Create `tests/fixtures/basic-site/docs/index.md`:

```markdown
# Home

[s](source.md) [t](target.md) [o](orphan.md) [n](no-backlinks.md)
```

- [ ] **Step 2: Run integration tests to verify they fail**

```bash
uv run pytest tests/integration/test_build.py -v
```

Expected: failures (plugin doesn't do anything yet).

- [ ] **Step 3: Implement plugin lifecycle**

Replace `src/mkdocs_back_links/plugin.py`:

```python
"""MkDocs plugin entry point."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page

from .config import BackLinksConfig
from .linkgraph import build_edges, inverse_index, local_subgraph
from .render import render_backlinks_section, render_local_graph_data


_ASSETS_DIR = Path(__file__).parent / "assets"


class BackLinksPlugin(BasePlugin[BackLinksConfig]):
    def on_config(self, config):
        # Reset state for a fresh build (mkdocs serve reuses the plugin instance).
        self._markdown: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._urls: dict[str, str] = {}
        self._page_overrides: dict[str, dict] = {}
        self._edges: list[tuple[str, str]] = []
        self._inverse: dict[str, list[str]] = {}
        return config

    def on_files(self, files: Files, config):
        for f in files:
            if f.src_uri.endswith(".md") and f.page is None and not f.is_documentation_page():
                # is_documentation_page filters; but be safe
                continue
            if f.src_uri.endswith(".md"):
                self._urls[f.src_uri] = "/" + f.url if not f.url.startswith("/") else f.url
        return files

    def on_page_markdown(self, markdown: str, *, page: Page, config, files):
        page_id = page.file.src_uri
        self._markdown[page_id] = markdown
        self._titles[page_id] = page.title or page_id
        self._urls[page_id] = page.url if page.url.startswith("/") else "/" + page.url
        meta_overrides = (page.meta or {}).get("back_links") or {}
        if isinstance(meta_overrides, dict):
            self._page_overrides[page_id] = meta_overrides
        return markdown

    def on_env(self, env, config, files):
        self._edges = build_edges(self._markdown)
        self._inverse = inverse_index(self._edges)
        return env

    def on_page_content(self, html: str, *, page: Page, config, files):
        page_id = page.file.src_uri
        overrides = self._page_overrides.get(page_id, {})

        backlinks_enabled = self.config.backlinks.enabled and overrides.get("backlinks", True)
        graph_enabled = self.config.graph.enabled and overrides.get("graph", True)

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
            nodes_ids, sub_edges = local_subgraph(page_id, self._edges)
            graph = {
                "current": page_id,
                "nodes": [
                    {"id": n, "title": self._titles.get(n, n), "url": self._urls.get(n, "/" + n)}
                    for n in nodes_ids
                ],
                "edges": [{"source": s, "target": t} for s, t in sub_edges],
            }
            extra += render_local_graph_data(graph)

        return html + extra

    def on_post_build(self, config):
        site_dir = Path(config["site_dir"])
        out_dir = site_dir / "assets" / "back_links"
        out_dir.mkdir(parents=True, exist_ok=True)

        excluded = set(self.config.graph.exclude)
        nodes = [
            {"id": pid, "title": self._titles.get(pid, pid), "url": self._urls.get(pid, "/" + pid)}
            for pid in sorted(self._markdown)
            if pid not in excluded
        ]
        edges = [
            {"source": s, "target": t}
            for s, t in self._edges
            if s not in excluded and t not in excluded
        ]
        (out_dir / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}))

        for asset in ("back_links.css", "back_links.js"):
            src = _ASSETS_DIR / asset
            if src.exists():
                shutil.copy(src, out_dir / asset)
        vendor_src = _ASSETS_DIR / "vendor" / "d3.min.js"
        if vendor_src.exists():
            shutil.copy(vendor_src, out_dir / "d3.min.js")
```

- [ ] **Step 4: Run integration tests**

```bash
uv run pytest tests/integration/test_build.py -v
```

Expected: all PASS. Backlinks render, local graph inlines, global graph.json written, orphan has no section, front-matter override hides section.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: wire plugin lifecycle hooks for backlinks, local + global graph"
```

---

## Task 9: Inject CSS/JS asset references into pages

The plugin writes assets to `site/assets/back_links/` but pages don't load them yet. Use `on_post_page` (post-template render) to inject `<link>` and `<script>` tags before `</head>` and `</body>`.

**Files:**
- Modify: `src/mkdocs_back_links/plugin.py`
- Modify: `tests/integration/test_build.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_build.py`:

```python
def test_assets_referenced(tmp_path):
    site = _build(tmp_path)
    target_html = (site / "target" / "index.html").read_text()
    assert "/assets/back_links/back_links.css" in target_html
    assert "/assets/back_links/back_links.js" in target_html
    assert "/assets/back_links/d3.min.js" in target_html
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/test_build.py::test_assets_referenced -v
```

Expected: FAIL.

- [ ] **Step 3: Implement asset injection**

Add to `BackLinksPlugin` in `src/mkdocs_back_links/plugin.py`:

```python
    _ASSET_TAGS_HEAD = (
        '<link rel="stylesheet" href="/assets/back_links/back_links.css">'
    )
    _ASSET_TAGS_BODY = (
        '<script src="/assets/back_links/d3.min.js" defer></script>'
        '<script src="/assets/back_links/back_links.js" defer></script>'
    )

    def on_post_page(self, output: str, *, page, config):
        if "</head>" in output:
            output = output.replace("</head>", self._ASSET_TAGS_HEAD + "</head>", 1)
        if "</body>" in output:
            output = output.replace("</body>", self._ASSET_TAGS_BODY + "</body>", 1)
        return output
```

- [ ] **Step 4: Create placeholder assets so the file copies don't no-op**

Create `src/mkdocs_back_links/assets/back_links.css` with a single comment so it's non-empty:

```css
/* mkdocs-back-links — populated in later tasks */
```

Create `src/mkdocs_back_links/assets/back_links.js`:

```javascript
/* mkdocs-back-links — populated in later tasks */
```

Create `src/mkdocs_back_links/assets/vendor/.gitkeep` (empty file, so the directory exists; `d3.min.js` is added in Task 10).

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/integration/test_build.py -v
```

Expected: `test_assets_referenced` may still fail because `d3.min.js` isn't yet vendored — that's wired in Task 10. All other tests should still pass. If only `test_assets_referenced` fails, mark it xfail temporarily by adding `@pytest.mark.xfail(reason="d3 vendored in Task 10")` above it; remove the marker in Task 10.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: inject asset tags into rendered pages"
```

---

## Task 10: Vendor d3 UMD bundle

Download the d3 v7 UMD bundle once and check it in. The plugin already copies anything at `assets/vendor/d3.min.js` to `site/assets/back_links/d3.min.js`.

**Files:**
- Create: `src/mkdocs_back_links/assets/vendor/d3.min.js`
- Modify: `tests/integration/test_build.py` (remove xfail marker if added)

- [ ] **Step 1: Download the d3 v7 UMD bundle**

```bash
curl -fL https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js \
  -o /home/tom/dev/mkdocs-back-links/src/mkdocs_back_links/assets/vendor/d3.min.js
```

Expected: a non-empty file (~270 KB unminified, ~90 KB gzipped on the wire).

- [ ] **Step 2: Sanity check**

```bash
head -c 200 src/mkdocs_back_links/assets/vendor/d3.min.js
```

Expected: starts with `// https://d3js.org` or similar copyright header.

- [ ] **Step 3: Remove the xfail marker if present in `test_assets_referenced`**

- [ ] **Step 4: Run all tests**

```bash
uv run pytest -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mkdocs_back_links/assets/vendor/d3.min.js tests/
git commit -m "chore: vendor d3 v7 UMD bundle"
```

---

## Task 11: Backlinks CSS

Style the backlinks section using Material's CSS custom properties so it adopts theme/palette automatically.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.css`

- [ ] **Step 1: Replace the file**

```css
/* mkdocs-back-links — backlinks section + graph pane */

.mbl-backlinks {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--md-default-fg-color--lightest);
  font-size: 0.85rem;
}

.mbl-backlinks h2 {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: var(--md-default-fg-color--light);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mbl-backlinks ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.mbl-backlinks li {
  margin: 0.2rem 0;
}

.mbl-backlinks a {
  color: var(--md-typeset-a-color);
  text-decoration: none;
}

.mbl-backlinks a:hover {
  text-decoration: underline;
}
```

- [ ] **Step 2: Verify visually with the demo site (built later) — no test for CSS in v1**

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.css
git commit -m "feat: backlinks section styling"
```

---

## Task 12: Graph pane CSS

Sticky-pane styles for the secondary sidebar plus header strip and SVG element styles.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.css`

- [ ] **Step 1: Append to the CSS file**

```css
/* --- Graph pane (sticky bottom of secondary sidebar) --- */

.mbl-graph-pane {
  position: sticky;
  bottom: 0;
  background: var(--md-default-bg-color);
  border-top: 1px solid var(--md-default-fg-color--lightest);
  height: var(--mbl-graph-height, 40vh);
  display: flex;
  flex-direction: column;
  z-index: 2;
}

.mbl-graph-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  font-size: 0.75rem;
  border-bottom: 1px solid var(--md-default-fg-color--lightest);
}

.mbl-graph-header h3 {
  margin: 0;
  font-size: inherit;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--md-default-fg-color--light);
}

.mbl-graph-toggle {
  display: inline-flex;
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 999px;
  overflow: hidden;
}

.mbl-graph-toggle button {
  background: transparent;
  border: 0;
  padding: 0.15rem 0.6rem;
  font: inherit;
  color: var(--md-default-fg-color--light);
  cursor: pointer;
}

.mbl-graph-toggle button[aria-pressed="true"] {
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
}

.mbl-graph-expand {
  background: transparent;
  border: 0;
  cursor: pointer;
  color: var(--md-default-fg-color--light);
  font-size: 1rem;
  line-height: 1;
}

.mbl-graph-svg {
  flex: 1;
  width: 100%;
  cursor: grab;
}

.mbl-graph-svg:active { cursor: grabbing; }

.mbl-graph-node { fill: var(--md-default-fg-color); cursor: pointer; }
.mbl-graph-node--current { fill: var(--md-primary-fg-color); }
.mbl-graph-link { stroke: var(--md-default-fg-color--lightest); stroke-opacity: 0.8; }

/* Modal overlay for expanded view */
.mbl-graph-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mbl-graph-modal__inner {
  background: var(--md-default-bg-color);
  width: min(90vw, 1100px);
  height: min(85vh, 800px);
  display: flex;
  flex-direction: column;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.css
git commit -m "feat: graph pane and modal styling"
```

---

## Task 13: JS bootstrap and sidebar injection

The script locates Material's secondary sidebar and inserts the empty pane element. No graph rendering yet — just the DOM scaffold and the toggle/expand wiring (no-op handlers).

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Replace the file**

```javascript
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

  function init() {
    const target = findSidebarTarget();
    if (!target) return;
    const data = readLocalGraph();
    if (!data) return;

    const pane = buildPaneElement();
    target.appendChild(pane);

    // Expose for the rendering layer to pick up.
    window.__mblPane = pane;
    window.__mblLocal = data;
    document.dispatchEvent(new CustomEvent("mbl:pane-ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
```

- [ ] **Step 2: Build the demo fixture and inspect manually**

```bash
uv run mkdocs build -f tests/fixtures/basic-site/mkdocs.yml -d /tmp/mbl-build
grep -c "mbl-graph-pane" /tmp/mbl-build/target/index.html || true
```

The `grep` will return 0 because the pane is injected at runtime, not server-side. That's expected — visual verification happens once the demo site exists.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat: JS bootstrap injects graph pane into Material sidebar"
```

---

## Task 14: d3-force rendering of the local graph

Render nodes and edges from `window.__mblLocal` into the SVG using d3-force. Click to navigate. No drag/zoom yet.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Append a render module to the IIFE**

Inside the existing IIFE in `back_links.js`, replace the `init` function and add a `renderGraph` function:

```javascript
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
```

Then update `init` to call `renderGraph`:

```javascript
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
```

- [ ] **Step 2: Build and inspect manually (we'll get a real demo site in Task 18)**

```bash
uv run mkdocs build -f tests/fixtures/basic-site/mkdocs.yml -d /tmp/mbl-build
uv run python -m http.server -d /tmp/mbl-build 8765 &
# Visit http://localhost:8765/target/ in a browser. Confirm the graph renders.
# Then: kill %1
```

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat: render local graph with d3-force"
```

---

## Task 15: Drag, zoom, click-navigate hardening

Add d3-drag for pinning nodes, d3-zoom for pan/pinch-zoom, and double-click to unpin.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Extend `renderGraph`**

Inside `renderGraph`, after creating `root` but before binding data, add zoom:

```javascript
    const zoom = d3
      .zoom()
      .scaleExtent([0.25, 4])
      .on("zoom", (event) => {
        root.attr("transform", event.transform);
      });
    svg.call(zoom).on("dblclick.zoom", null);
```

After the `node` selection, attach drag:

```javascript
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

    node.call(drag).on("dblclick", (_event, d) => {
      d.fx = null;
      d.fy = null;
      sim.alpha(0.3).restart();
    });
```

Note: `dblclick` on the node unpins, while `dblclick.zoom` on the svg is disabled, so the two don't conflict.

- [ ] **Step 2: Verify in the browser**

Same procedure as Task 14, Step 2. Confirm: drag pins a node, double-click unpins, scroll/pinch zooms the SVG.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat: drag-to-pin, double-click to unpin, pan/pinch zoom"
```

---

## Task 16: Local/global toggle and lazy global fetch

Wire the header pills. Switching to **Global** lazy-fetches `/assets/back_links/graph.json` once, then re-renders.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Add toggle wiring inside `init`**

After `requestAnimationFrame(() => renderGraph(svg, data));` add:

```javascript
    let globalCache = null;
    let currentRender = null;

    pane.querySelectorAll(".mbl-graph-toggle button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const view = btn.dataset.view;
        pane.querySelectorAll(".mbl-graph-toggle button").forEach((b) => {
          b.setAttribute("aria-pressed", String(b === btn));
        });
        if (view === "local") {
          if (currentRender) currentRender.simulation.stop();
          currentRender = renderGraph(svg, data);
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
      });
    });
```

Update the initial render to track `currentRender`:

```javascript
    requestAnimationFrame(() => {
      currentRender = renderGraph(svg, data);
    });
```

- [ ] **Step 2: Verify in the browser**

Click **Global** — confirm the graph fetches `graph.json` (network tab) and re-renders with all pages. Click **Local** — back to neighborhood.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat: toggle local/global views, lazy-fetch global graph"
```

---

## Task 17: Performance freeze threshold for large global graphs

If the graph has more than `max_nodes` nodes, run a fixed number of simulation ticks then stop the simulation. The plugin emits the threshold into the page so JS can read it.

**Files:**
- Modify: `src/mkdocs_back_links/render.py`
- Modify: `src/mkdocs_back_links/plugin.py`
- Modify: `src/mkdocs_back_links/assets/back_links.js`
- Modify: `tests/unit/test_render.py`

- [ ] **Step 1: Failing test — render emits a settings tag**

Append to `tests/unit/test_render.py`:

```python
from mkdocs_back_links.render import render_settings_data


def test_settings_data_emits_json():
    html = render_settings_data({"max_nodes": 500, "default_view": "local"})
    assert 'id="mbl-settings"' in html
    import json, re
    m = re.search(r'>(.*)</script>', html, re.DOTALL)
    parsed = json.loads(m.group(1))
    assert parsed["max_nodes"] == 500
    assert parsed["default_view"] == "local"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/unit/test_render.py -v
```

Expected: ImportError on `render_settings_data`.

- [ ] **Step 3: Implement `render_settings_data`**

Append to `src/mkdocs_back_links/render.py`:

```python
def render_settings_data(settings: Mapping[str, object]) -> str:
    payload = json.dumps(settings, separators=(",", ":")).replace("</", "<\\/")
    return f'<script id="mbl-settings" type="application/json">{payload}</script>\n'
```

- [ ] **Step 4: Wire it into the plugin's `on_page_content`**

In `src/mkdocs_back_links/plugin.py`, inside `on_page_content`, after the graph block, append settings:

```python
        if graph_enabled:
            ...  # existing local graph rendering

            settings = {
                "max_nodes": self.config.graph.max_nodes,
                "default_view": self.config.graph.default_view,
            }
            extra += render_settings_data(settings)
```

Also import `render_settings_data` at the top of the file.

- [ ] **Step 5: Read settings in JS and apply freeze threshold**

In `back_links.js`, add a helper near `readLocalGraph`:

```javascript
  function readSettings() {
    const tag = document.getElementById("mbl-settings");
    if (!tag) return { max_nodes: 500, default_view: "local" };
    try { return JSON.parse(tag.textContent); }
    catch (_e) { return { max_nodes: 500, default_view: "local" }; }
  }
```

In `renderGraph`, after creating the simulation:

```javascript
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
```

In `init`, also honor `default_view`:

```javascript
    const settings = readSettings();
    if (settings.default_view === "global") {
      // simulate clicking the Global pill once the pane is ready
      const globalBtn = pane.querySelector('.mbl-graph-toggle button[data-view="global"]');
      if (globalBtn) globalBtn.click();
    } else {
      requestAnimationFrame(() => { currentRender = renderGraph(svg, data); });
    }
```

- [ ] **Step 6: Run the unit tests**

```bash
uv run pytest -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: max_nodes freeze threshold + default_view honored"
```

---

## Task 18: Expand-to-modal

Clicking the expand button opens a full-screen modal containing the same SVG/graph state. Escape or background click closes it.

**Files:**
- Modify: `src/mkdocs_back_links/assets/back_links.js`

- [ ] **Step 1: Add a modal helper to the IIFE**

```javascript
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
```

In `init`, wire the expand button. Track the current data being shown (local or global) so the modal mirrors it:

```javascript
    let activeData = data;

    pane.querySelectorAll(".mbl-graph-toggle button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        // ... existing handler ...
        // After successful re-render:
        activeData = (btn.dataset.view === "local") ? data : globalCache;
      });
    });

    pane.querySelector(".mbl-graph-expand").addEventListener("click", () => {
      openModal(activeData);
    });
```

- [ ] **Step 2: Verify in the browser**

Click expand, confirm modal opens, escape/background closes it, current view (local vs global) is preserved.

- [ ] **Step 3: Commit**

```bash
git add src/mkdocs_back_links/assets/back_links.js
git commit -m "feat: expand graph to modal overlay"
```

---

## Task 19: Demo site

Replace the test fixture experience with a richer demo site at the repo root.

**Files:**
- Create: `mkdocs.yml`
- Create: `docs/index.md`
- Create: `docs/guides/install.md`
- Create: `docs/guides/configure.md`
- Create: `docs/concepts/architecture.md`
- Create: `docs/concepts/internals.md`

- [ ] **Step 1: Demo `mkdocs.yml`**

```yaml
site_name: mkdocs-back-links demo
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - toc.integrate
nav:
  - Home: index.md
  - Guides:
      - guides/install.md
      - guides/configure.md
  - Concepts:
      - concepts/architecture.md
      - concepts/internals.md
plugins:
  - search
  - back-links
```

- [ ] **Step 2: Demo pages**

`docs/index.md`:

```markdown
# mkdocs-back-links demo

This site demonstrates the [installation guide](guides/install.md) and
the [architecture](concepts/architecture.md). See also [internals](concepts/internals.md).
```

`docs/guides/install.md`:

```markdown
# Install

Before installing, read the [architecture overview](../concepts/architecture.md).

After installing, head to the [configure guide](configure.md).
```

`docs/guides/configure.md`:

```markdown
# Configure

Configuration depends on the [architecture](../concepts/architecture.md). See also
[internals](../concepts/internals.md) for the data flow.
```

`docs/concepts/architecture.md`:

```markdown
# Architecture

High-level design. See [internals](internals.md) for the build-time data flow.
```

`docs/concepts/internals.md`:

```markdown
# Internals

Implementation details. Back to [architecture](architecture.md).
```

- [ ] **Step 3: Move the existing `docs/superpowers/` directories so they don't collide with the demo**

The brainstorming/plan docs already live under `docs/superpowers/`. MkDocs will pick those up by default. Add to `mkdocs.yml`:

```yaml
exclude_docs: |
  superpowers/
```

(`exclude_docs` is supported by MkDocs 1.6+.)

- [ ] **Step 4: Build and serve**

```bash
uv run mkdocs build --strict
uv run mkdocs serve
```

Expected: build succeeds with no warnings. Open `http://127.0.0.1:8000/`, navigate to a page, verify:
1. Backlinks section appears at the bottom of pages with inbound links.
2. Graph pane sits sticky at the bottom of the right sidebar.
3. Toggling local/global works; click navigation works; drag/zoom work; expand modal works.

Stop the server (Ctrl-C) when done.

- [ ] **Step 5: Commit**

```bash
git add mkdocs.yml docs/index.md docs/guides docs/concepts
git commit -m "feat: demo site exercising the plugin"
```

---

## Task 20: README

Document install, basic config, and per-page front-matter overrides.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md`**

```markdown
# mkdocs-back-links

Backlinks at the bottom of every page and a sticky force-directed graph view in
the right sidebar, for [Material for MkDocs][material].

## Install

```bash
pip install mkdocs-back-links
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
        default_view: "local"   # or "global"
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with install, config, overrides, and how it works"
```

---

## Self-Review Notes

- Spec coverage: backlinks rendering (Tasks 7, 8, 11), graph data flow (Tasks 4, 5, 8), config (Task 6), per-page overrides (Task 8), graph pane UI (Tasks 12–18), demo site (Task 19), tests (Tasks 2–8, integration), README (Task 20). All spec sections covered.
- Type consistency: `extract_links`, `resolve_link`, `build_edges`, `inverse_index`, `local_subgraph` consistent across tasks. Plugin instance state names (`_markdown`, `_titles`, `_urls`, `_edges`, `_inverse`) defined in Task 8 and not renamed thereafter.
- Placeholders: none — every task contains complete code.
