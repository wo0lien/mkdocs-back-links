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
