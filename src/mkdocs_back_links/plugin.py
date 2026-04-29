"""MkDocs plugin entry point."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page

from .config import BackLinksConfig
from .linkgraph import (
    build_edges,
    extract_sections,
    inverse_page_index,
    inverse_section_index,
    local_subgraph,
)
from .render import render_backlinks_section, render_local_graph_data, render_settings_data


_ASSETS_DIR = Path(__file__).parent / "assets"

_HEADING_TAG_RE = re.compile(r'<h([1-6])\s+id="([^"]+)"[^>]*>')


class BackLinksPlugin(BasePlugin[BackLinksConfig]):
    def on_config(self, config):
        # Reset state for a fresh build (mkdocs serve reuses the plugin instance).
        self._markdown: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._urls: dict[str, str] = {}
        self._page_overrides: dict[str, dict] = {}
        self._sections: dict[str, list] = {}
        self._section_titles: dict[tuple[str, str], str] = {}
        self._edges: list = []
        self._inverse: dict[str, list[str]] = {}
        self._inverse_section: dict[tuple[str, str], list] = {}
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
        sections = extract_sections(markdown, list(self.config.graph.section_levels))
        self._sections[page_id] = sections
        for s in sections:
            self._section_titles[(page_id, s.slug)] = s.title
        return markdown

    def on_env(self, env, config, files):
        levels = list(self.config.graph.section_levels)
        self._edges = build_edges(self._markdown, section_levels=levels)
        self._inverse = inverse_page_index(self._edges)
        self._inverse_section = inverse_section_index(self._edges)
        return env

    def _build_section_blocks(self, page_id: str) -> dict[str, str]:
        """Map slug -> rendered <aside> for sections of `page_id` that have inbound links."""
        from .render import render_section_backlinks
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

        matches = list(_HEADING_TAG_RE.finditer(html))
        insertions: list[tuple[int, str]] = []
        for i, m in enumerate(matches):
            slug = m.group(2)
            level = int(m.group(1))
            block = blocks.get(slug)
            if block is None:
                continue
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

    def on_page_context(self, context, *, page: Page, config, nav):
        page_id = page.file.src_uri
        overrides = self._page_overrides.get(page_id, {})

        backlinks_enabled = self.config.backlinks.enabled and overrides.get("backlinks", True)
        graph_enabled = self.config.graph.enabled and overrides.get("graph", True)

        # Insert per-section backlinks blocks into the rendered HTML at the right boundaries.
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
            for s, _ss, t, _ts in self._edges
            if s not in excluded and t not in excluded and s != t
        ]
        (out_dir / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}))

        for asset in ("back_links.css", "back_links.js"):
            src = _ASSETS_DIR / asset
            if src.exists():
                shutil.copy(src, out_dir / asset)
        vendor_src = _ASSETS_DIR / "vendor" / "d3.min.js"
        if vendor_src.exists():
            shutil.copy(vendor_src, out_dir / "d3.min.js")
