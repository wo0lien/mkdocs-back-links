"""Typed configuration schema for the back-links plugin."""

from __future__ import annotations

from mkdocs.config import config_options as c
from mkdocs.config.base import Config


class _BacklinksSection(Config):
    enabled = c.Type(bool, default=True)
    heading = c.Type(str, default='Backlinks')
    section_collapse_threshold = c.Type(int, default=3)


class _GraphColors(Config):
    """Per-element color overrides. Empty string = keep the Material default.

    Each value is emitted as the corresponding `--mbl-graph-*` CSS custom
    property at `:root` scope, so any valid CSS color (hex, rgb, hsl, var())
    is accepted.
    """

    node = c.Type(str, default='')
    section = c.Type(str, default='')
    current_fill = c.Type(str, default='')
    current_stroke = c.Type(str, default='')
    link = c.Type(str, default='')
    highlight = c.Type(str, default='')
    label = c.Type(str, default='')
    current_label = c.Type(str, default='')


class _GraphSection(Config):
    enabled = c.Type(bool, default=True)
    height = c.Type(str, default='40vh')
    max_nodes = c.Type(int, default=500)
    section_levels = c.ListOfItems(c.Type(int), default=[2, 3])
    section_nodes_same_page = c.Type(bool, default=False)
    center_strength = c.Type(float, default=0.08)
    section_cluster_threshold = c.Type(int, default=2)
    hide_when_orphan = c.Type(bool, default=True)
    exclude = c.ListOfItems(c.Type(str), default=[])
    colors = c.SubConfig(_GraphColors)


class BackLinksConfig(Config):
    backlinks = c.SubConfig(_BacklinksSection)
    graph = c.SubConfig(_GraphSection)
