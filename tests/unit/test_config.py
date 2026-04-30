from mkdocs_back_links.config import BackLinksConfig


def _validate(raw):
    cfg = BackLinksConfig()
    cfg.load_dict(raw)
    errors, warnings = cfg.validate()
    return errors, warnings, cfg


def test_defaults_validate():
    errors, _warnings, cfg = _validate({})
    assert errors == []
    assert cfg.backlinks.enabled is True
    assert cfg.backlinks.heading == 'Backlinks'
    assert cfg.graph.enabled is True
    assert cfg.graph.height == '40vh'
    assert cfg.graph.max_nodes == 500
    assert cfg.graph.exclude == []


def test_overrides():
    errors, _warnings, cfg = _validate(
        {
            'backlinks': {'enabled': False, 'heading': 'Linked from'},
            'graph': {
                'enabled': True,
                'height': '30vh',
                'max_nodes': 200,
                'exclude': ['404.md', 'tags.md'],
            },
        }
    )
    assert errors == []
    assert cfg.backlinks.enabled is False
    assert cfg.backlinks.heading == 'Linked from'
    assert cfg.graph.max_nodes == 200
    assert cfg.graph.exclude == ['404.md', 'tags.md']


def test_bad_max_nodes_type_rejected():
    errors, _, _ = _validate({'graph': {'max_nodes': 'lots'}})
    assert errors


def test_section_defaults():
    errors, _, cfg = _validate({})
    assert errors == []
    assert cfg.backlinks.section_collapse_threshold == 3
    assert cfg.graph.section_levels == [2, 3]
    assert cfg.graph.section_nodes_same_page is False


def test_section_overrides():
    errors, _, cfg = _validate(
        {
            'backlinks': {'section_collapse_threshold': 0},
            'graph': {'section_levels': [2], 'section_nodes_same_page': True},
        }
    )
    assert errors == []
    assert cfg.backlinks.section_collapse_threshold == 0
    assert cfg.graph.section_levels == [2]
    assert cfg.graph.section_nodes_same_page is True


def test_bad_section_levels_rejected():
    errors, _, _ = _validate({'graph': {'section_levels': ['two']}})
    assert errors


def test_bad_section_collapse_threshold_rejected():
    errors, _, _ = _validate({'backlinks': {'section_collapse_threshold': 'many'}})
    assert errors
