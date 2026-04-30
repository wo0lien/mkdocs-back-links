from importlib.metadata import entry_points


def test_plugin_is_registered():
    eps = entry_points(group='mkdocs.plugins')
    names = {ep.name for ep in eps}
    assert 'back-links' in names


def test_plugin_class_loadable():
    eps = entry_points(group='mkdocs.plugins', name='back-links')
    (ep,) = eps
    cls = ep.load()
    assert cls.__name__ == 'BackLinksPlugin'
