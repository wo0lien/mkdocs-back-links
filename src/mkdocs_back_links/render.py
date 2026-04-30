"""HTML rendering helpers for backlinks and inlined local-graph data."""

from __future__ import annotations

import json
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def render_backlinks_section(
    *, heading: str, entries: Iterable[Mapping[str, str]]
) -> str:
    items = list(entries)
    if not items:
        return ''
    lis = '\n'.join(
        f'    <li><a href="{escape(e["url"], quote=True)}">{escape(e["title"])}</a></li>'
        for e in items
    )
    return (
        '<section class="mbl-backlinks" aria-labelledby="mbl-backlinks-heading">\n'
        f'  <h2 id="mbl-backlinks-heading">{escape(heading)}</h2>\n'
        f'  <ul>\n{lis}\n  </ul>\n'
        '</section>\n'
    )


def render_local_graph_data(graph: Mapping[str, object]) -> str:
    payload = json.dumps(graph, separators=(',', ':'))
    # Defuse any literal </script> appearing inside string fields
    safe = payload.replace('</', '<\\/')
    return f'<script id="mbl-local-graph" type="application/json">{safe}</script>\n'


def render_settings_data(settings: Mapping[str, object]) -> str:
    payload = json.dumps(settings, separators=(',', ':')).replace('</', '<\\/')
    return f'<script id="mbl-settings" type="application/json">{payload}</script>\n'


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
        return ''

    rendered = []
    for e in items:
        same_page = e['source_page'] == target_page
        if same_page:
            label_raw = '# ' + (
                e.get('section_title_lookup') or e['source_section'] or e['page_title']
            )
            href = '#' + (e['source_section'] or '')
        else:
            label_raw = e['page_title']
            href = e['page_url']
        rendered.append((label_raw.lower(), label_raw, href))
    rendered.sort(key=lambda r: r[0])

    lis = '\n'.join(
        f'    <li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>'
        for _key, label, href in rendered
    )

    inner = (
        f'  <h3>Backlinks to "{escape(section_title)}"</h3>\n  <ul>\n{lis}\n  </ul>\n'
    )

    if collapse_threshold > 0 and len(items) > collapse_threshold:
        body = (
            f'  <details>\n'
            f'    <summary>↩ {len(items)} backlinks</summary>\n'
            f'{inner}'
            f'  </details>\n'
        )
    else:
        body = inner

    return (
        f'<aside class="mbl-section-backlinks" data-section="{escape(section_slug, quote=True)}">\n'
        f'{body}'
        '</aside>\n'
    )
