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
