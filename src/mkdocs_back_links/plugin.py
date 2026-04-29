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
                "url": self._urls.get(page_id, "/" + page_id) + "#" + section.slug,
            })
        return nodes

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
            page_nodes_ids, _page_sub_edges = local_subgraph(page_id, page_edges)

            nodes_by_id: dict[str, dict] = {
                n: {
                    "id": n,
                    "type": "page",
                    "title": self._titles.get(n, n),
                    "url": self._urls.get(n, "/" + n),
                }
                for n in page_nodes_ids
            }
            for pid in page_nodes_ids:
                for sn in self._section_nodes_for_page(pid):
                    nodes_by_id[sn["id"]] = sn

            edges_by_key: dict[tuple[str, str, str], dict] = {}

            def add_edge(src: str, tgt: str, kind: str) -> None:
                if src == tgt:
                    return
                edges_by_key[(src, tgt, kind)] = {"source": src, "target": tgt, "kind": kind}

            for s, _ss, t, ts in self._edges:
                if s not in page_nodes_ids and t not in page_nodes_ids:
                    continue
                tgt_id = f"{t}#{ts}" if ts and f"{t}#{ts}" in nodes_by_id else t
                if tgt_id not in nodes_by_id:
                    continue
                if s not in nodes_by_id:
                    continue
                add_edge(s, tgt_id, "cross")

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

        seen: set[tuple[str, str, str]] = set()
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
