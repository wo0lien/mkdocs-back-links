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
    max_nodes = c.Type(int, default=500)
    exclude = c.ListOfItems(c.Type(str), default=[])


class BackLinksConfig(Config):
    backlinks = c.SubConfig(_BacklinksSection)
    graph = c.SubConfig(_GraphSection)
