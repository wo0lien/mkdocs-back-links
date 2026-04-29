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


def render_settings_data(settings: Mapping[str, object]) -> str:
    payload = json.dumps(settings, separators=(",", ":")).replace("</", "<\\/")
    return f'<script id="mbl-settings" type="application/json">{payload}</script>\n'
