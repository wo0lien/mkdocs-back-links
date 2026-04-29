"""Pure functions for parsing markdown and building the link graph."""

from __future__ import annotations

import re
from typing import NamedTuple
from markdown.extensions.toc import slugify as _md_slugify

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


import posixpath


def resolve_link(source_id: str, href: str) -> tuple[str, str | None] | None:
    """Resolve a link href to (target_page_id, fragment_or_None).

    Returns None when the link doesn't point to a markdown page or escapes
    the docs root. The fragment is the slug after `#`, or None if absent.
    """
    # Extract fragment from original href before stripping query
    _, _, raw_frag = href.partition("#")
    fragment = raw_frag or None
    # Strip fragment and query to get the page path
    no_frag = href.split("#", 1)[0]
    page_part = no_frag.split("?", 1)[0]
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


from collections import defaultdict
from typing import Iterable, Mapping


def build_edges(pages: Mapping[str, str]) -> list[tuple[str, str]]:
    """Return a sorted, deduped, self-link-free list of (source, target) edges
    where both source and target are keys in `pages`."""
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


def inverse_index(edges: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """Return a map of target_id -> sorted list of source ids that link to it."""
    inv: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        inv[target].add(source)
    return {k: sorted(v) for k, v in inv.items()}


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
